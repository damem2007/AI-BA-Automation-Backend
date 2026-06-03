from pydantic import BaseModel, Field
from typing import List, Literal, Optional

## Further analysis to make the orchestration smarter.
SourceIntent = Literal[
    "elicitation",
    "governance",
    "delivery",
    "procurement",
    "staffing",
    "compliance",
    "architecture",
    "operations",
    "reference",
    "analytical",
    "unknown",
]

class SourceFileInput(BaseModel):
     name: str
     type: Optional[str] = None
     size: Optional[int] = None
     content_base64: Optional[str] = None


class TranscriptRequest(BaseModel):
     project_name: str
     transcript: str = ""
     source_text: Optional[str] = None
     project_type: Literal["internal", "external"] = "internal"
     company_name: Optional[str] = None
     industry: Optional[str] = None
     domain: Optional[str] = None
     initiative_type: Optional[str] = None
     analysis_focus_key: Optional[str] = None
     analysis_focus_chapter: Optional[str] = None
     analysis_focus_area: Optional[str] = None
     selected_activity_keys: Optional[List[str]] = None
     selected_activity_labels: Optional[List[str]] = None
     selected_techniques: Optional[List[str]] = None
     allow_ai_inference: bool = True
     infer_additional_techniques: bool = True
     selected_outputs: Optional[List[str]] = None
     source_files: Optional[List[SourceFileInput]] = None
     strategic_analysis_enabled: bool = False
     country: Optional[str] = None
     source_intent: SourceIntent = "unknown"
     source_subtype: Optional[str] = None


class RefinementRequest(BaseModel):
     # Refinement runs reuse the latest saved canonical model, then apply a new BA activity lens.
     selected_activity_keys: Optional[List[str]] = None
     selected_activity_labels: Optional[List[str]] = None
     selected_techniques: Optional[List[str]] = None
     include_previous_activities: bool = False
     allow_ai_inference: bool = True
     infer_additional_techniques: bool = True
     selected_outputs: Optional[List[str]] = None
     source_files: Optional[List[SourceFileInput]] = None
     refinement_output_mode: Literal["aggregated", "phase_only"] = "aggregated"
     current_version_id: Optional[int] = None

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


class DataMappingRow(BaseModel):
    source: str
    target: str
    transformation: str
    rule: str
    notes: str


class FocusAreaOutput(BaseModel):
    title: str
    description: str
    items: List[str]


class AIRecommendationNote(BaseModel):
    note: str
    rationale: str
    next_step: str


class SemanticInsight(BaseModel):
    insight: str
    evidence: str
    confidence: float


class Contradiction(BaseModel):
    issue: str
    evidence: List[str]
    recommendation: str
    confidence: float


