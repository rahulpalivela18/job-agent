"""Robust job-description scraper.

Strategy ladder (cheapest, most reliable first):

1. Board-specific API — Greenhouse / Lever / Ashby / SmartRecruiters
   (these boards expose free JSON APIs, no HTML scraping needed)
2. Plain HTTP + schema.org ``JobPosting`` JSON-LD (covers most static boards)
3. iframe follow — many boards (incl. Greenhouse/Lever) load the JD in an
   iframe; we fetch that and re-run extraction
4. Playwright headless render — JS-heavy / React SPA pages
5. Optional LLM extraction from raw visible text (only if ``llm`` passed)

``scrape_jd(url)`` keeps the original public signature, so existing callers
(``main.py``, ``manual_input.py``) keep working unchanged.
"""

import html as _html
import json
import re
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

TIMEOUT = 15
MIN_DESCRIPTION = 100
MIN_FULL_JD = 800
MAX_DESCRIPTION = 5000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _clean_text(text):
    """Collapse whitespace/newlines into single spaces."""
    return re.sub(r"\s+", " ", text or "").strip()


def _html_to_text(value):
    """Strip HTML markup into plain text.

    Many ATS JSON APIs (e.g. Greenhouse) return the description field
    HTML-escaped, so BeautifulSoup would otherwise see literal ``&lt;p&gt;``
    text. Unescape first, then parse only when real tags are present.
    """
    if not value:
        return ""
    text = _html.unescape(value)
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
    return _clean_text(text)


def _job_dict(title, company, url, description, source, location="Unknown"):
    return {
        "title": title or "Unknown",
        "company": company or "Unknown",
        "url": url,
        "description": _clean_text(description)[:MAX_DESCRIPTION],
        "source": source,
        "location": location or "Unknown",
    }


def _http_get(url, timeout=TIMEOUT):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception:
        return None


# --------------------------------------------------------------------------
# 1. Board-specific APIs
# --------------------------------------------------------------------------


def _host(url):
    return (urlparse(url).netloc or "").lower()


def _path_parts(url):
    return [p for p in urlparse(url).path.split("/") if p]


def _detect_board(url):
    host = _host(url)
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    if "smartrecruiters.com" in host:
        return "smartrecruiters"
    if "myworkdayjobs.com" in host:
        return "workday"
    if "jobvite.com" in host:
        return "jobvite"
    return None


def _fetch_greenhouse(url):
    parts = _path_parts(url)
    if len(parts) < 3 or not parts[2].isdigit():
        return None
    slug, job_id = parts[0], parts[2]
    resp = _http_get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}")
    if not resp:
        return None
    data = resp.json()
    if not data.get("content"):
        return None
    description = _html_to_text(data["content"])
    location = data.get("location") or {}
    if isinstance(location, dict):
        location = location.get("name", "Unknown")
    return _job_dict(
        data.get("title", ""),
        data.get("company_name") or slug,
        url,
        description,
        "greenhouse",
        location,
    )


def _og_title(url):
    """Best-effort page title from og:twitter meta tags."""
    resp = _http_get(url)
    if not resp:
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.find("meta", {"property": "og:title"}) or soup.find(
        "meta", {"name": "twitter:title"}
    )
    title = meta.get("content", "") if meta else ""
    if not title and soup.title:
        title = _clean_text(soup.title.get_text())
    return _clean_text(title)


def _fetch_lever(url):
    parts = _path_parts(url)
    if len(parts) < 2:
        return None
    company, job_id = parts[0], parts[1]
    resp = _http_get(f"https://api.lever.co/v0/postings/{company}/{job_id}")
    if not resp:
        return None
    data = resp.json()
    # Lever's API no longer exposes `title`; description lives in
    # descriptionBodyPlain (openingPlain is just the pitch).
    description = _clean_text(
        data.get("descriptionBodyPlain")
        or data.get("descriptionPlain")
        or data.get("text")
        or ""
    )
    if not description:
        return None
    location = data.get("categories", {}).get("location", "Unknown")
    title = data.get("title") or _og_title(data.get("hostedUrl") or url)
    return _job_dict(title, company, url, description, "lever", location)


