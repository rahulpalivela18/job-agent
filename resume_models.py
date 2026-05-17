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
