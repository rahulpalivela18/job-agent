import sys


def get_multiline_input(prompt="Paste description (Ctrl+D to finish):"):
    print(prompt)
    print("(Paste and press Ctrl+D on Mac/Linux or Ctrl+Z + Enter on Windows)\n")

    data = sys.stdin.read()
    return data.strip()


def manual_jobs():
    jobs = []

    n = int(input("How many jobs do you want to paste? "))

    for i in range(n):
        print(f"\n--- Job {i + 1} ---")
        title = input("Title: ")
        company = input("Company: ")
        description = get_multiline_input()[:1500]
        url = input("URL: ")

        jobs.append(
            {"title": title, "company": company, "description": description, "url": url}
        )

    return jobs


def add_manual_job(jobs_list=None, scrape_func=None):
    print("\n--- Manual Job Entry ---")
    print("Paste job URL or press Enter for manual entry:")
    user_input = input("URL/Input: ").strip()

    if user_input.startswith("http"):
        if scrape_func:
            job = scrape_func(user_input)
        else:
            from scraping.basic_scrape_jd import scrape_jd

            job = scrape_jd(user_input)

        if job and len(job.get("description", "")) > 100:
            print(f"\n✓ Scraped: {job['title']} at {job['company']}")
            print(f"  Description length: {len(job['description'])} chars")
            return job
        else:
            print("\n⚠️  Could not scrape this URL (site may require JavaScript).")
            print("   Falling back to manual entry.\n")
            user_input = ""  # Reset to trigger manual path
    if not user_input.startswith("http"):
        title = input("Job Title: ").strip()
        company = input("Company: ").strip()
        print(
            "Description (paste text, then press Ctrl+D on Mac/Linux or Ctrl+Z+Enter on Windows):"
        )
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        description = "\n".join(lines).strip()
        url = input("URL (optional): ").strip()

        return {
            "title": title,
            "company": company,
            "url": url,
            "description": description,
            "source": "manual",
        }


if __name__ == "__main__":
    jobs = manual_jobs()

    print("\nYou entered the following jobs:")
    for job in jobs:
        print(f"{job['title']} @ {job['company']} - {job['url']}")
