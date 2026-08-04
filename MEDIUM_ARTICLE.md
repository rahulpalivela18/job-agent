# Medium Article Draft — publish-ready

> **Title:** I Automated My Job Applications With LLMs. Then I Studied Whether It Actually Worked.
>
> **Subtitle:** An empirical case study of an LLM-powered job-search pipeline — scoring, personalization, and what 140 LLM calls for $0.02 taught me about applied AI systems.
>
> **Suggested tags:** Machine Learning, Artificial Intelligence, Software Engineering, LLMs, Job Search

---

## TL;DR

I built a system that scrapes job boards, scores each posting against my resume with an LLM, and writes tailored cover letters and resumes. Then I treated it like a research artifact and measured it:

- **Scores are a coarse filter, not a ranker.** Mean 8.06/10, and 49% of postings scored a 9. Applied vs. pending scores were statistically indistinguishable (8.11 vs 8.00).
- **Cover letters are moderately personalized, not boilerplate.** Mean pairwise similarity 0.34 (deduplicated) — real per-job differences, same skeleton.
- **The free, deterministic parts do the heavy lifting.** A simple keyword extractor recovers required skills with **94% recall**, and the entire LLM pipeline cost ≈ **$0.02** for 35 applications.

Code and full report: [github.com/rahulpalivela18/job-agent](https://github.com/rahulpalivela18/job-agent) (branch `research-analysis`).

---

## The Problem

Applying to software jobs is a high-volume, low-differentiation task. The candidate fills essentially identical forms and writes near-identical materials for dozens of postings. This makes it a natural target for LLM automation — and, from a systems standpoint, a fascinating test case: **where do learned components actually add value on top of deterministic ones?**

Most "LLM does my job search" posts end at *"look how cool the automation is."* This one goes a step further: I studied the outputs like a dataset and asked whether the intelligent parts are doing real work.

## The System

The pipeline (open-sourced) has four stages:

1. **Acquisition** — auto-scrape Greenhouse, Lever, and Ashby boards for a target role.
2. **Filtering** — skip already-applied jobs, skip senior roles, then LLM-score each posting 1–10 and keep only ≥ 6.
3. **Tailoring** — extract JD keywords for free, LLM-rewrite the resume summary, reorder bullets, render a single-page PDF.
4. **Application** — LLM writes a cover letter + "why fit" blurb, record gets saved.

The design is deliberately asymmetric in cost: keyword/tag matching is free string comparison; everything intelligent costs LLM calls (≈4 per resume, ≈750 tokens).

## The Research Questions

- **RQ1 — Scoring validity:** Is the 1–10 fit score discriminative? Does it relate to what I actually applied to?
- **RQ2 — Personalization:** Are generated cover letters tailored per job, or templated?
- **RQ3 — Free path & cost:** How well does the deterministic keyword extractor recover required skills, and what does the whole thing cost?

## Methodology (in brief)

- **Real data:** 35 scored postings from the live system — 19 applied, 16 pending — each with cover letter, fit reason, score, status.
- **Synthetic benchmark:** 150 clearly-labeled fabricated postings (`synthetic: True`) across 10 role families, each embedding 5 known required skills — so I could measure extractor recall against ground truth.
- **Personalization metric:** mean pairwise TF-IDF cosine similarity over generated texts, on the deduplicated set of postings.

Everything is reproducible offline: `analysis/analyze.py`, `analysis/synthetic_benchmark.py`.

## Results

### 1. The score is a filter, not a ranker

Scores span 6–9 with a heavy ceiling effect — 17 of 35 (49%) scored 9:

![Score distribution](analysis/charts/score_distribution.png)

| Group | n | Mean | Median |
|---|---|---|---|
| applied | 19 | 8.11 | 9 |
| pending | 16 | 8.00 | 8 |

![Score by status](analysis/charts/score_by_status.png)

The score is great at screening out bad matches at the ≥6 gate — but above the gate it carries almost no signal. This makes sense: an LLM optimizer rarely wants to say "no" to a job you already filtered into relevance.

### 2. Personalization is real, but shallow

Deduplicating the log (35 → 31 unique postings) — an important step, since identical duplicate rows inflate similarity to 1.0:

| Generated text | Mean pairwise cosine | Max |
|---|---|---|
| Cover letters | **0.34** | 0.72 |
| Fit reasons | **0.21** | — |

![Personalization](analysis/charts/personalization.png)

Cover letters share a template skeleton (~34% similarity) but are clearly distinct per posting (max 0.72, not 1.0). Fit reasons are much more distinct. Verdict: distinguishable, job-specific, but visibly same-structure.

### 3. The cheap parts do the heavy lifting

On the 150 synthetic postings: the deterministic keyword extractor recovers required skills with **94% mean recall** (105/150 perfect), at **0.26 ms per posting**. The misses are two-word skills mangled by punctuation ("A/B Testing", "ETL").

**Cost:** 140 LLM calls, ~26,250 tokens, ≈ **$0.02 total** for all 35 applications. LLM cost is simply not a constraint for this class of automation.

## Discussion

Three takeaways:

1. **Use LLMs as gates, not oracles.** For decisions where you can afford to be permissive, an LLM score with a low-cost screening role beats trying to make it a precise ranker.
2. **Measure personalization, don't assume it.** "Tailored" is a claim; pairwise similarity is a number. Most systems would fail this test harder than mine did.
3. **Evaluation hygiene matters.** A naive similarity computation on my raw log reported a max of 1.0 — caused purely by duplicate rows. Self-reported system analyses are full of traps like this.

## Limitations

- Small real dataset (n = 35), single candidate, single model (gpt-4.1-mini).
- No outcome data — I can't yet say whether score or personalization correlates with callbacks.
- Synthetic corpus is generated text; real postings have more lexical diversity.
- Cost is an estimate from the documented token budget, not logged token counts.

## Future Work

- Log actual tokens to replace cost estimates.
- Collect application outcomes (interview/callback) and test whether score/personalization predict success.
- Re-scrape JD text and compare LLM scoring vs. deterministic tag matching on the real corpus.
- Ablate prompts to see how much personalization is prompt-driven.

## Why This Matters (for applicants and builders)

I did this as an MS CS applicant with no formal research lab experience. The lesson: **research artifacts don't require a lab or an IEEE paper.** A working system, real data, a clear question, an honest metric, and a reproducible writeup is a legitimate research contribution — and it's reproducible by anyone, which most "research" in this space isn't.

The code, raw results, and figures are all in the repo.

---

*Rahul Palivela — [github.com/rahulpalivela18](https://github.com/rahulpalivela18)*