def _fetch_ashby(url):
    parts = _path_parts(url)
    if len(parts) < 2:
        return None
    company, job_id = parts[0], parts[1]
    resp = _http_get(
        f"https://api.ashbyhq.com/posting-api/job-board/{company}?includeCompensation=true"
    )
    if not resp:
        return None
    data = resp.json()
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    for job in jobs:
        if job_id and job_id in (job.get("jobUrl") or ""):
            location = job.get("location")
            if not isinstance(location, str):
                location = "Unknown"
            return _job_dict(
                job.get("title", ""),
                company,
                url,
                job.get("descriptionPlain") or "",
                "ashby",
                location,
            )
    return None


def _fetch_smartrecruiters(url):
    parts = _path_parts(url)
    if len(parts) < 2:
        return None
    company = parts[0]
    m = re.search(r"\d+", parts[1])
    if not m:
        return None
    posting_id = m.group(0)
    resp = _http_get(
        f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting_id}"
    )
    if not resp:
        return None
    data = resp.json()
    ad = data.get("jobAd", {}) or {}
    sections = ad.get("sections", []) or {}
    raw_sections = sections.values() if isinstance(sections, dict) else sections
    description = ""
    for section in raw_sections:
        if isinstance(section, dict) and section.get("text"):
            description += _html_to_text(section["text"]) + "\n"
    description = _clean_text(description)
    if not description:
        return None
    loc = data.get("location", {}) or {}
    location = f"{loc.get('city', '')} {loc.get('country', '')}".strip() or "Unknown"
    return _job_dict(
        data.get("name", ""), company, url, description, "smartrecruiters", location
    )


_BOARD_FETCHERS = {
    "greenhouse": _fetch_greenhouse,
    "lever": _fetch_lever,
    "ashby": _fetch_ashby,
    "smartrecruiters": _fetch_smartrecruiters,
}


def _fetch_via_api(url):
    board = _detect_board(url)
    fetcher = _BOARD_FETCHERS.get(board)
    if not fetcher:
        return None
    try:
        return fetcher(url)
    except Exception:
        return None


# Careers sites that wrap a custom (non-ATS) JSON API instead of embedding
# standard ATS boards. Host regex → API URL template; ``{job_id}`` is pulled
# from the posting URL. Add more as you find them.
_CAREERS_API = [
    # Celonis careers SPA: /job-detail?jobId=… → dxp-api.celonis.com/v1/jobs/{id}
    (
        re.compile(r"careers\.celonis\.com"),
        "https://dxp-api.celonis.com/v1/jobs/{job_id}",
        "Celonis",
    ),
]


def _extract_job_id(url):
    """Pull a job id out of a careers URL (query param or path)."""
    parsed = urlparse(url)
    job_id = parse_qs(parsed.query).get("jobId", [""])[0]
    if job_id:
        return job_id
    m = re.search(r"/job[/-](\d+)", parsed.path)
    return m.group(1) if m else None


def _fetch_custom_careers_api(url):
    host = _host(url)
    for pattern, api_template, company in _CAREERS_API:
        if not pattern.search(host):
            continue
        job_id = _extract_job_id(url)
        if not job_id:
            return None
        resp = _http_get(api_template.format(job_id=job_id))
        if not resp:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        description = data.get("description") or ""
        if not description:
            return None
        location = data.get("groupedLocation") or data.get("location") or "Unknown"
        return _job_dict(
            data.get("title", ""),
            company,
            url,
            _html_to_text(description),
            "careers-api",
            location,
        )
    return None


# ATS board embeds referenced inside a page (iframes / apply links).
_BOARD_URL_PATTERNS = [
    (
        r"job-boards\.greenhouse\.io/embed/job_app\?for=([a-z0-9_\-]+)&(?:amp;)?token=(\d+)",
        "https://job-boards.greenhouse.io/{slug}/jobs/{job_id}",
    ),
    (
        r"boards\.greenhouse\.io/([a-z0-9_\-]+)/jobs/(\d+)",
        "https://boards.greenhouse.io/{slug}/jobs/{job_id}",
    ),
    (
        r"jobs\.lever\.co/([a-z0-9_\-]+)/([a-f0-9\-]{36})",
        "https://jobs.lever.co/{slug}/{job_id}",
    ),
    (
        r"jobs\.ashbyhq\.com/([a-z0-9_\-]+)/([a-f0-9\-]{36})",
        "https://jobs.ashbyhq.com/{slug}/{job_id}",
    ),
    (
        r"jobs\.smartrecruiters\.com/([a-z0-9_\-]+)/(\d+)-",
        "https://jobs.smartrecruiters.com/{slug}/{job_id}",
    ),
]


