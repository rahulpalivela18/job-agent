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


def is_senior_role(jd_text: str) -> bool:
    """
    Call llm to check if the JD is for a senior role or not
    """

    llm = LLM()

    min_yoe_val = "less than 3 years of experience"  # change to your recommended val

    prompt = f"""
Given the following job description, determine if this role is for a position that requires {min_yoe_val} or not. Return only "yes" if it is else return "No".

Job Description: 
{jd_text}
    """

    response = llm.call(prompt)

    return not (response.strip().lower() == "yes")
