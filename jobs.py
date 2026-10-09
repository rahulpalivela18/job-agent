import requests
import yaml
import os
import xml.etree.ElementTree as ET

from scraping.basic_scrape_jd import _html_to_text

ROLE_SYNONYMS = {}
_syn_path = os.path.join(os.path.dirname(__file__), "role_synonyms.yml")
if os.path.exists(_syn_path):
    with open(_syn_path) as f:
        ROLE_SYNONYMS = yaml.safe_load(f) or {}

# Flat list of companies to fetch jobs from.
# Each entry is either:
#   "company_name"  — name used as ATS slug (covers most companies)
#   ("name", "slug") — custom slug when the ATS board name differs
COMPANIES = [
    "gitlab",
    "spotify",
    "perplexity",
    "quantcast",
    "deel",
    ("ashbyhq", "Ashby"),
    ("hume", "humeai"),
    "intuit",
]

INDIA_ONLY_COMPANIES = [
    ("razorpay", "razorpaysoftwareprivatelimited"),
    ("phonepe", "phonepe"),
    "myntra",
    ("groww", "groww"),
    ("inmobi", "inmobi"),
    "dezerv",
    "alphagrep",
    "neysa",
    ("paypay", "paypay"),
    ("sila", "sila"),
    "podium",
    "modmed",
    "ghx",
    "enzene",
    ("twinhealth", "twinhealth"),
    "careeredge",
    "graviton",
    "go2andaman",
    "vymo",
    "helium",
    ("kimbal", "kimbal"),
    "sada",
    "acurus",
    ("glance", "glance"),
    "quadeye",
    "infuseb2b",
    ("valpro", "valpro"),
    ("propstack", "propstack"),
    ("taboola", "taboola"),
    "axio",
    ("storable", "storable"),
    "nk securities",
    "verona matchmaking",
    ("techgrove by banyan software", "techgrovebybanyansoftware"),
    ("blenheim chalcot india", "blenheimchalcotindia"),
    ("forbes & company limited", "forbes"),
    ("tru fru", "trufru"),
    "one digital",
    "m0",
    "innovative embedded systems pvt ltd siic iit kanpur",
]


def _expand_role(role):
    """Convert user role query into list of title substrings to match."""
    if not role:
        return []
    key = role.lower().strip().replace(" ", "_").replace("/", "_")
    if key in ROLE_SYNONYMS:
        return [t.lower() for t in ROLE_SYNONYMS[key]]
    return [role.lower()]


def fetch_ashby(company_slug, role_terms=None):
    """Fetch jobs from Ashby API"""
    try:
        resp = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}?includeCompensation=true",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        jobs = data if isinstance(data, list) else data.get("jobs", [])

        for job in jobs:
            title = job.get("title", "").lower()

            if any(
                x in title.lower()
                for x in ["senior", "lead", "staff", "manager", "director"]
            ):
                continue

            if role_terms and not any(term in title for term in role_terms):
                continue

            yield {
                "title": title,
                "company": company_slug,
                "url": job.get("jobUrl")
                or f"https://boards.ashbyhq.com/{company_slug}/{job.get('id')}",
                "description": job.get("descriptionPlain")
                or job.get("description", ""),
                "location": job.get("location")
                if isinstance(job.get("location"), str)
                else "Unknown",
                "source": "ashby",
            }

    except Exception:
        return


GREENHOUSE_BOARD_URLS = [
    "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "https://job-boards.greenhouse.io/{slug}",
    "https://boards.greenhouse.io/{slug}",
]


def fetch_greenhouse(company_slug, role_terms=None):
    """Fetch jobs from Greenhouse API"""

    try:
        resp = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])

        for job in jobs:
            title = job.get("title", "").lower()

            if any(
                x in title.lower()
                for x in ["senior", "lead", "staff", "manager", "director"]
            ):
                continue

            if role_terms and not any(term in title for term in role_terms):
                continue

            job_id = job.get("id")
            # Fetch detail to get full content (Greenhouse list endpoint omits it)
            description = ""
            try:
                detail = requests.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs/{job_id}",
                    timeout=10,
                )
                detail.raise_for_status()
                description = detail.json().get("content", "")
            except Exception:
                pass

            yield {
                "title": title,
                "company": company_slug,
                "url": job.get("jobUrl")
                or f"https://boards.greenhouse.io/{company_slug}/jobs/{job_id}",
                "description": description,
                "location": job.get("location", {}).get("name", "Unknown"),
                "source": "greenhouse",
            }

    except Exception:
        return


