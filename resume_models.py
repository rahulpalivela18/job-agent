from pydantic import BaseModel
from typing import List, Optional
import yaml


class PersonalInfo(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    github: str = ""
    linkedin: str = ""
    website: str = ""


class Bullet(BaseModel):
    text: str
    tags: List[str] = []


class JobExperience(BaseModel):
    company: str
    role: str
    period: str
    bullets: List[Bullet]
    tags: List[str] = []
    priority: str = "medium"


class Project(BaseModel):
    name: str
    bullets: List[Bullet]
    tags: List[str] = []
    link: str = ""
    priority: str = "medium"


class Education(BaseModel):
    degree: str
    school: str
    gpa: Optional[str] = None
    period: Optional[str] = None
    coursework: List[str] = []


class SkillCategory(BaseModel):
    category: str
    skills: List[str]


class ResumeStore(BaseModel):
    """Model for storing information of the resume"""

    personal: PersonalInfo
    summary: str
    work_experience: List[JobExperience]
    projects: List[Project]
    education: List[Education]
    skills: List[SkillCategory]

    @classmethod
    def from_yaml(cls, path: str) -> "ResumeStore":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: str) -> None:
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)

    def to_yaml_string(self) -> str:
        return yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False)

    def to_text(self) -> str:
        lines = []

        p = self.personal
        contact = f"Email: [{p.email}] | Phone: [{p.phone}] | GitHub: [{p.github}] | LinkedIn: [{p.linkedin}]"
        lines.append(p.name)
        lines.append(p.location)
        lines.append(contact)

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("### SUMMARY")
        lines.append("")
        lines.append(self.summary)

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("### SKILLS")
        lines.append("")
        for cat in self.skills:
            lines.append(f"**{cat.category}:** {', '.join(cat.skills)}")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("### WORK EXPERIENCE")
        lines.append("")
        for job in self.work_experience:
            lines.append(f"**{job.role} — {job.company}**")
            lines.append(job.period)
            lines.append("")
            for b in job.bullets:
                lines.append(f"* {b.text}")
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append("### PROJECTS")
        lines.append("")
        for proj in self.projects:
            lines.append(f"**{proj.name}**")
            if proj.link:
                lines.append(f"Link: {proj.link}")
            lines.append("")
            for b in proj.bullets:
                lines.append(f"* {b.text}")
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append("### EDUCATION")
        lines.append("")
        for edu in self.education:
            lines.append(f"**{edu.degree} — {edu.school}**")
            if edu.gpa:
                lines.append(f"GPA: {edu.gpa}")
            lines.append("")
            if edu.coursework:
                lines.append("### COURSEWORK")
                lines.append("")
                lines.append(", ".join(edu.coursework))

        return "\n".join(lines).strip()
