from jobs import fetch_jobs
from storage import save_job, is_already_applied
from manual_input import add_manual_job
from scraping.basic_scrape_jd import scrape_jd
from scraping.utils import min_yoe_required, is_senior_role
from resume_builder import build_resume
import webbrowser

from llm import LLM


def load_resume():
    with open("resume.txt", "r") as f:
        return f.read()


def main(llm):
    resume = load_resume()
    mode = input("Choose mode: (1) Auto fetch (2) Manual input: ")

    if mode == "2":
        jobs = []
        while True:
            job = add_manual_job()
            if job:
                jobs.append(job)
            more = input("\nAdd another job? (y/n): ").strip().lower()
            if more != "y":
                break
    else:
        role = input("Enter the job role you are interested in: ")
        jobs = fetch_jobs(role)

    max_jobs = 5
    count = 0

    for job in jobs:
        is_applied, company_name = is_already_applied(job["url"])
        if is_applied:
            print(f"Already applied to {job['title']} @ {company_name}, skipping.")
            continue

        # Get/fetch JD text for YOE check before LLM call
        jd_text = job.get("description", "")
        if not jd_text or len(jd_text) < 100:
            try:
                jd_text = scrape_jd(job["url"])
                job["description"] = jd_text
            except Exception:
                pass

        # if jd_text and len(jd_text) > 50:
        #     yoe = min_yoe_required(jd_text)
        #     if yoe >= 3:
        #         print(f"  Skipping {job['title']} — requires {yoe}+ years experience")
        #         continue

        if jd_text and is_senior_role(jd_text):
            print(f" Skipping {job['title']}, identified as senior role")
            continue

        score = llm.score_job(resume, job)
        print("Score:", score)

        if score < 6:
            print("Skpping this job, score below 6 :(")
            continue

        print("\n" + "=" * 50)
        print(f"{job['title']} @ {job['company']}")
        print(f"Score: {score}/10")

        # Generate tailored resume PDF
        if not company_name or company_name.lower() == "unknown":
            company_name = input(
                f'  Company name for "{job.get("title", "unknown")}": '
            ).strip()
            job["company"] = company_name
        if jd_text and len(jd_text) > 100:
            print("\n--- GENERATING TAILORED RESUME ---\n")
            try:
                pdf_path = build_resume(jd_text, company_name, llm)
                print(f"\n📄 Tailored PDF: {pdf_path}")
            except Exception as e:
                print(f"⚠️ Resume generation failed: {e}")

        result = llm.generate_application(resume, job)

        if "error" in result:
            print("⚠️ JSON failed:\n", result["error"])
            continue

        print("\n--- COVER LETTER ---\n")
        print(result.get("cover_letter"))

        print("\n--- WHY FIT ---\n")
        print(result.get("fit_reason"))

        print("\nApply:", job["url"] if job.get("url") else "(no URL)")

        job_data = {
            "title": job["title"],
            "company": job["company"],
            "score": score,
            "cover_letter": result.get("cover_letter"),
            "fit_reason": result.get("fit_reason"),
            "url": job["url"],
            "status": "pending",
        }

        save_job(job_data)

        open_now = input("\nOpen job link? (y/n): ")
        if open_now.lower() == "y":
            webbrowser.open(job["url"])

        applied = input("Mark as applied? (y/n): ")
        if applied.lower() == "y":
            job_data["status"] = "applied"
            save_job(job_data)

        count += 1

        if count >= max_jobs:
            print("\nReached limit for this run ✅")
            break


if __name__ == "__main__":
    llm = LLM(provider="openai", model="gpt-4.1-mini")
    main(llm)
