import os
from dotenv import load_dotenv
from openai import OpenAI
import json
from huggingface_hub import InferenceClient
import re


load_dotenv()


class LLM:
    def __init__(self, provider="openai", model=None):
        self.provider = provider
        self.model = model

        if provider == "openai":
            self.model = model or "gpt-4.1-mini"
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        elif provider == "hf":
            self.model = model or "openai/gpt-oss-120b"
            self.client = InferenceClient(
                model=self.model, token=os.getenv("HF_API_KEY")
            )

    def _safe_json(self, text):
        """
        Safely parse JSON from the model's response, with error handling.
        """
        try:
            return json.loads(text)
        except:
            # try extracting JSON block
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return None

    def generate_application(self, resume, job):
        """
        Generate a tailored job application based on the resume and job description.
        """

        prompt = self._build_prompt(resume, job)

        response = self._call_model(prompt)

        data = self._safe_json(response)

        if data:
            return data

        return {"error": response}

    def _build_prompt(self, resume, job):
        """
        Build the prompt for the LLM based on the resume and job description.
        """

        return f"""
You are a job application assistant.

My Resume:
{resume}

Job:
Title: {job["title"]}
Company: {job["company"]}
Description: {job["description"][:800]}

Return ONLY valid JSON.
Do NOT explain anything.
Do NOT add extra text.
Do NOT wrap in markdown.

Format:
{{
  "cover_letter": "3-4 lines max",
  "fit_reason": "2-3 lines max"
}}
"""

    def _call_openai(self, prompt, max_tokens=800):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    def _call_hf(self, prompt, max_tokens=800):
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens
        )
        return response.choices[0].message.content

    def _call_model(self, prompt, max_tokens=800):
        if self.provider == "openai":
            return self._call_openai(prompt, max_tokens)
        elif self.provider == "hf":
            return self._call_hf(prompt, max_tokens)
        else:
            return "Unsupported provider"

    def score_job(self, resume, job):
        """
        Score how well the resume matches the job description.
        """

        prompt = f"""
You are evaluating job fit.

My resume:
{resume}

Candidate experience level: Early Career (0-1 years)

Prefer:
- backend / AI / software roles
- 0-2 years experience

Penalize:
- senior/staff roles
- non-engineering roles

Job:
Title: {job["title"]}
Company: {job["company"]}
Description: {job["description"][:800]}

Return ONLY valid JSON in this format:
{{ "score": number }}
Do NOT explain anything.

Example:
{{ "score": 8 }}

"""

        response = self._call_model(prompt)
        data = self._safe_json(response)

        if data and "score" in data:
            try:
                return int(data["score"])
            except:
                pass

        # fallback → extract number
        match = re.search(r"\d+", response or "")
        if match:
            return int(match.group())

        return 0

    def suggest_resume_improvements(self, resume, job):
        prompt = f"""
You are a career assistant.

Given the resume and job description, suggest how to improve the resume for THIS specific job.

My Resume:
{resume}

Job:
Title: {job["title"]}
Company: {job["company"]}
Description: {job["description"][:800]}

Return ONLY valid JSON:

{{
  "highlight": ["what to emphasize"],
  "add": ["what to add if possible"],
  "remove": ["what to reduce or remove"],
  "rewrite_suggestions": ["specific bullet rewrites"]
}}
"""

        response = self._call_model(prompt, max_tokens=500)

        data = self._safe_json(response)

        if data:
            return data

        return {"error": response}

    def tailor_summary(self, summary: str, jd_text: str) -> str:
        """
        Tailor the resume summary to better fit the job description.
        """

        prompt = f"""
Rewrite this professional summary to include 2-3 keywords from the job description.
Keep it concise — 1-2 sentences max. Do NOT invent experience you don't have.
Current Summary: {summary}
Job Description: {jd_text[:800]}
Return ONLY the rewritten summary. No explanation, no JSON.
"""
        return self._call_model(prompt, max_tokens=500).strip()

    def reorder_bullets(self, bullets: list, jd_text: str) -> list:
        """
        Given a list of bullet strings, return them reordered with
        most JD-relevant bullets first.
        """
        prompt = f"""
Reorder these resume bullets so the most relevant to the job description comes FIRST.
Return them as a numbered list. Keep ALL bullets — just reorder.
Bullets:
{chr(10).join(f"{i + 1}. {b}" for i, b in enumerate(bullets))}
Job Description: {jd_text[:600]}
Return ONLY the reordered numbered list.
"""
        response = self._call_model(prompt, max_tokens=500)
        # Parse numbered list back into list of strings
        result = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit() and ". " in line[:4]:
                result.append(line.split(". ", 1)[1])
        return result if result else bullets  # Fallback

    def select_projects(
        self, projects: list, jd_text: str, max_projects: int = 3
    ) -> list:
        """
        Given list of project dicts, return top {max_projects} most relevant.
        """
        prompt = f"""
I have these projects. Pick the top {max_projects} most relevant to the job description.
Return their indices (1-based) in order of relevance.
Projects:
{chr(10).join(f"{i + 1}. {p["name"]}: {" ".join(p["bullets"][:2])}" for i, p in enumerate(projects))}
Job Description: {jd_text[:800]}
Return ONLY the indices as a comma-separated list. Example: 3,1,2
"""
        response = self._call_model(prompt, max_tokens=500).strip()
        try:
            indices = [
                int(x.strip()) - 1 for x in response.split(",") if x.strip().isdigit()
            ]
            return [projects[i] for i in indices if 0 <= i < len(projects)][
                :max_projects
            ]
        except:
            return projects[:max_projects]  # Fallback

    def extract_competencies(self, skills_categories: list, jd_text: str) -> list:
        """
        Extract 6-8 competency keywords from JD, mapped to resume skills.
        """
        all_skills = []
        for cat in skills_categories:
            all_skills.extend(
                cat.skills if isinstance(cat.skills, list) else [cat.skills]
            )
        prompt = f"""
From this job description, extract 6-8 competency keywords that match the candidate's skills.
Return them as a comma-separated list.
Candidate skills available: {", ".join(all_skills)}
Job Description: {jd_text[:800]}
Return ONLY the comma-separated list. Example: Python, LLMs, React, PostgreSQL, DevOps
"""
        response = self._call_model(prompt, max_tokens=500).strip()
        return [s.strip() for s in response.split(",") if s.strip()][:8]
