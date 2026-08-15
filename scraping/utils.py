import re
from llm import LLM


def min_yoe_required(jd_text: str) -> int:
    """
    Extract the minimum years of experience required from a JD.
    Returns 0 if no YOE requirement found.
    Uses regex to find
    """
    text = jd_text.lower()
    # Range first: "3-5 years" → min=3
    range_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)", text)
    if range_match:
        return int(range_match.group(1))
    # Single: "3+ years", "minimum 3 years", "at least 3 years", "3 years of experience"
    single = re.search(
        r"(?:(\d+)\+?|minimum\s+(\d+)|at\s+least\s+(\d+))\s*(?:years?|yrs?)\s*(?:of\s+)?(?:professional\s+)?(?:related\s+)?(?:work\s+)?(?:industry\s+)?experience",
        text,
    )
    if single:
        for g in single.groups():
            if g:
                return int(g)
    return 0


def is_senior_role(jd_text: str, llm=None) -> bool:
    """Check if a JD is for a senior role — regex first, LLM fallback."""

    yoe = min_yoe_required(jd_text)
    if yoe >= 3:
        return True

    if yoe > 0:
        return False

    if llm is None:
        llm = LLM()

    experience = 2.5

    prompt = f"""Given the job description below, return only "yes" if it requires {experience}+ years of experience, otherwise "no".
Job Description: {jd_text[:1500]}"""

    response = llm.call(prompt, max_tokens=10)
    return response.strip().lower() == "yes"
