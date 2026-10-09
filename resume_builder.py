import sys
import os
import re
from datetime import date
from jinja2 import Environment, FileSystemLoader, select_autoescape

from resume_models import ResumeStore
from llm import LLM
from scraping.jd_processing import keyword_match_summary


def load_env():
    """Load Jinja2 template environment."""
    return Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape(["html"])
    )


def _tag_match_count(tags, kw_set):
    """Count how many tags match the keyword set."""
    return sum(1 for t in tags if t.lower() in kw_set)


def generate_resume_html(
    store: ResumeStore,
    jd_text: str,
    llm: LLM,
    company_slug: str = "company",
    output_dir: str = "output",
) -> str:
    """
    Full pipeline: JD → AI tailoring → fill template → save HTML.
    Priority rules:
      - High-priority jobs (full-time): always included, all bullets
      - Low-priority jobs (internships): only if relevant, max 2 bullets
      - Projects: scored by relevance, max 2 included
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- Step 1: Score pieces by tag match ---
    tag_scores = keyword_match_summary(jd_text, store)
    kw_set = set(kw.lower() for kw in tag_scores["keywords"])
    print(f"  JD keywords: {tag_scores['keywords'][:5]}...")

    # --- Step 2: AI tailor summary ---
    print(f"  Tailoring summary...")
    new_summary = llm.tailor_summary(store.summary, jd_text)

    # --- Step 3: Select and reorder jobs by priority ---
    print(f"  Selecting experiences by priority...")

    high_priority = [j for j in store.work_experience if j.priority == "high"]
    low_priority = [j for j in store.work_experience if j.priority != "high"]

    MIN_EXPERIENCES = 3

    tailored_experiences = []

    # Always include high-priority jobs, all bullets
    for job in high_priority:
        bullets = [b.text for b in job.bullets]
        reordered = llm.reorder_bullets(bullets, jd_text)
        tailored_experiences.append(
            {
                "company": job.company,
                "role": job.role,
                "period": job.period,
                "bullets": reordered,
            }
        )

    # Score low-priority jobs by tag match, add until MIN_EXPERIENCES
    scored_low = [(_tag_match_count(j.tags, kw_set), j) for j in low_priority]
    scored_low.sort(key=lambda x: -x[0])  # best match first

    for score, job in scored_low:
        if len(tailored_experiences) >= MIN_EXPERIENCES:
            break
        bullets = [b.text for b in job.bullets]
        reordered = llm.reorder_bullets(bullets, jd_text)
        max_bullets = 3 if score > 0 else 2
        tailored_experiences.append(
            {
                "company": job.company,
                "role": job.role,
                "period": job.period,
                "bullets": reordered[:max_bullets],
            }
        )

    # --- Step 4: Select top projects by priority + tag match, trimmed ---
    print(f"  Selecting top projects...")
    scored_projects = []
    for p in store.projects:
        tag_score = _tag_match_count(p.tags, kw_set)
        priority_bonus = {"high": 5, "medium": 2, "low": 0}.get(p.priority, 0)
        scored_projects.append((tag_score + priority_bonus, p))

    scored_projects.sort(key=lambda x: -x[0])
    selected_projects = [p for _, p in scored_projects[:2]]

    selected = []
    for p in selected_projects:
        bullets = [b.text for b in p.bullets]
        reordered = llm.reorder_bullets(bullets, jd_text)
        selected.append({"name": p.name, "bullets": reordered, "link": p.link})

    # Score remaining projects, add until MIN_PROJECTS
    selected_names = {s["name"] for s in selected}
    remaining = [p for p in store.projects if p.name not in selected_names]
    remaining.sort(key=lambda p: _tag_match_count(p.tags, kw_set), reverse=True)
    MIN_PROJECTS = min(3, len(store.projects))
    for p in remaining:
        if len(selected) >= MIN_PROJECTS:
            break
        bullets = [b.text for b in p.bullets]
        reordered = llm.reorder_bullets(bullets, jd_text)
        selected.append({"name": p.name, "bullets": reordered, "link": p.link})

    # --- Step 5: Build context for template ---
    skill_map = {
        "Languages": ["Programming Languages"],
        "Frameworks & Libraries": ["AI/ML", "Backend", "Frontend"],
        "Tools & Platforms": ["DevOps", "Databases"],
        "Concepts": ["Core Concepts"],
    }
    all_skills = {cat.category: cat.skills for cat in store.skills}
    skills_data = []
    for group, cats in skill_map.items():
        merged = []
        for c in cats:
            merged.extend(all_skills.get(c, []))
        skills_data.append({"category": group, "skills": merged})

    education_data = [
        {
            "degree": e.degree,
            "school": e.school,
            "gpa": e.gpa,
            "period": e.period,
            "coursework": e.coursework,
        }
        for e in store.education
    ]

    context = {
        "personal": store.personal.model_dump(),
        "summary": new_summary,
        "experiences": tailored_experiences,
        "projects": selected,
        "skills": skills_data,
        "education": education_data,
    }

    # --- Step 7: Render template ---
    env = load_env()
    template = env.get_template("resume_template.html")
    html = template.render(**context)

    # --- Step 8: Save HTML ---
    sanitized_name = re.sub(r"[^a-z0-9]", "-", company_slug.lower())
    today = date.today().isoformat()
    html_path = os.path.join(output_dir, f"resume_{sanitized_name}_{today}.html")
    with open(html_path, "w") as f:
        f.write(html)

    print(f"  Saved: {html_path}")
    return html_path


def html_to_pdf(html_path: str) -> str:
    """
    Convert HTML to PDF using Playwright (headless Chromium).
    Returns path to generated PDF.
    """
    pd_path = html_path.replace(".html", ".pdf")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"file://{os.path.abspath(html_path)}", wait_until="networkidle")
            page.pdf(
                path=pd_path,
                format="letter",
                print_background=True,
                margin={
                    "top": "0.5in",
                    "bottom": "0.5in",
                    "left": "0.5in",
                    "right": "0.5in",
                },
            )
            browser.close()

        pdf_size = os.path.getsize(pd_path)
        print(f"  PDF generated: {pd_path} ({pdf_size / 1024:.1f} KB)")
        return pd_path
    except Exception as e:
        print(f"  PDF generation failed: {e}")
        print(f"  HTML available at: {html_path}")
        return html_path  # Fallback to HTML


def build_resume(
    jd_text: str,
    company: str = "",
    llm: LLM = None,
    store: ResumeStore = None,
    generate_pdf: bool = True,
) -> str:
    """
    Top-level function: generate a tailored resume from JD text.
    Returns path to output file (HTML or PDF).
    """
    if store is None:
        store = ResumeStore.from_yaml("resume_store.yaml")
    if llm is None:
        llm = LLM(provider="openrouter")

    company_slug = company or "company"

    html_path = generate_resume_html(store, jd_text, llm, company_slug)

    if generate_pdf:
        return html_to_pdf(html_path)

    return html_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python resume_builder.py <jd_text_or_file> [company_name]")
        sys.exit(1)

    jd_input = sys.argv[1]
    company = sys.argv[2] if len(sys.argv) > 2 else ""

    # Read JD from file or use as text
    if os.path.isfile(jd_input):
        with open(jd_input, "r") as f:
            jd_text = f.read()
    else:
        jd_text = jd_input

    if not jd_text.strip():
        print("Error: empty JD text")
        sys.exit(1)

    print(f"Building resume for: {company or 'unknown company'}")
    result = build_resume(jd_text, company)
    print(f"\nDone: {result}")