def _find_board_url(html):
    """Return a canonical ATS board URL found embedded in a page, if any."""
    for pattern, template in _BOARD_URL_PATTERNS:
        m = re.search(pattern, html or "", re.IGNORECASE)
        if m:
            return template.format(slug=m.group(1), job_id=m.group(2))
    return None


# --------------------------------------------------------------------------
# 2. JSON-LD (schema.org JobPosting) extraction
# --------------------------------------------------------------------------


def _json_ld_jobs(html):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                continue
            try:
                data = json.loads(match.group())
            except Exception:
                continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                found.append(item)
    return found


def _json_ld_job(url, html):
    for job in _json_ld_jobs(html):
        title = job.get("title") or job.get("name")
        description = _html_to_text(
            job.get("description") or job.get("jobDescription") or ""
        )
        if len(description) < MIN_DESCRIPTION:
            continue
        org = job.get("hiringOrganization") or {}
        if isinstance(org, dict):
            company = org.get("name", "")
        else:
            company = org if isinstance(org, str) else ""
        location = ""
        loc = job.get("jobLocation") or {}
        if isinstance(loc, dict):
            addr = loc.get("address") or {}
            if isinstance(addr, dict):
                location = (
                    f"{addr.get('addressLocality', '')} "
                    f"{addr.get('addressRegion', '')}".strip()
                )
            elif isinstance(addr, str):
                location = addr
        return _job_dict(
            title, company, url, description, "json-ld", location or "Unknown"
        )
    return None


# --------------------------------------------------------------------------
# 3. Generic HTML extraction + iframe follow
# --------------------------------------------------------------------------


