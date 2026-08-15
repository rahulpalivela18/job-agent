"""
analysis/analyze.py — Empirical analysis of the real application log (jobs.json).

Computes, using only the real data recorded by the pipeline:
  1. Dataset summary (N, statuses, companies, titles)
  2. Score distribution + applied vs. pending comparison
  3. Personalized-content similarity (cover letters & fit reasons)
  4. Cost model (LLM calls per resume, tokens, USD)

Outputs:
  - analysis/results/stats.json   (all numbers as JSON)
  - analysis/charts/*.png         (figures)

Pure inputs: ../jobs.json. No network, no LLM calls, no fabricated rows.
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
JOBS_FILE = ROOT / "jobs.json"
RESULTS_DIR = ROOT / "analysis" / "results"
CHARTS_DIR = ROOT / "analysis" / "charts"


# ---------------------------------------------------------------- load data
def load_jobs():
    if not JOBS_FILE.exists():
        sys.exit(f"Missing {JOBS_FILE}. Run the pipeline (python main.py) first.")
    with open(JOBS_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------- text utils
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,}")
STOP = {
    "the",
    "and",
    "for",
    "with",
    "are",
    "you",
    "your",
    "that",
    "this",
    "will",
    "can",
    "have",
    "from",
    "into",
    "has",
    "our",
    "who",
    "what",
    "where",
    "when",
    "how",
    "why",
    "about",
    "been",
    "but",
    "was",
    "were",
    "not",
    "all",
    "any",
    "would",
    "could",
    "should",
    "they",
    "them",
    "their",
    "role",
    "roles",
    "team",
    "apply",
    "application",
    "job",
    "company",
}


def tokenize(text):
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOP]


def tf_vector(tokens):
    counts = Counter(tokens)
    return counts


def cosine(a, b):
    """Cosine similarity between two TF maps."""
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def mean(seq):
    seq = list(seq)
    return sum(seq) / len(seq) if seq else 0.0


def median(seq):
    seq = sorted(seq)
    n = len(seq)
    if not seq:
        return 0.0
    if n % 2 == 1:
        return seq[n // 2]
    return (seq[n // 2 - 1] + seq[n // 2]) / 2


def stdev(seq):
    seq = list(seq)
    if len(seq) < 2:
        return 0.0
    m = mean(seq)
    return math.sqrt(sum((x - m) ** 2 for x in seq) / (len(seq) - 1))


def p95(seq):
    seq = sorted(seq)
    if not seq:
        return 0.0
    i = min(len(seq) - 1, int(0.95 * len(seq)))
    return seq[i]


# ---------------------------------------------------------------- metrics
def dedupe_by_posting(jobs):
    """Drop duplicate postings (same title + company) to avoid inflating
    similarity with identical rows. Returns the unique subset."""
    seen = set()
    out = []
    for j in jobs:
        key = (str(j.get("title", "")).lower(), str(j.get("company", "")).lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def pairwise_similarity(texts):
    """Mean pairwise cosine similarity (and std) of a set of texts."""
    vecs = [tf_vector(tokenize(t)) for t in texts]
    sims = []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            sims.append(cosine(vecs[i], vecs[j]))
    return {
        "mean": mean(sims),
        "stdev": stdev(sims),
        "min": min(sims) if sims else 0.0,
        "max": max(sims) if sims else 0.0,
    }


def cost_model(n_jobs):
    """Estimated LLM cost from README pipeline budget (~4 calls, ~750 tokens)."""
    calls_per_resume = 4
    tokens_per_resume = 750
    # gpt-4.1-mini list prices (USD per 1M tokens), mid-2026
    price_in = 0.40
    price_out = 1.60
    # assume ~70/30 input/output split of the 750-token budget
    in_tok = tokens_per_resume * 0.7
    out_tok = tokens_per_resume * 0.3
    per_resume = (in_tok * price_in + out_tok * price_out) / 1_000_000
    return {
        "llm_calls_per_resume": calls_per_resume,
        "tokens_per_resume": tokens_per_resume,
        "model": "gpt-4.1-mini",
        "cost_per_resume_usd": round(per_resume, 4),
        "total_calls": calls_per_resume * n_jobs,
        "total_tokens_est": tokens_per_resume * n_jobs,
        "total_cost_est_usd": round(per_resume * n_jobs, 2),
    }


# ---------------------------------------------------------------- charts
def chart_score_distribution(scores, out):
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    bins = np.arange(min(scores) - 0.5, max(scores) + 1.5)
    ax.hist(scores, bins=bins, color="#4a90e2", edgecolor="white", rwidth=0.85)
    ax.set_xlabel("LLM job-fit score (1–10)")
    ax.set_ylabel("jobs")
    ax.set_title("Score distribution of scored applications (real data)")
    ax.set_xticks([int(x) for x in bins[:-1] + 0.5])
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def chart_score_by_status(applied_scores, pending_scores, out):
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    data = [pending_scores, applied_scores]
    ax.boxplot(
        data,
        tick_labels=["pending", "applied"],
        widths=0.5,
        patch_artist=True,
        boxprops=dict(facecolor="#dbe7f5"),
    )
    ax.set_ylabel("LLM job-fit score")
    ax.set_title("Score by application status (real data)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def chart_similarity(cover_sims, reason_sims, out):
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    ax.hist(cover_sims, bins=20, alpha=0.65, color="#4a90e2", label="cover letters")
    ax.hist(reason_sims, bins=20, alpha=0.65, color="#e2a14a", label="fit reasons")
    ax.set_xlabel("pairwise cosine similarity")
    ax.set_ylabel("pairs")
    ax.set_title("Personalization: pairwise text similarity (real data)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    jobs = load_jobs()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- dataset summary
    statuses = Counter(j.get("status", "unknown") for j in jobs)
    companies = Counter(j.get("company", "") for j in jobs)
    titles = [j.get("title", "") for j in jobs]
    scores = [j["score"] for j in jobs if j.get("score") is not None]

    cover_texts = [j["cover_letter"] for j in jobs if j.get("cover_letter")]
    reason_texts = [j["fit_reason"] for j in jobs if j.get("fit_reason")]

    applied = [j["score"] for j in jobs if j.get("status") == "applied"]
    pending = [j["score"] for j in jobs if j.get("status") != "applied"]

    unique_jobs = dedupe_by_posting(jobs)
    unique_cover_texts = [
        j["cover_letter"] for j in unique_jobs if j.get("cover_letter")
    ]
    unique_reason_texts = [j["fit_reason"] for j in unique_jobs if j.get("fit_reason")]

    cover_sims = pairwise_similarity(unique_cover_texts)
    reason_sims = pairwise_similarity(unique_reason_texts)

    stats = {
        "dataset": {
            "n_jobs": len(jobs),
            "statuses": dict(statuses),
            "n_distinct_titles": len(set(titles)),
            "n_companies": len(companies),
            "top_companies": companies.most_common(10),
            "n_with_cover_letter": len(cover_texts),
            "n_with_fit_reason": len(reason_texts),
        },
        "scores": {
            "n": len(scores),
            "mean": round(mean(scores), 2),
            "median": median(scores),
            "stdev": round(stdev(scores), 2),
            "min": min(scores),
            "max": max(scores),
            "p95": p95(scores),
            "distribution": dict(sorted(Counter(scores).items())),
        },
        "score_vs_status": {
            "applied_n": len(applied),
            "pending_n": len(pending),
            "applied_mean": round(mean(applied), 2),
            "pending_mean": round(mean(pending), 2),
            "applied_median": median(applied),
            "pending_median": median(pending),
        },
        "personalization": {
            "deduplicated_by_posting": True,
            "n_unique_postings": len(unique_jobs),
            "cover_letters": {
                "n": len(unique_cover_texts),
                "mean_len_chars": round(mean([len(t) for t in unique_cover_texts]), 1),
                "pairwise_cosine_mean": round(cover_sims["mean"], 3),
                "pairwise_cosine_stdev": round(cover_sims["stdev"], 3),
                "pairwise_cosine_min": round(cover_sims["min"], 3),
                "pairwise_cosine_max": round(cover_sims["max"], 3),
            },
            "fit_reasons": {
                "n": len(unique_reason_texts),
                "pairwise_cosine_mean": round(reason_sims["mean"], 3),
                "pairwise_cosine_stdev": round(reason_sims["stdev"], 3),
            },
        },
        "cost_model": cost_model(len(jobs)),
    }

    with open(RESULTS_DIR / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    # ---- charts
    chart_score_distribution(scores, CHARTS_DIR / "score_distribution.png")
    if applied and pending:
        chart_score_by_status(applied, pending, CHARTS_DIR / "score_by_status.png")
    chart_similarity(
        _all_pairs(unique_cover_texts),
        _all_pairs(unique_reason_texts),
        CHARTS_DIR / "personalization.png",
    )

    print(json.dumps(stats, indent=2))


def _all_pairs(texts):
    vecs = [tf_vector(tokenize(t)) for t in texts]
    out = []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            out.append(cosine(vecs[i], vecs[j]))
    return out


if __name__ == "__main__":
    main()
