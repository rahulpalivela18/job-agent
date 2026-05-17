import requests
import yaml
import os

ROLE_SYNONYMS = {}
_syn_path = os.path.join(os.path.dirname(__file__), "role_synonyms.yml")
if os.path.exists(_syn_path):
    with open(_syn_path) as f:
        ROLE_SYNONYMS = yaml.safe_load(f) or {}

COMPANIES = {
    "greenhouse": [
        "stripe",
        "notion",
        "airbnb",
        "databricks",
        "openai",
        "databricks",
        "robinhood",
    ],
    "lever": ["openai", "ashbyhq"],
    "ashby": ["ashbyhq", "quantcast", "hume", "perplexity"],
    "bamboohr": [],
    "teamtailor": [],
    "workday": [],
}


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
        jobs = resp.json().get("jobs", [])

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
                "url": job.get("jobUrl")
                or f"https://boards.ashbyhq.com/{company_slug}/{job.get('id')}",
                "description": job.get("description", ""),  # Full JD here!
                "location": job.get("location", {}).get("name", "Unknown"),
                "source": "ashby",
            }

    except Exception as e:
        print(f"Error fetching from Ashby for {company_slug}: {e} :(")


def fetch_greenhouse(company_slug, role_terms=None):
    """Fetch jobs from Greenhouse API"""

    try:
        resp = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs",
            timeout=10,
        )
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])

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

    except Exception as e:
        print(f"Error fetching from Greenhouse for {company_slug}: {e} :(")


def fetch_lever(company_slug, role_terms=None):
    """Fetch jobs from Lever API"""

    try:
        resp = requests.get(
            f"https://api.lever.co/v0/postings/{company_slug}", timeout=10
        )
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])

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
                "description": job.get("description", ""),  # Full JD here!
                "location": job.get("location", {}).get("name", "Unknown"),
                "source": "lever",
            }

    except Exception as e:
        print(f"Error fetching from Lever for {company_slug}: {e} :(")


def fetch_jobs(role=None, max_jobs=30):
    """Fetch jobs across all ATS platforms for the specified companies."""
    jobs = []
    role_terms = _expand_role(role)

    green_house_companies = COMPANIES.get("greenhouse", [])
    lever_companies = COMPANIES.get("lever", [])
    ashby_companies = COMPANIES.get("ashby", [])

    for company in green_house_companies:
        try:
            jobs.extend(list(fetch_greenhouse(company, role_terms)))
        except:
            continue

    for company in lever_companies:
        try:
            jobs.extend(list(fetch_lever(company, role_terms)))
        except:
            continue

    for company in ashby_companies:
        try:
            jobs.extend(list(fetch_ashby(company, role_terms)))
        except:
            continue

    print("Total jobs fetched:", len(jobs))

    return jobs[:max_jobs]
