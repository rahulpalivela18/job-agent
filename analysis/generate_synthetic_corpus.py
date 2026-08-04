"""
analysis/generate_synthetic_corpus.py

Generates a clearly-labeled SYNTHETIC corpus of job descriptions to
stress-test the pipeline's deterministic keyword/tag scoring on a larger,
controlled input set.

IMPORTANT: These postings are fabricated for benchmarking only. Every record
is tagged {"synthetic": true} so results based on it are never conflated
with the real application log in analysis/results.

Usage:
  python analysis/generate_synthetic_corpus.py [N] [seed]
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "synthetic_jds.json"

COMPANIES = [
    "Nimbus Labs",
    "Crestline AI",
    "Fathom Analytics",
    "Vantage Systems",
    "Orbital Dynamics",
    "Kindred Health",
    "Stackhouse",
    "Meridian Data",
    "PolarGrid",
    "Cobalt Robotics",
    "Lumenware",
    "Axis One",
]

ROLES = [
    "Software Engineer",
    "Backend Engineer",
    "AI Engineer",
    "Machine Learning Engineer",
    "Full Stack Engineer",
    "Data Engineer",
    "Platform Engineer",
    "DevOps Engineer",
    "Site Reliability Engineer",
    "Data Scientist",
]

SENIORITY = [
    "Software Engineer",
    "Software Engineer I",
    "Software Engineer II",
    "Backend Engineer",
    "Machine Learning Engineer",
]

SKILLS = {
    "Software Engineer": ["Python", "Java", "SQL", "REST APIs", "Microservices"],
    "Backend Engineer": ["Python", "Go", "PostgreSQL", "Kafka", "Distributed Systems"],
    "AI Engineer": ["Python", "LLMs", "PyTorch", "RAG", "Vector Databases"],
    "Machine Learning Engineer": [
        "Python",
        "PyTorch",
        "scikit-learn",
        "Feature Engineering",
        "MLOps",
    ],
    "Full Stack Engineer": ["React", "TypeScript", "Node.js", "PostgreSQL", "AWS"],
    "Data Engineer": ["Python", "Spark", "Airflow", "Snowflake", "ETL"],
    "Platform Engineer": ["Kubernetes", "Terraform", "CI/CD", "Go", "AWS"],
    "DevOps Engineer": ["Docker", "Kubernetes", "Terraform", "GitHub Actions", "AWS"],
    "Site Reliability Engineer": [
        "Kubernetes",
        "Grafana",
        "Prometheus",
        "SLOs",
        "Incident Response",
    ],
    "Data Scientist": [
        "Python",
        "Pandas",
        "SQL",
        "Statistical Modeling",
        "A/B Testing",
    ],
}

RESPONSIBILITIES = {
    "Software Engineer": [
        "Design, build, and ship production-grade backend services.",
        "Collaborate with product and design to deliver features end to end.",
        "Write clean, tested, maintainable code with code reviews.",
        "Diagnose and fix production issues with on-call rotations.",
    ],
    "Backend Engineer": [
        "Build and scale distributed systems serving millions of requests.",
        "Design APIs and event-driven data pipelines.",
        "Optimize database queries and system latency.",
        "Own services from design through monitoring and on-call.",
    ],
    "AI Engineer": [
        "Develop LLM-powered features including retrieval-augmented generation.",
        "Evaluate and fine-tune models for quality and cost.",
        "Build evaluation pipelines and guardrails for model output.",
        "Integrate LLM APIs with product surfaces.",
    ],
    "Machine Learning Engineer": [
        "Train and evaluate models on large-scale datasets.",
        "Own the ML lifecycle from experimentation to production deployment.",
        "Build feature stores and automated retraining pipelines.",
        "Monitor model drift and quality in production.",
    ],
    "Full Stack Engineer": [
        "Ship features across React frontend and Node.js backend.",
        "Design data models and REST/GraphQL APIs.",
        "Improve performance, accessibility, and test coverage.",
        "Work closely with product, design, and infra teams.",
    ],
    "Data Engineer": [
        "Build and maintain scalable ETL/ELT data pipelines.",
        "Model warehouse tables and ensure data quality.",
        "Orchestrate workflows with Airflow.",
        "Optimize query performance across large datasets.",
    ],
    "Platform Engineer": [
        "Maintain Kubernetes-based infrastructure and tooling.",
        "Automate deployments with Terraform and CI/CD pipelines.",
        "Reduce developer friction with internal developer platform.",
        "Improve observability and incident response.",
    ],
    "DevOps Engineer": [
        "Automate build, test, and deployment pipelines.",
        "Manage cloud infrastructure as code with Terraform.",
        "Harden security and monitoring for production systems.",
        "Support developer tooling and release processes.",
    ],
    "Site Reliability Engineer": [
        "Own reliability, SLOs, and incident response for core services.",
        "Build monitoring, alerting, and capacity planning.",
        "Drive postmortems and reliability improvements.",
        "Automate operational toil.",
    ],
    "Data Scientist": [
        "Analyze user behavior and product data to guide decisions.",
        "Design and analyze A/B tests.",
        "Build and validate statistical and ML models.",
        "Communicate findings to product and engineering teams.",
    ],
}


def make_jd(rng: random.Random, role: str, i: int) -> dict:
    company = rng.choice(COMPANIES)
    title = f"{role} — {company}"
    skills = SKILLS[role]
    duties = RESPONSIBILITIES[role]

    exp_phrase = rng.choice(
        ["0-2 years", "1-3 years", "2-4 years", "0-1 years", "1-2 years"]
    )

    body = f"""
{role} at {company}

About the role
We are looking for a {role.lower()} to join our team building products used by millions.
This is an early-career role. Candidates should have {exp_phrase} of relevant experience.

What you will do
{chr(10).join("- " + d for d in duties)}

What we are looking for
- Experience with {", ".join(skills[:3])}
- Familiarity with {", ".join(skills[3:])}
- Strong problem-solving and communication skills
- A collaborative, product-minded approach

Nice to have
- Experience with cloud platforms and CI/CD
- Prior internship or project experience
- Interest in reliability, quality, and testing

Our stack: {", ".join(skills)}.
"""
    return {
        "id": f"synth-{i:04d}",
        "title": title.lower(),
        "company": company,
        "role_family": role,
        "url": f"https://synthetic.example/{i}",
        "description": body.strip(),
        "synthetic": True,
    }


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    rng = random.Random(seed)

    corpus = []
    for i in range(n):
        role = rng.choice(ROLES)
        corpus.append(make_jd(rng, role, i))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(corpus, f, indent=1)

    from collections import Counter

    by_role = Counter(j["role_family"] for j in corpus)
    print(f"Wrote {len(corpus)} synthetic JDs -> {OUT}")
    print("By role family:", dict(by_role))
    print("All records tagged synthetic=True")


if __name__ == "__main__":
    main()