class SWOTAnalysis(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    threats: List[str] = Field(default_factory=list)


class PESTELAnalysis(BaseModel):
    political: List[str] = Field(default_factory=list)
    economic: List[str] = Field(default_factory=list)
    social: List[str] = Field(default_factory=list)
    technological: List[str] = Field(default_factory=list)
    environmental: List[str] = Field(default_factory=list)
    legal: List[str] = Field(default_factory=list)


class BACCMAnalysis(BaseModel):
    change: List[str] = Field(default_factory=list)
    need: List[str] = Field(default_factory=list)
    solution: List[str] = Field(default_factory=list)
    stakeholder: List[str] = Field(default_factory=list)
    value: List[str] = Field(default_factory=list)
    context: List[str] = Field(default_factory=list)


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
    focus_area_outputs: Optional[List[FocusAreaOutput]] = None
    data_mapping_matrix: Optional[List[DataMappingRow]] = None
    ai_recommendation_notes: Optional[List[AIRecommendationNote]] = None
    semantic_insights: Optional[List[SemanticInsight]] = None
    contradictions: Optional[List[Contradiction]] = None


class ExternalBAAnalysisOutput(BAAnalysisOutput):
    swot_analysis: SWOTAnalysis
    pestel_analysis: PESTELAnalysis
    baccm_analysis: BACCMAnalysis


# CBAKF models below are the semantic source of truth; output views are derived.
class ProjectMetadata(BaseModel):
    project_name: str = ""
    project_type: Literal["internal", "external"] = "internal"
    industry: str = ""
    organization: str = ""
    country: str = ""
    domain: str = ""
    initiative_type: str = ""
    created_at: str = ""
    analysis_version: str = "CBAKF-1.0"


class AnalysisOrchestration(BaseModel):
    business_domain: str = ""
    selected_activity_keys: List[str] = Field(default_factory=list)
    selected_activity_labels: List[str] = Field(default_factory=list)
    babok_activities: List[str] = Field(default_factory=list)
    babok_chapters: List[str] = Field(default_factory=list)
    selected_techniques: List[str] = Field(default_factory=list)
    core_competencies: List[str] = Field(default_factory=list)
    output_preferences: List[str] = Field(default_factory=list)
    allow_ai_inference: bool = True
    allow_ai_technique_expansion: bool = True
    source_material_types: List[str] = Field(default_factory=list)
    strategic_analysis_enabled: bool = False
    inference_notes: List[str] = Field(default_factory=list)
    # These fields make BABOK phase progression explicit without changing the canonical output model.
    refinement_phase: int = 1
    activity_run_history: List["ActivityRun"] = Field(default_factory=list)
    rerun_warnings: List[str] = Field(default_factory=list)


class ActivityRun(BaseModel):
    phase: int = 1
    version_id: Optional[int] = None
    previous_version_id: Optional[int] = None
    selected_activity_keys: List[str] = Field(default_factory=list)
    selected_activities: List[str] = Field(default_factory=list)
    rerun_activity_keys: List[str] = Field(default_factory=list)
    rerun_activities: List[str] = Field(default_factory=list)
    selected_techniques: List[str] = Field(default_factory=list)
    created_at: str = ""
    note: str = ""


class MetadataItem(BaseModel):
    key: str = ""
    value: str = ""


class SourceMaterial(BaseModel):
    type: str = ""
    name: str = ""
    metadata: List[MetadataItem] = Field(default_factory=list)
    source_reference: str = ""


class SourceContext(BaseModel):
    source_intent: SourceIntent = "unknown"
    source_subtype: Optional[str] = None
    source_materials: List[SourceMaterial] = Field(default_factory=list)
    participants: List["SemanticEntity"] = Field(default_factory=list)
    sessions: List["SemanticEntity"] = Field(default_factory=list)
    attachments: List[SourceMaterial] = Field(default_factory=list)
    timestamps: List["SemanticEntity"] = Field(default_factory=list)
    follow_up_actions: List["SemanticEntity"] = Field(default_factory=list)


class SemanticEntity(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    source_reference: str = ""
    confidence: float = 0
    related_entities: List[str] = Field(default_factory=list)
    metadata: List[MetadataItem] = Field(default_factory=list)


class SemanticRequirement(BaseModel):
    id: str = ""
    description: str = ""
    priority: str = ""
    source_reference: str = ""
    confidence: float = 0
    related_entities: List[str] = Field(default_factory=list)
    metadata: List[MetadataItem] = Field(default_factory=list)


class SemanticRequirements(BaseModel):
    functional: List[SemanticRequirement] = Field(default_factory=list)
    non_functional: List[SemanticRequirement] = Field(default_factory=list)
    integration: List[SemanticRequirement] = Field(default_factory=list)
    security: List[SemanticRequirement] = Field(default_factory=list)
    reporting: List[SemanticRequirement] = Field(default_factory=list)
    data: List[SemanticRequirement] = Field(default_factory=list)
    usability: List[SemanticRequirement] = Field(default_factory=list)
    compliance: List[SemanticRequirement] = Field(default_factory=list)


class ActionPoint(BaseModel):
    id: str = ""
    description: str = ""
    owner: str = ""
    due_date: str = ""
    status: Literal["open", "in_progress", "completed", "blocked"] = "open"
    source_reference: str = ""
    priority: str = ""
    related_entities: List[str] = Field(default_factory=list)


class SemanticModel(BaseModel):
    stakeholders: List[SemanticEntity] = Field(default_factory=list)
    business_objectives: List[SemanticEntity] = Field(default_factory=list)
    pain_points: List[SemanticEntity] = Field(default_factory=list)
    capabilities: List[SemanticEntity] = Field(default_factory=list)
    requirements: SemanticRequirements = Field(default_factory=SemanticRequirements)
    constraints: List[SemanticEntity] = Field(default_factory=list)
    risks: List[SemanticEntity] = Field(default_factory=list)
    assumptions: List[SemanticEntity] = Field(default_factory=list)
    dependencies: List[SemanticEntity] = Field(default_factory=list)
    integrations: List[SemanticEntity] = Field(default_factory=list)
    business_rules: List[SemanticEntity] = Field(default_factory=list)
    processes: List[SemanticEntity] = Field(default_factory=list)
    data_entities: List[SemanticEntity] = Field(default_factory=list)
    decisions: List[SemanticEntity] = Field(default_factory=list)
    open_questions: List[SemanticEntity] = Field(default_factory=list)
    action_points: List[ActionPoint] = Field(default_factory=list)
    # Recommendations remain semantic guidance, not document-only notes.
    recommendations: List[SemanticEntity] = Field(default_factory=list)
    timelines: List[SemanticEntity] = Field(default_factory=list)
    priorities: List[SemanticEntity] = Field(default_factory=list)
    success_metrics: List[SemanticEntity] = Field(default_factory=list)


class StrategicAnalysis(BaseModel):
    swot: SWOTAnalysis = Field(default_factory=SWOTAnalysis)
    pestel: PESTELAnalysis = Field(default_factory=PESTELAnalysis)
    baccm: BACCMAnalysis = Field(default_factory=BACCMAnalysis)
    market_context: SemanticEntity = Field(default_factory=SemanticEntity)
    competitive_factors: List[SemanticEntity] = Field(default_factory=list)
    change_impact: SemanticEntity = Field(default_factory=SemanticEntity)
    value_assessment: SemanticEntity = Field(default_factory=SemanticEntity)


class DeliveryAnalysis(BaseModel):
    epics: List[SemanticEntity] = Field(default_factory=list)
    features: List[SemanticEntity] = Field(default_factory=list)
    user_stories: List[UserStory] = Field(default_factory=list)
    acceptance_criteria: List[AcceptanceCriteria] = Field(default_factory=list)
    uat_scenarios: List[UATScenario] = Field(default_factory=list)
    implementation_phases: List[SemanticEntity] = Field(default_factory=list)
    release_recommendations: List[SemanticEntity] = Field(default_factory=list)
    rollout_constraints: List[SemanticEntity] = Field(default_factory=list)
    change_management: List[SemanticEntity] = Field(default_factory=list)


class GovernanceAnalysis(BaseModel):
    regulatory_requirements: List[SemanticEntity] = Field(default_factory=list)
    audit_considerations: List[SemanticEntity] = Field(default_factory=list)
    reporting_obligations: List[SemanticEntity] = Field(default_factory=list)
    data_residency: List[SemanticEntity] = Field(default_factory=list)
    security_model: SemanticEntity = Field(default_factory=SemanticEntity)
    approval_requirements: List[SemanticEntity] = Field(default_factory=list)
    compliance_constraints: List[SemanticEntity] = Field(default_factory=list)


class OutputView(BaseModel):
    title: str = ""
    summary: str = ""
    sections: List[FocusAreaOutput] = Field(default_factory=list)


class OutputViews(BaseModel):
    executive_summary: OutputView = Field(default_factory=OutputView)
    brd: OutputView = Field(default_factory=OutputView)
    functional_specification: OutputView = Field(default_factory=OutputView)
    roadmap: OutputView = Field(default_factory=OutputView)
    stakeholder_summary: OutputView = Field(default_factory=OutputView)
    jira_export: OutputView = Field(default_factory=OutputView)
    uat_pack: OutputView = Field(default_factory=OutputView)

## Further analysis to make the orchestration smarter.
class EngagementEntity(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    source_reference: str = ""
    confidence: float = 0
    related_entities: list[str] = Field(default_factory=list)
    metadata: list[MetadataItem] = Field(default_factory=list)

class EngagementContext(BaseModel):
    staffing_context: list[EngagementEntity] = Field(default_factory=list)
    eligibility_constraints: list[EngagementEntity] = Field(default_factory=list)
    capability_evidence: list[EngagementEntity] = Field(default_factory=list)
    procurement_constraints: list[EngagementEntity] = Field(default_factory=list)
    engagement_conditions: list[EngagementEntity] = Field(default_factory=list)

class CBAKFAnalysisOutput(BaseModel):
    artifact_id: str = ""
    project_metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    analysis_orchestration: AnalysisOrchestration = Field(
        default_factory=AnalysisOrchestration
    )
    source_context: SourceContext = Field(default_factory=SourceContext)
    semantic_model: SemanticModel = Field(default_factory=SemanticModel)
    strategic_analysis: StrategicAnalysis = Field(default_factory=StrategicAnalysis)
    delivery_analysis: DeliveryAnalysis = Field(default_factory=DeliveryAnalysis)
    governance_analysis: GovernanceAnalysis = Field(default_factory=GovernanceAnalysis)
    output_views: OutputViews = Field(default_factory=OutputViews)
    engagement_context: EngagementContext = Field(default_factory=EngagementContext)
