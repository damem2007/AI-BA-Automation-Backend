from pydantic import BaseModel
from typing import List

class TranscriptRequest(BaseModel):
     project_name: str
     transcript: str

class UserStory(BaseModel):
    role: str
    goal: str
    benefit: str
    story: str

class AcceptanceCriteria(BaseModel):
    user_story: str
    criteria: List[str]

class Requirement(BaseModel):
    id: str
    type: str
    description: str
    priority: str

class Risk(BaseModel):
    risk: str
    impact: str
    mitigation: str


class Dependency(BaseModel):
    dependency: str
    reason: str


class UATScenario(BaseModel):
    scenario: str
    steps: List[str]
    expected_result: str


class BAAnalysisOutput(BaseModel):
    business_summary: str
    user_stories: List[UserStory]
    acceptance_criteria: List[AcceptanceCriteria]
    functional_requirements: List[Requirement]
    assumptions: List[str]
    risks: List[Risk]
    dependencies: List[Dependency]
    open_questions: List[str]
    uat_scenarios: List[UATScenario]
