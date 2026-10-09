"""
analysis/synthetic_benchmark.py

Runs the pipeline's DETERMINISTIC keyword extractor
(scraping.jd_processing.extract_keywords) over the clearly-labeled synthetic
corpus and measures how well it recovers the *known* required skills that were
embedded in each generated posting.

Because the corpus is synthetic, every JD has ground-truth skills (the SKILLS
tables in generate_synthetic_corpus.py), so we can measure an information-
retrieval-style metric without any human labels:

  - skill recall: fraction of a JD's known required skills that appear in the
    extracted top-N keywords (1-gram or 2-gram match)

This is a real measurement of system behavior on synthetic inputs. Results are
written to analysis/results/synthetic_benchmark.json, separate from the real
application log.

Usage: python analysis/synthetic_benchmark.py [n_max]
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraping.jd_processing import extract_keywords  # noqa: E402

CORPUS = ROOT / "data" / "synthetic_jds.json"
RESULTS = ROOT / "analysis" / "results"


def skill_recall(description: str, required_skills: list) -> float:
    """Fraction of required skills found in extracted keywords (1- or 2-gram)."""
    kws = set(extract_keywords(description))
    if not required_skills:
        return 1.0
    hits = 0
    for skill in required_skills:
        s = skill.lower()
        if s in kws or any(s in k for k in kws):
            hits += 1
    return hits / len(required_skills)


def main():
    n_max = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
    corpus = json.load(open(CORPUS))
    corpus = [j for j in corpus if j.get("synthetic")][:n_max]
    assert len(corpus) > 0, (
        "Empty synthetic corpus — run generate_synthetic_corpus.py first"
    )

    print(f"Benchmarking {len(corpus)} synthetic JDs (all tagged synthetic=True)")

    # Reconstruct ground-truth skills from the generator's SKILLS table.
    sys.path.insert(0, str(ROOT / "analysis"))
    from generate_synthetic_corpus import SKILLS  # noqa: E402

    recalls = []
    kw_counts = []
    bigram_shares = []
    by_family = Counter()
    by_role_recall = {}

    t0 = time.time()
    for j in corpus:
        required = SKILLS[j["role_family"]]
        rec = skill_recall(j["description"], required)
        recalls.append(rec)
        kws = extract_keywords(j["description"])
        kw_counts.append(len(kws))
        bigram_shares.append(sum(1 for k in kws if " " in k) / max(1, len(kws)))
        by_family[j["role_family"]] += 1
        by_role_recall.setdefault(j["role_family"], []).append(rec)

    elapsed = time.time() - t0

    per_role = {
        role: {"n": len(rs), "skill_recall_mean": round(sum(rs) / len(rs), 3)}
        for role, rs in sorted(by_role_recall.items())
    }

    stats = {
        "n_synthetic_jds": len(corpus),
        "role_family_distribution": dict(by_family),
        "keywords_per_jd": {
            "mean": round(sum(kw_counts) / len(kw_counts), 2),
            "min": min(kw_counts),
            "max": max(kw_counts),
        },
        "bigram_share_mean": round(sum(bigram_shares) / len(bigram_shares), 3),
        "skill_recall": {
            "mean": round(sum(recalls) / len(recalls), 3),
            "min": round(min(recalls), 3),
            "max": round(max(recalls), 3),
            "perfect_jds": sum(1 for r in recalls if r == 1.0),
        },
        "skill_recall_by_role_family": per_role,
        "runtime_seconds": round(elapsed, 3),
        "note": "Synthetic corpus — system behavior measurement on fabricated inputs.",
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "synthetic_benchmark.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
