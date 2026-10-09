import requests
import yaml
import os

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


def fetch_jobs(role=None, max_jobs=30, india_only=False):
    """Auto-detect ATS for each company and fetch matching jobs."""
    jobs = []
    role_terms = _expand_role(role)
    company_list = INDIA_ONLY_COMPANIES if india_only else COMPANIES

    for entry in company_list:
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
