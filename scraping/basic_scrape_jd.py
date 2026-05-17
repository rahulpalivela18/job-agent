from bs4 import BeautifulSoup
import re
import requests


def scrape_jd(url):
    """
    Scrape job description from any URL.
    Returns dict with title, company, description, url.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = (
            soup.find("h1", {"data-test": "job-title"}).get_text(strip=True)
            if soup.find("h1", {"data-test": "job-title"})
            else soup.find("h1", class_=re.compile("title", re.I)).get_text(strip=True)
            if soup.find("h1", class_=re.compile("title", re.I))
            else soup.find("h1").get_text(strip=True)
            if soup.find("h1")
            else soup.title.string
            if soup.title
            else "Unknown"
        )

        company = (
            soup.find("a", {"data-test": "company-name"}).get_text(strip=True)
            if soup.find("a", {"data-test": "company-name"})
            else soup.find("div", class_=re.compile("company", re.I)).get_text(
                strip=True
            )
            if soup.find("div", class_=re.compile("company", re.I))
            else "Unknown"
        )

        desc_container = (
            soup.find("div", {"data-test": "job-description"})
            or soup.find("section", class_=re.compile("description", re.I))
            or soup.find("div", class_=re.compile("description|content|detail", re.I))
            or soup.find("main")
            or soup.find("article")
            or soup.body
        )

        description = (
            desc_container.get_text(separator=" ", strip=True) if desc_container else ""
        )
        description = re.sub(r"\s+", " ", description).strip()[:5000]

        return {
            "title": title,
            "company": company,
            "url": url,
            "description": description,
            "source": "scraped",
            "location": "Unknown",
        }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None
