import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from collections import Counter
from resume_models import ResumeStore

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "need",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "also",
    "about",
    "above",
    "after",
    "again",
    "against",
    "below",
    "between",
    "during",
    "before",
    "behind",
    "into",
    "through",
    "under",
    "up",
    "down",
    "out",
    "off",
    "over",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "we",
    "our",
    "you",
    "your",
    "they",
    "their",
    "them",
    "he",
    "she",
    "his",
    "her",
    "who",
    "which",
    "what",
    "where",
    "when",
    "why",
    "how",
    "able",
    "get",
    "use",
    "using",
    "used",
    "work",
    "working",
    "new",
    "including",
}


def extract_keywords(jd_text: str, top_n: int = 20) -> list:
    """
    Extract top N keywords from the job description text.
    """

    text = jd_text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    words = text.split()
    bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
    # bigrams is a list of adj word pairs like "data science", "machine learning" etc.

    word_counts = Counter(w for w in words if w not in STOPWORDS and len(w) > 2)

    bigram_counts = Counter(
        b for b in bigrams if all(w not in STOPWORDS for w in b.split())
    )
    # bigram_counts is a counter of how many times each bigram appears in the text, excluding those with stopwords
    # example with a stopword is "data science" appears 5 times, but "data and science" appears 3 times, then bigram_counts["data science"] = 5, but bigram_counts["data and science"] is not counted because it contains the stopword "and"\

    top_words = [w for w, _ in word_counts.most_common(top_n)]
    top_bigrams = [b for b, _ in bigram_counts.most_common(top_n // 2)]

    return top_words + top_bigrams


def score_by_tags(store: ResumeStore, jd_keywords: list) -> dict:
    """
    Score each experience and project by how many tags match JD keywords.
    Returns sorted scores for AI to decide what to include.
    """

    kw_set = set(kw.lower() for kw in jd_keywords)

    def match_count(tags):
        return sum(1 for t in tags if t.lower() in kw_set)

    results = {
        "experiences": [],
        "projects": [],
    }
    for job in store.work_experience:
        score = match_count(job.tags)
        bullet_scores = [match_count(b.tags) for b in job.bullets]
        results["experiences"].append(
            {
                "title": f"{job.role} @ {job.company}",
                "score": score,
                "bullet_scores": bullet_scores,
                "total_bullets": len(job.bullets),
            }
        )
    for proj in store.projects:
        score = match_count(proj.tags)
        results["projects"].append(
            {
                "title": proj.name,
                "score": score,
            }
        )
    results["experiences"].sort(key=lambda x: -x["score"])
    results["projects"].sort(key=lambda x: -x["score"])
    return results


def keyword_match_summary(jd_text: str, store: ResumeStore) -> dict:
    """
    Full pipeline: extract keywords, score resume pieces, return results.
    """
    keywords = extract_keywords(jd_text)
    scores = score_by_tags(store, keywords)
    return {
        "keywords": keywords[:10],
        "scores": scores,
    }
