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


def fetch_himalayas(role_terms=None, max_pages=10):
    """Remote-only jobs from the Himalayas public API.

    The API returns 20 jobs per cursor page and ignores search/filter params,
    so we page through a bounded number of recent pages and filter locally.
    """
    jobs = []
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
            if role_terms and not any(term in title for term in role_terms):
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
        if role_terms and not any(term in title_l for term in role_terms):
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
    """Auto-detect ATS for each company and fetch matching jobs.

    Remote-native boards (Himalayas, WeWorkRemotely) are fetched first so
    remote roles survive the ``max_jobs`` slice. Pass ``remote_only=True``
    to skip company ATS boards entirely.
    """
    jobs = []
    role_terms = _expand_role(role)
    company_list = INDIA_ONLY_COMPANIES if india_only else COMPANIES

    if not india_only:
        for name, fetcher in (
            ("Himalayas", fetch_himalayas),
            ("WeWorkRemotely", fetch_weworkremotely),
        ):
            found = fetcher(role_terms)
            if found:
                print(f"  {name:>15} → {len(found)} remote jobs")
                jobs.extend(found)

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