def _generic_extract(url, html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    title = soup.find("meta", {"property": "og:title"}) or soup.find(
        "meta", {"name": "twitter:title"}
    )
    title = title.get("content", "") if title else ""
    if not title:
        h1 = soup.find("h1")
        title = _clean_text(h1.get_text()) if h1 else ""
    if not title and soup.title:
        title = _clean_text(soup.title.get_text())
    if not title:
        title = "Unknown"

    company = soup.find("meta", {"property": "og:site_name"})
    company = _clean_text(company.get("content", "")) if company else ""

    selectors = [
        "[data-test='job-description']",
        "[data-test='jobDescription']",
        "section[class*='description' i]",
        "div[class*='description' i]",
        "div[class*='job-details' i]",
        "article",
        "main",
        "body",
    ]
    candidates = []
    for selector in selectors:
        for node in soup.select(selector):
            text = _clean_text(node.get_text(separator=" "))
            if text:
                candidates.append(text)
    description = max(candidates, key=len) if candidates else ""
    if len(description) < MIN_DESCRIPTION:
        return None

    return _job_dict(title, company, url, description, "generic", "Unknown")


def _iframe_src(html):
    soup = BeautifulSoup(html, "html.parser")
    for frame in soup.find_all(["iframe", "frame"]):
        src = frame.get("src")
        if src and src.startswith("http"):
            return src
    return None


def _try_html(url, html=None):
    """Extract from a fetched HTML doc: JSON-LD → iframe → generic."""
    if html is None:
        resp = _http_get(url)
        if not resp:
            return None
        html = resp.text

    job = _json_ld_job(url, html)
    if job:
        return job

    src = _iframe_src(html)
    if src:
        resp = _http_get(src)
        if resp:
            job = _json_ld_job(url, resp.text) or _generic_extract(url, resp.text)
            if job:
                return job

    return _generic_extract(url, html)


# --------------------------------------------------------------------------
# 4. Playwright fallback for JS-rendered pages
# --------------------------------------------------------------------------


def _render_impl(url):
    """Render a JS-heavy page headlessly. Returns (html, visible_text)."""
    from playwright.sync_api import sync_playwright

    # Collect all visible text, piercing shadow DOM (used by Workday etc.)
    collect_js = """
    () => {
      const walk = (root) => {
        let text = '';
        const walker = document.createTreeWalker(
          root, NodeFilter.SHOW_TEXT
        );
        let node;
        while ((node = walker.nextNode())) {
          text += (node.textContent || '') + ' ';
        }
        for (const el of root.querySelectorAll('*')) {
          if (el.shadowRoot) text += walk(el.shadowRoot);
        }
        return text;
      };
      return walk(document.body || document.documentElement);
    }
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        page.set_default_timeout(15000)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(500)
        html = page.content()
        texts = []
        for frame in page.frames:
            try:
                texts.append(frame.evaluate(collect_js))
            except Exception:
                pass
        browser.close()

    text = "\n\n".join(t for t in texts if t)
    return html, text


def _render(url):
    """Render a page with a hard wall-clock timeout (Playwright can hang)."""
    import importlib.util

    if importlib.util.find_spec("playwright") is None:
        return None, None

    import threading

    result = {}

    def run():
        try:
            result["out"] = _render_impl(url)
        except Exception:
            result["out"] = (None, None)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=45)
    return result.get("out", (None, None))


def _generic_from_text(text, url):
    if len(text) < MIN_DESCRIPTION:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0][:120] if lines else "Unknown"
    return _job_dict(title, "Unknown", url, text, "generic", "Unknown")


# --------------------------------------------------------------------------
# 5. LLM extraction fallback (optional, requires an llm object)
# --------------------------------------------------------------------------


def _llm_extract(text, llm, url):
    prompt = (
        "Extract the job posting from the raw page text below.\n"
        "Return ONLY valid JSON, no markdown, no explanation:\n"
        '{"title": "...", "company": "...", "location": "...", '
        '"description": "the full job description"}\n\n'
        f"Raw text:\n{text[:6000]}"
    )
    data = llm._safe_json(llm.call(prompt, max_tokens=1200))
    if not data or not data.get("description"):
        return None
    return _job_dict(
        data.get("title", ""),
        data.get("company", ""),
        url,
        data["description"],
        "llm",
        data.get("location", "Unknown"),
    )


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def _better(candidate, job):
    """Return whichever job dict has the fuller description."""
    if not job:
        return candidate
    if not candidate:
        return job
    if len(job["description"]) > len(candidate["description"]):
        return job
    return candidate


def scrape_jd(url, llm=None):
    """Scrape a job description from any URL. Returns a dict or None.

    Strategies in order: board API → custom careers API → HTTP+JSON-LD →
    ATS embed discovery → Playwright render → LLM fallback (only when
    ``llm`` is provided).
    """
    job = _fetch_via_api(url)
    if job:
        return job

    job = _fetch_custom_careers_api(url)
    if job:
        return job

    resp = _http_get(url)
    html = resp.text if resp else None
    if html:
        board_url = _find_board_url(html)
        if board_url:
            job = _fetch_via_api(board_url)
            if job:
                job["url"] = url
                return job

    candidate = _try_html(url, html=html)
    if candidate and len(candidate["description"]) >= MIN_FULL_JD:
        return candidate

    rendered_html, rendered_text = _render(url)
    if rendered_html:
        rendered_job = _try_html(url, html=rendered_html)
        if rendered_job and len(rendered_job["description"]) < MIN_FULL_JD:
            board_url = _find_board_url(rendered_html)
            if board_url:
                api_job = _fetch_via_api(board_url)
                if api_job:
                    api_job["url"] = url
                    rendered_job = api_job
        candidate = _better(candidate, rendered_job)
        candidate = _better(candidate, _generic_from_text(rendered_text, url))

    if candidate and len(candidate["description"]) >= MIN_DESCRIPTION:
        return candidate

    if llm is not None and rendered_text:
        job = _llm_extract(rendered_text, llm, url)
        if job:
            return job

    if candidate:
        return candidate

    print(f"Could not scrape {url}")
    return None