def fetch_lever(company_slug, role_terms=None):
    """Fetch jobs from Lever API"""

    try:
        resp = requests.get(
            f"https://api.lever.co/v0/postings/{company_slug}", timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        jobs = data if isinstance(data, list) else data.get("jobs", [])

        for job in jobs:
            title = job.get("title", "").lower()

            # Skipping senior roles early
            if any(
                x in title.lower()
                for x in ["senior", "lead", "staff", "manager", "director"]
            ):
                continue

            # Filter by role if provided
            if role_terms and not any(term in title for term in role_terms):
                continue

            # yield is a generator
            yield {
                "title": title,
                "company": company_slug,
                "url": job.get("hostedUrl")
                or f"https://jobs.lever.co/{company_slug}/{job.get('id')}",
                "description": job.get("description", ""),
                "location": job.get("categories", {}).get("location", "Unknown"),
                "source": "lever",
            }

    except Exception:
        return


# ---------------------------------------------------------------------------
# Remote-first job boards (aggregators that are remote-native)
# ---------------------------------------------------------------------------

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

SENIOR_TITLE_KEYWORDS = (
    "senior",
    "lead",
    "staff",
    "principal",
    "manager",
    "director",
    "head of",
)


def _is_senior_title(title):
    return any(kw in title for kw in SENIOR_TITLE_KEYWORDS)


def _matches_role(title_l, role_terms):
    return not role_terms or any(term in title_l for term in role_terms)


def _is_worldwide_location(location):
    loc = (location or "").lower()
    return not loc or any(
        w in loc for w in ("worldwide", "anywhere", "global", "remote")
    )


def fetch_himalayas(
    role_terms=None, max_pages=5, query=None, worldwide_only=False
):
    """Remote-only jobs from the Himalayas public API (no auth).

    Uses the filtered ``/jobs/api/search`` endpoint when a query or
    ``worldwide_only`` is given (supports ``q``, ``worldwide``, ``sort``,
    ``page``), otherwise falls back to the cursor-paginated browse feed.
    """
    jobs = []

    # Filtered search path — server-side q + worldwide filter.
    if query or worldwide_only or role_terms:
        q = query or (role_terms[0] if role_terms else "")
        page = 1
        for _ in range(max_pages):
            params = {"sort": "recent", "page": page}
            if q:
                params["q"] = q
            if worldwide_only:
                params["worldwide"] = "true"
            try:
                resp = requests.get(
                    "https://himalayas.app/jobs/api/search",
                    params=params,
                    headers={"User-Agent": UA},
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                break
            batch = data.get("jobs", [])
            if not batch:
                break
            for job in batch:
                title = (job.get("title") or "").lower()
                if not title or _is_senior_title(title):
                    continue
                if role_terms and not _matches_role(title, role_terms):
                    continue
                restrictions = job.get("locationRestrictions") or []
                location = (
                    ", ".join(restrictions)
                    if isinstance(restrictions, list)
                    else restrictions
                )
                jobs.append(
                    {
                        "title": title,
                        "company": job.get("companyName")
                        or job.get("companySlug")
                        or "Unknown",
                        "url": job.get("applicationLink")
                        or job.get("guid")
                        or "",
                        "description": _html_to_text(
                            job.get("description") or ""
                        ),
                        "location": location or "Remote",
                        "source": "himalayas",
                    }
                )
            total = data.get("totalCount", 0)
            if total and page * 20 >= total:
                break
            page += 1
        if jobs:
            return jobs
        # Fall through to browse feed if search returned nothing.

    params = {}
    for _ in range(max_pages):
        try:
            resp = requests.get(
                "https://himalayas.app/jobs/api",
                params=params,
                headers={"User-Agent": UA},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            break

        for job in data.get("jobs", []):
            title = (job.get("title") or "").lower()
            if not title or _is_senior_title(title):
                continue
            if not _matches_role(title, role_terms):
                continue
            restrictions = job.get("locationRestrictions") or []
            location = (
                ", ".join(restrictions)
                if isinstance(restrictions, list)
                else restrictions
            )
            if worldwide_only and not _is_worldwide_location(location):
                continue
            jobs.append(
                {
                    "title": title,
                    "company": job.get("companyName")
                    or job.get("companySlug")
                    or "Unknown",
                    "url": job.get("applicationLink") or job.get("guid") or "",
                    "description": _html_to_text(job.get("description") or ""),
                    "location": location or "Remote",
                    "source": "himalayas",
                }
            )

        cursor = data.get("nextCursor")
        if not cursor:
            break
        params = {"cursor": cursor}

    return jobs


WWR_FEEDS = {
    "programming": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "all": "https://weworkremotely.com/remote-jobs.rss",
}


def fetch_weworkremotely(role_terms=None, feed="programming"):
    """Remote-only jobs from We Work Remotely RSS feeds."""
    url = WWR_FEEDS.get(feed, WWR_FEEDS["programming"])
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception:
        return []

    jobs = []
    for item in root.iter("item"):
        raw_title = (item.findtext("title") or "").strip()
        company, _, title = raw_title.partition(": ")
        if not title:
            title, company = raw_title, "Unknown"
        title_l = title.lower()
        if not title_l or _is_senior_title(title_l):
            continue
        if not _matches_role(title_l, role_terms):
            continue
        jobs.append(
            {
                "title": title,
                "company": company or "Unknown",
                "url": item.findtext("link") or item.findtext("guid") or "",
                "description": _html_to_text(item.findtext("description") or ""),
                "location": item.findtext("region") or "Remote",
                "source": "weworkremotely",
            }
        )
    return jobs


def fetch_remotive(role_terms=None, worldwide_only=False, search=None):
    """Remote-only jobs from the Remotive public API (no auth).

    GET https://remotive.com/api/remote-jobs with optional ``search`` /
    ``category`` / ``limit`` params. ``candidate_required_location`` carries
    the geo restriction (``"Worldwide"`` = anywhere).
    """
    params = {}
    if search or (role_terms and len(role_terms) == 1):
        params["search"] = search or role_terms[0]
    try:
        resp = requests.get(
            "https://remotive.com/api/remote-jobs",
            params=params,
            headers={"User-Agent": UA},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    raw = data.get("jobs", []) if isinstance(data, dict) else []
    jobs = []
    server_filtered = bool(params)  # API already matched title+description
    for job in raw:
        title = (job.get("title") or "").strip()
        title_l = title.lower()
        if not title_l or _is_senior_title(title_l):
            continue
        if not server_filtered and not _matches_role(title_l, role_terms):
            continue
        location = job.get("candidate_required_location") or "Remote"
        if worldwide_only and not _is_worldwide_location(location):
            continue
        jobs.append(
            {
                "title": title,
                "company": job.get("company_name") or "Unknown",
                "url": job.get("url") or "",
                "description": _html_to_text(job.get("description") or ""),
                "location": location,
                "source": "remotive",
            }
        )
    return jobs


def fetch_remoteok(role_terms=None, worldwide_only=False):
    """Remote-only jobs from the RemoteOK public API (no auth).

    GET https://remoteok.com/api returns a JSON array whose first element
    is a legal notice (no ``position`` key) — skipped. ``0`` salaries mean
    undisclosed. Needs a browser-like User-Agent or it 403s.
    """
    try:
        resp = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    jobs = []
    for entry in data:
        if not isinstance(entry, dict) or not entry.get("position"):
            continue  # legal notice / metadata element
        title = (entry.get("position") or "").strip()
        title_l = title.lower()
        if not title_l or _is_senior_title(title_l):
            continue
        if not _matches_role(title_l, role_terms):
            continue
        location = entry.get("location") or "Remote"
        if worldwide_only and not _is_worldwide_location(location):
            continue
        url = entry.get("url") or entry.get("apply_url") or ""
        if url.startswith("/"):
            url = f"https://remoteok.com{url}"
        elif entry.get("slug") and not url:
            url = f"https://remoteok.com/remote-jobs/{entry['slug']}"
        jobs.append(
            {
                "title": title,
                "company": entry.get("company") or "Unknown",
                "url": url,
                "description": _html_to_text(entry.get("description") or ""),
                "location": location,
                "source": "remoteok",
            }
        )
    return jobs


def fetch_jobicy(role_terms=None, worldwide_only=False):
    """Remote-only jobs from the Jobicy public API (no auth).

    GET https://jobicy.com/api/v2/remote-jobs — last ~7 days of remote
    listings. Parser is defensive about field names.
    """
    try:
        resp = requests.get(
            "https://jobicy.com/api/v2/remote-jobs",
            headers={"User-Agent": UA},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    if isinstance(data, dict):
        raw = data.get("jobs") or data.get("data") or []
    elif isinstance(data, list):
        raw = data
    else:
        return []
    jobs = []
    for job in raw:
        if not isinstance(job, dict):
            continue
        title = (
            job.get("jobTitle") or job.get("title") or ""
        ).strip()
        title_l = title.lower()
        if not title_l or _is_senior_title(title_l):
            continue
        if not _matches_role(title_l, role_terms):
            continue
        location = (
            job.get("jobGeo")
            or job.get("jobLocation")
            or job.get("location")
            or job.get("candidate_required_location")
            or "Remote"
        )
        if isinstance(location, list):
            location = ", ".join(location)
        if worldwide_only and not _is_worldwide_location(location):
            continue
        jobs.append(
            {
                "title": title,
                "company": job.get("companyName")
                or job.get("company")
                or "Unknown",
                "url": job.get("jobLink")
                or job.get("url")
                or job.get("link")
                or "",
                "description": _html_to_text(
                    job.get("jobDescription")
                    or job.get("description")
                    or job.get("jobExcerpt")
                    or ""
                ),
                "location": location or "Remote",
                "source": "jobicy",
            }
        )
    return jobs


def fetch_remote(
    role=None, max_jobs=50, worldwide_only=True, max_pages=5
):
    """Dedicated remote-worldwide fetcher (all free, no auth).

    Aggregates remote-native boards only — Himalayas (search API with
    ``worldwide=true``), WeWorkRemotely (RSS), Remotive, RemoteOK, Jobicy —
    dedupes by URL and returns up to ``max_jobs``. Pass
    ``worldwide_only=False`` to include region-restricted remote roles
    (e.g. US-only, EMEA-only).

    ``fetch_jobs`` stays the normal path for company ATS boards.
    """
    role_terms = _expand_role(role)
    query = role.strip() if role and role.strip() else None
    jobs: list = []
    seen_urls: set = set()

    sources = [
        (
            "Himalayas",
            lambda: fetch_himalayas(
                role_terms,
                max_pages=max_pages,
                query=query,
                worldwide_only=worldwide_only,
            ),
        ),
        ("WeWorkRemotely", lambda: fetch_weworkremotely(role_terms)),
        (
            "Remotive",
            lambda: fetch_remotive(role_terms, worldwide_only=worldwide_only),
        ),
        (
            "RemoteOK",
            lambda: fetch_remoteok(role_terms, worldwide_only=worldwide_only),
        ),
        (
            "Jobicy",
            lambda: fetch_jobicy(role_terms, worldwide_only=worldwide_only),
        ),
    ]
    for name, fetcher in sources:
        try:
            found = fetcher() or []
        except Exception as e:
            print(f"  {name:>15} → error: {e}")
            continue
        fresh = []
        for job in found:
            url = (job.get("url") or "").strip()
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            fresh.append(job)
        if fresh:
            print(f"  {name:>15} → {len(fresh)} remote jobs")
            jobs.extend(fresh)
        else:
            print(f"  {name:>15} → 0 jobs match")

    print(f"\nTotal remote jobs fetched: {len(jobs)}")
    return jobs[:max_jobs]


def _resolve_company(entry):
    """Normalise a COMPANIES entry into (display_name, api_slug)."""
    if isinstance(entry, (list, tuple)):
        return entry[0], entry[1]
    return entry, entry


def _fetch_with_source(company_slug, fetcher, role_terms):
    """Run a fetcher and return (source_name, jobs) or None."""
    try:
        jobs = list(fetcher(company_slug, role_terms))
        return jobs if jobs else None
    except Exception:
        return None


def _detect_ats(company_slug):
    """Probe which ATS a company uses (without role filter)."""
    for probe_url in GREENHOUSE_BOARD_URLS:
        try:
            r = requests.get(probe_url.format(slug=company_slug), timeout=5)
            if r.ok:
                return ("greenhouse", fetch_greenhouse)
        except Exception:
            continue
    for ats_name, fetcher, url_template in [
        ("lever", fetch_lever, "https://api.lever.co/v0/postings/{slug}"),
        (
            "ashby",
            fetch_ashby,
            "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
        ),
    ]:
        try:
            r = requests.get(url_template.format(slug=company_slug), timeout=5)
            if r.ok:
                return ats_name, fetcher
        except Exception:
            continue
    return None, None


def fetch_jobs(role=None, max_jobs=30, india_only=False, remote_only=False):
    """Normal path: company ATS boards (Greenhouse/Lever/Ashby auto-detect).

    For remote-worldwide aggregation use :func:`fetch_remote` instead.
    ``remote_only=True`` is kept for backward compat and delegates to
    :func:`fetch_remote`.
    """
    if remote_only:
        return fetch_remote(role, max_jobs=max_jobs, worldwide_only=False)

    jobs = []
    role_terms = _expand_role(role)
    company_list = INDIA_ONLY_COMPANIES if india_only else COMPANIES

    for entry in [] if remote_only else company_list:
        name, slug = _resolve_company(entry)
        ats_name, fetcher = _detect_ats(slug)
        if not fetcher:
            print(f"  {name:>15} → no ATS detected")
            continue
        found = _fetch_with_source(slug, fetcher, role_terms)
        if found:
            print(f"  {name:>15} → {ats_name:>12} ({len(found)} jobs)")
            jobs.extend(found)
        else:
            print(f"  {name:>15} → {ats_name:>12} (0 jobs match role)")

    print(f"\nTotal jobs fetched: {len(jobs)}")

    return jobs[:max_jobs]
