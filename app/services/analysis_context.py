from typing import Dict, List, Optional


BA_ACTIVITY_AREAS: List[Dict[str, object]] = [
    {
        "chapter": "Early-stage BA Activities",
        "items": [
            {
                "key": "discovery",
                "label": "Discovery",
                "techniques": ["Document Analysis", "Interviews", "Workshops", "Brainstorming"],
                "competencies": ["Analytical Thinking and Problem Solving", "Business Knowledge", "Communication Skills"],
                "outputs": ["discovery report", "problem statement", "context summary", "follow-up questions"],
                "notes": ["Reconstruct business context from fragmented source materials and identify what is still unknown."],
            },
            {
                "key": "stakeholder-analysis",
                "label": "Stakeholder Analysis",
                "techniques": ["Stakeholder List, Map, or Personas", "Interviews", "Workshops"],
                "competencies": ["Interaction Skills", "Communication Skills", "Business Knowledge"],
                "outputs": ["stakeholder map", "actor list", "RACI candidates", "engagement risks"],
                "notes": ["Detect missing operational, technical, approval, support, compliance, and impacted-user perspectives."],
            },
            {
                "key": "process-understanding",
                "label": "Process Understanding",
                "techniques": ["Process Analysis", "Process Modelling", "Observation", "Document Analysis"],
                "competencies": ["Analytical Thinking and Problem Solving", "Tools and Technology"],
                "outputs": ["current process summary", "process gaps", "exceptions", "handoff risks"],
                "notes": ["Detect workflow steps, actors, handoffs, business rules, bottlenecks, and exception paths."],
            },
            {
                "key": "problem-framing",
                "label": "Problem Framing",
                "techniques": ["Root Cause Analysis", "Business Capability Analysis", "Brainstorming"],
                "competencies": ["Analytical Thinking and Problem Solving", "Business Knowledge"],
                "outputs": ["problem statement", "root cause hypotheses", "impact summary", "decision framing"],
                "notes": ["Separate symptoms, root-cause hypotheses, constraints, business impacts, and solution assumptions."],
            },
            {
                "key": "needs-assessment",
                "label": "Needs Assessment",
                "techniques": ["Business Cases", "SWOT Analysis", "Benchmarking and Market Analysis", "Interviews"],
                "competencies": ["Business Knowledge", "Analytical Thinking and Problem Solving"],
                "outputs": ["needs assessment", "business drivers", "capability gaps", "value opportunities"],
                "notes": ["Link needs to stakeholders, business outcomes, constraints, and measurable value."],
            },
        ],
    },
    {
        "chapter": "Chapter 3: Business Analysis Planning and Monitoring",
        "items": [
            {
                "key": "plan-ba-approach",
                "label": "Plan Business Analysis Approach",
                "techniques": ["Brainstorming", "Interviews", "Workshops", "Estimation"],
                "competencies": ["Analytical Thinking and Problem Solving", "Communication Skills"],
                "outputs": ["BA approach", "analysis plan", "decision log"],
                "notes": ["Clarify governance, cadence, documentation standards, and stakeholder decision rights."],
            },
            {
                "key": "plan-stakeholder-engagement",
                "label": "Plan Stakeholder Engagement",
                "techniques": ["Stakeholder List, Map, or Personas", "Interviews", "Workshops"],
                "competencies": ["Interaction Skills", "Communication Skills"],
                "outputs": ["stakeholder map", "engagement plan", "communication plan"],
                "notes": ["Check for missing approvers, SMEs, impacted users, support teams, and external parties."],
            },
            {
                "key": "plan-ba-governance",
                "label": "Plan Business Analysis Governance",
                "techniques": ["Decision Analysis", "Item Tracking", "Reviews"],
                "competencies": ["Business Knowledge", "Tools and Technology"],
                "outputs": ["governance approach", "approval workflow", "change control notes"],
                "notes": ["Confirm who can approve requirements, scope changes, priorities, and exceptions."],
            },
            {
                "key": "plan-ba-information-management",
                "label": "Plan Business Analysis Information Management",
                "techniques": ["Document Analysis", "Glossary", "Data Dictionary"],
                "competencies": ["Tools and Technology", "Communication Skills"],
                "outputs": ["information management plan", "artifact inventory", "traceability approach"],
                "notes": ["Define where artifacts live, versioning expectations, and traceability needs."],
            },
        ],
    },
    {
        "chapter": "Chapter 4: Elicitation and Collaboration",
        "items": [
            {
                "key": "prepare-elicitation",
                "label": "Prepare for Elicitation",
                "techniques": ["Document Analysis", "Interviews", "Workshops", "Survey or Questionnaire"],
                "competencies": ["Communication Skills", "Interaction Skills"],
                "outputs": ["elicitation plan", "question bank", "source material review notes"],
                "notes": ["Use uploaded files to infer source context, assumptions, and information gaps."],
            },
            {
                "key": "conduct-elicitation",
                "label": "Conduct Elicitation",
                "techniques": ["Interviews", "Workshops", "Observation", "Focus Groups", "Prototyping"],
                "competencies": ["Interaction Skills", "Behavioural Characteristics"],
                "outputs": ["elicitation notes", "confirmed facts", "candidate requirements", "open questions"],
                "notes": ["Separate stakeholder statements from confirmed facts and unresolved ambiguity."],
            },
            {
                "key": "confirm-elicitation-results",
                "label": "Confirm Elicitation Results",
                "techniques": ["Reviews", "Workshops", "Item Tracking"],
                "competencies": ["Communication Skills", "Analytical Thinking and Problem Solving"],
                "outputs": ["validated findings", "issues list", "decision and action log"],
                "notes": ["Highlight statements that need validation, signoff, or reconciliation."],
            },
            {
                "key": "communicate-ba-information",
                "label": "Communicate Business Analysis Information",
                "techniques": ["Reviews", "Workshops", "Glossary", "Mind Mapping"],
                "competencies": ["Communication Skills", "Interaction Skills"],
                "outputs": ["stakeholder-ready summary", "communication notes", "review package"],
                "notes": ["Shape outputs for audience clarity, decision support, and shared understanding."],
            },
            {
                "key": "collaborate-with-stakeholders",
                "label": "Collaborate with Stakeholders",
                "techniques": ["Interviews", "Workshops", "Observation", "Brainstorming", "Document Analysis", "Focus Groups"],
                "competencies": ["Facilitation", "Analytical Thinking and Problem Solving", "Communication Skills", "Business Knowledge"],
                "outputs": ["collaboration summary", "stakeholder concerns", "decision log", "follow-up elicitation plan"],
                "notes": ["Evaluate stakeholder coverage, participation gaps, unresolved disagreements, and collaboration risks."],
            },
        ],
    },
    {
        "chapter": "Chapter 5: Requirements Life Cycle Management",
        "items": [
            {
                "key": "trace-requirements",
                "label": "Trace Requirements",
                "techniques": ["Item Tracking", "Reviews", "Scope Modelling"],
                "competencies": ["Tools and Technology", "Analytical Thinking and Problem Solving"],
                "outputs": ["traceability notes", "requirement lineage", "dependency map"],
                "notes": ["Identify relationships between business need, requirement, design, test, and release."],
            },
            {
                "key": "maintain-requirements",
                "label": "Maintain Requirements",
                "techniques": ["Backlog Management", "Item Tracking", "Prioritization"],
                "competencies": ["Tools and Technology", "Business Knowledge"],
                "outputs": ["maintained backlog", "requirement updates", "version notes"],
                "notes": ["Call out stale, duplicated, conflicting, or incomplete requirements."],
            },
            {
                "key": "prioritize-requirements",
                "label": "Prioritize Requirements",
                "techniques": ["Prioritization", "Decision Analysis", "Risk Analysis and Management"],
                "competencies": ["Analytical Thinking and Problem Solving", "Business Knowledge"],
                "outputs": ["prioritized requirement list", "MoSCoW notes", "priority rationale"],
                "notes": ["Use value, risk, urgency, dependency, compliance, and delivery sequencing."],
            },
            {
                "key": "assess-requirements-changes",
                "label": "Assess Requirements Changes",
                "techniques": ["Impact Analysis", "Risk Analysis and Management", "Decision Analysis"],
                "competencies": ["Analytical Thinking and Problem Solving", "Business Knowledge"],
                "outputs": ["change impact assessment", "risk notes", "decision recommendation"],
                "notes": ["Assess scope, stakeholder, data, integration, process, cost, and timeline impacts."],
            },
        ],
    },
    {
        "chapter": "Chapter 6: Strategy Analysis",
        "items": [
            {
                "key": "analyze-current-state",
                "label": "Analyze Current State",
                "techniques": ["Process Analysis", "SWOT Analysis", "Business Capability Analysis", "Benchmarking and Market Analysis"],
                "competencies": ["Business Knowledge", "Analytical Thinking and Problem Solving"],
                "outputs": ["current state analysis", "pain points", "capability gaps"],
                "notes": ["Separate current facts from symptoms, inferred causes, and desired outcomes."],
            },
            {
                "key": "define-future-state",
                "label": "Define Future State",
                "techniques": ["Business Capability Analysis", "Process Modelling", "Prototyping"],
                "competencies": ["Business Knowledge", "Communication Skills"],
                "outputs": ["future state summary", "target capabilities", "success measures"],
                "notes": ["Link desired outcomes to capabilities, stakeholders, and measurable value."],
            },
            {
                "key": "assess-risks",
                "label": "Assess Risks",
                "techniques": ["Risk Analysis and Management", "Decision Analysis", "Root Cause Analysis"],
                "competencies": ["Analytical Thinking and Problem Solving", "Business Knowledge"],
                "outputs": ["risk register", "mitigation plan", "risk recommendations"],
                "notes": ["Assess business, technical, adoption, compliance, data, and operational risks."],
            },
            {
                "key": "define-change-strategy",
                "label": "Define Change Strategy",
                "techniques": ["Business Cases", "Roadmap", "Stakeholder List, Map, or Personas"],
                "competencies": ["Communication Skills", "Interaction Skills"],
                "outputs": ["change strategy", "transition approach", "readiness notes"],
                "notes": ["Identify adoption, rollout, training, operational readiness, and transition needs."],
            },
        ],
    },
    {
        "chapter": "Chapter 7: Requirements Analysis and Design Definition",
        "items": [
            {
                "key": "specify-and-model-requirements",
                "label": "Specify and Model Requirements",
                "techniques": ["Data Modelling", "Process Modelling", "Use Cases and Scenarios", "User Stories"],
                "competencies": ["Analytical Thinking and Problem Solving", "Tools and Technology"],
                "outputs": ["functional requirements", "use cases", "user stories", "data mapping matrix"],
                "notes": ["Produce implementation-ready requirements only when supported by source material."],
            },
            {
                "key": "validate-requirements",
                "label": "Validate Requirements",
                "techniques": ["Acceptance and Evaluation Criteria", "Reviews", "Prototyping"],
                "competencies": ["Communication Skills", "Analytical Thinking and Problem Solving"],
                "outputs": ["validation notes", "acceptance criteria", "quality issues"],
                "notes": ["Check that requirements are clear, testable, feasible, aligned, and valuable."],
            },
            {
                "key": "define-requirements-architecture",
                "label": "Define Requirements Architecture",
                "techniques": ["Functional Decomposition", "Scope Modelling", "Data Flow Diagrams"],
                "competencies": ["Analytical Thinking and Problem Solving", "Tools and Technology"],
                "outputs": ["requirements architecture", "decomposition", "traceability structure"],
                "notes": ["Group requirements by capability, process, system boundary, data object, or release slice."],
            },
            {
                "key": "define-design-options",
                "label": "Define Design Options",
                "techniques": ["Decision Analysis", "Prototyping", "Vendor Assessment"],
                "competencies": ["Business Knowledge", "Analytical Thinking and Problem Solving"],
                "outputs": ["design options", "decision matrix", "tradeoff notes"],
                "notes": ["Compare options using value, risk, complexity, constraints, and stakeholder impact."],
            },
            {
                "key": "analyze-potential-value",
                "label": "Analyze Potential Value and Recommend Solution",
                "techniques": ["Financial Analysis", "Business Cases", "Metrics and KPIs"],
                "competencies": ["Business Knowledge", "Analytical Thinking and Problem Solving"],
                "outputs": ["value analysis", "recommendation notes", "benefit hypothesis"],
                "notes": ["Tie solution recommendations to measurable outcomes and open validation needs."],
            },
        ],
    },
]


BABOK_FOCUS_AREAS: List[Dict[str, object]] = [
    {
        "chapter": "Analysis Focus Presets",
        "items": [
            {
                "key": "infer",
                "label": "Let model infer",
                "guidance": "Infer the most relevant BABOK-aligned focus from the source materials.",
                "artifacts": [],
            },
            {
                "key": "technical-analysis",
                "label": "Technical Analysis",
                "guidance": (
                    "Emphasize implementation-facing analysis such as systems, data, "
                    "interfaces, integrations, access, controls, and technical constraints."
                ),
                "artifacts": [
                    "Data mapping matrix",
                    "Interface notes",
                    "Data dictionary candidates",
                    "Transformation rules",
                    "Roles and permissions matrix",
                    "Non-functional requirements",
                ],
            },
        ],
    },
    {
        "chapter": "Chapter 1: Introduction",
        "items": [
            {"key": "purpose-of-babok-guide", "label": "Purpose of the BABOK Guide"},
            {"key": "what-is-business-analysis", "label": "What is Business Analysis?"},
            {"key": "who-is-business-analyst", "label": "Who is a Business Analyst?"},
            {"key": "babok-guide-structure", "label": "Structure of the BABOK Guide"},
        ],
    },
    {
        "chapter": "Chapter 2: Business Analysis Key Concepts",
        "items": [
            {"key": "baccm", "label": "Business Analysis Core Concept Model"},
            {"key": "requirements-classification", "label": "Requirements Classification Schema"},
            {"key": "stakeholders", "label": "Stakeholders"},
            {"key": "requirements-and-designs", "label": "Requirements and Designs"},
        ],
    },
    {
        "chapter": "Chapter 3: Business Analysis Planning and Monitoring",
        "items": [
            {"key": "plan-ba-approach", "label": "Plan Business Analysis Approach"},
            {"key": "plan-stakeholder-engagement", "label": "Plan Stakeholder Engagement"},
            {"key": "plan-ba-governance", "label": "Plan Business Analysis Governance"},
            {"key": "plan-ba-information-management", "label": "Plan Business Analysis Information Management"},
            {"key": "identify-ba-performance-improvements", "label": "Identify Business Analysis Performance Improvements"},
        ],
    },
    {
        "chapter": "Chapter 4: Elicitation and Collaboration",
        "items": [
            {"key": "prepare-elicitation", "label": "Prepare for Elicitation"},
            {"key": "conduct-elicitation", "label": "Conduct Elicitation"},
            {"key": "confirm-elicitation-results", "label": "Confirm Elicitation Results"},
            {"key": "communicate-ba-information", "label": "Communicate Business Analysis Information"},
            {"key": "manage-stakeholder-collaboration", "label": "Manage Stakeholder Collaboration"},
        ],
    },
    {
        "chapter": "Chapter 5: Requirements Life Cycle Management",
        "items": [
            {"key": "assess-requirements-changes", "label": "Assess Requirements Changes"},
            {"key": "approve-requirements", "label": "Approve Requirements"},
        ],
    },
    {
        "chapter": "Chapter 6: Strategy Analysis",
        "items": [
            {"key": "analyze-current-state", "label": "Analyze Current State"},
            {"key": "define-future-state", "label": "Define Future State"},
            {"key": "assess-risks", "label": "Assess Risks"},
            {"key": "define-change-strategy", "label": "Define Change Strategy"},
        ],
    },
    {
        "chapter": "Chapter 7: Requirements Analysis and Design Definition",
        "items": [
            {"key": "specify-and-model-requirements", "label": "Specify and Model Requirements"},
            {"key": "validate-requirements", "label": "Validate Requirements"},
            {"key": "define-requirements-architecture", "label": "Define Requirements Architecture"},
            {"key": "define-design-options", "label": "Define Design Options"},
            {"key": "analyze-potential-value", "label": "Analyze Potential Value and Recommend Solution"},
        ],
    },
    {
        "chapter": "Chapter 8: Solution Evaluation",
        "items": [
            {"key": "measure-solution-performance", "label": "Measure Solution Performance"},
            {"key": "analyze-performance-measures", "label": "Analyze Performance Measures"},
            {"key": "assess-solution-limitations", "label": "Assess Solution Limitations"},
            {"key": "assess-enterprise-limitations", "label": "Assess Enterprise Limitations"},
            {"key": "recommend-actions-value", "label": "Recommend Actions to Increase Solution Value"},
        ],
    },
    {
        "chapter": "Chapter 9: Underlying Competencies",
        "items": [
            {"key": "analytical-thinking-problem-solving", "label": "Analytical Thinking and Problem Solving"},
            {"key": "behavioural-characteristics", "label": "Behavioural Characteristics"},
            {"key": "business-knowledge", "label": "Business Knowledge"},
            {"key": "communication-skills", "label": "Communication Skills"},
            {"key": "interaction-skills", "label": "Interaction Skills"},
            {"key": "tools-and-technology", "label": "Tools and Technology"},
        ],
    },
    {
        "chapter": "Chapter 10: Techniques",
        "items": [
            {"key": "acceptance-evaluation-criteria", "label": "Acceptance and Evaluation Criteria"},
            {"key": "backlog-management", "label": "Backlog Management"},
            {"key": "balanced-scorecard", "label": "Balanced Scorecard"},
            {"key": "benchmarking-market-analysis", "label": "Benchmarking and Market Analysis"},
            {"key": "brainstorming", "label": "Brainstorming"},
            {"key": "business-capability-analysis", "label": "Business Capability Analysis"},
            {"key": "business-cases", "label": "Business Cases"},
            {"key": "business-model-canvas", "label": "Business Model Canvas"},
            {"key": "business-rules-analysis", "label": "Business Rules Analysis"},
            {"key": "collaborative-games", "label": "Collaborative Games"},
            {"key": "concept-modelling", "label": "Concept Modelling"},
            {"key": "data-dictionary", "label": "Data Dictionary"},
            {"key": "data-flow-diagrams", "label": "Data Flow Diagrams"},
            {"key": "data-mining", "label": "Data Mining"},
            {"key": "data-modelling", "label": "Data Modelling"},
            {"key": "decision-analysis", "label": "Decision Analysis"},
            {"key": "decision-modelling", "label": "Decision Modelling"},
            {"key": "document-analysis", "label": "Document Analysis"},
            {"key": "estimation", "label": "Estimation"},
            {"key": "financial-analysis", "label": "Financial Analysis"},
            {"key": "focus-groups", "label": "Focus Groups"},
            {"key": "functional-decomposition", "label": "Functional Decomposition"},
            {"key": "glossary", "label": "Glossary"},
            {"key": "interface-analysis", "label": "Interface Analysis"},
            {"key": "interviews", "label": "Interviews"},
            {"key": "item-tracking", "label": "Item Tracking"},
            {"key": "lessons-learned", "label": "Lessons Learned"},
            {"key": "metrics-kpis", "label": "Metrics and KPIs"},
            {"key": "mind-mapping", "label": "Mind Mapping"},
            {"key": "non-functional-requirements", "label": "Non-Functional Requirements Analysis"},
            {"key": "observation", "label": "Observation"},
            {"key": "organizational-modelling", "label": "Organizational Modelling"},
            {"key": "prioritization", "label": "Prioritization"},
            {"key": "process-analysis", "label": "Process Analysis"},
            {"key": "process-modelling", "label": "Process Modelling"},
            {"key": "prototyping", "label": "Prototyping"},
            {"key": "reviews", "label": "Reviews"},
            {"key": "risk-analysis-management", "label": "Risk Analysis and Management"},
            {"key": "roles-permissions-matrix", "label": "Roles and Permissions Matrix"},
            {"key": "root-cause-analysis", "label": "Root Cause Analysis"},
            {"key": "scope-modelling", "label": "Scope Modelling"},
            {"key": "sequence-diagrams", "label": "Sequence Diagrams"},
            {"key": "stakeholder-map-personas", "label": "Stakeholder List, Map, or Personas"},
            {"key": "state-modelling", "label": "State Modelling"},
            {"key": "survey-questionnaire", "label": "Survey or Questionnaire"},
            {"key": "swot-analysis", "label": "SWOT Analysis"},
            {"key": "use-cases-scenarios", "label": "Use Cases and Scenarios"},
            {"key": "user-stories", "label": "User Stories"},
            {"key": "vendor-assessment", "label": "Vendor Assessment"},
            {"key": "workshops", "label": "Workshops"},
        ],
    },
    {
        "chapter": "Chapter 11: Perspectives",
        "items": [
            {"key": "agile-perspective", "label": "Agile Perspective"},
            {"key": "business-intelligence-perspective", "label": "Business Intelligence Perspective"},
            {"key": "information-technology-perspective", "label": "Information Technology Perspective"},
            {"key": "business-architecture-perspective", "label": "Business Architecture Perspective"},
            {"key": "business-process-management-perspective", "label": "Business Process Management Perspective"},
        ],
    },
]


TECHNICAL_FOCUS_KEYS = {
    "technical-analysis",
    "data-dictionary",
    "data-flow-diagrams",
    "data-modelling",
    "interface-analysis",
    "non-functional-requirements",
    "roles-permissions-matrix",
    "sequence-diagrams",
    "state-modelling",
    "information-technology-perspective",
}


def resolve_focus_area(
    focus_key: Optional[str],
    focus_chapter: Optional[str],
    focus_area: Optional[str],
) -> Optional[Dict[str, object]]:
    if not focus_key or focus_key == "infer":
        return None

    for group in BABOK_FOCUS_AREAS:
        for item in group["items"]:
            if item["key"] == focus_key:
                return {
                    "key": item["key"],
                    "chapter": group["chapter"],
                    "label": item["label"],
                    "guidance": item.get("guidance"),
                    "artifacts": item.get("artifacts", []),
                }

    if focus_area:
        return {
            "key": focus_key,
            "chapter": focus_chapter or "Custom BABOK Focus",
            "label": focus_area,
            "guidance": None,
            "artifacts": [],
        }

    return None


def build_focus_prompt(
    focus_key: Optional[str],
    focus_chapter: Optional[str],
    focus_area: Optional[str],
) -> str:
    resolved_focus = resolve_focus_area(focus_key, focus_chapter, focus_area)

    if resolved_focus is None:
        return """
    BABOK Focus Area: Infer the most relevant BABOK knowledge area, technique,
    or perspective from the source materials. If the elicitation exercise is unclear,
    state the likely focus as an assumption or open question."""

    artifact_list = resolved_focus.get("artifacts", [])
    artifact_instruction = ""
    if artifact_list:
        artifact_instruction = (
            "\n    Suggested focused artifacts: "
            + ", ".join(str(artifact) for artifact in artifact_list)
            + "."
        )

    technical_instruction = ""
    if resolved_focus["key"] in TECHNICAL_FOCUS_KEYS:
        technical_instruction = """
    For technical analysis, keep the Core Analysis separate from technical
    outputs. Fill data_mapping_matrix when source fields, target fields,
    transformations, rules, validations, or interface handoffs are supported
    by the source materials. Use focus_area_outputs for interface notes, data
    dictionary candidates, permission considerations, integration constraints,
    technical risks, and missing information. Do not fabricate fields."""

    return f"""
    BABOK Focus Chapter: {resolved_focus["chapter"]}
    BABOK Focus Area: {resolved_focus["label"]}

    Shape the analysis around this BABOK focus area while preserving the Core
    Analysis structure. Use focus_area_outputs for BABOK-aligned findings,
    models, decisions, artefacts, and follow-up work that belong outside the
    Core Analysis.{artifact_instruction}{technical_instruction}"""


def resolve_activity_recommendations(activity_keys: List[str]) -> Dict[str, object]:
    selected = []
    techniques = []
    competencies = []
    outputs = []
    notes = []

    for group in BA_ACTIVITY_AREAS:
        for item in group["items"]:
            if item["key"] in activity_keys:
                selected.append(
                    {
                        "key": item["key"],
                        "label": item["label"],
                        "chapter": group["chapter"],
                    }
                )
                techniques.extend(item.get("techniques", []))
                competencies.extend(item.get("competencies", []))
                outputs.extend(item.get("outputs", []))
                notes.extend(item.get("notes", []))

    if not selected:
        notes.append(
            "No activity selected. The model should infer the activity from the "
            "source materials and flag the assumption."
        )

    return {
        "selected_activities": selected,
        "related_techniques": unique_preserve_order(techniques),
        "core_competencies": unique_preserve_order(competencies),
        "suggested_outputs": unique_preserve_order(outputs),
        "recommendation_notes": unique_preserve_order(notes),
    }


def build_activity_prompt(
    activity_keys: List[str],
    selected_techniques: Optional[List[str]] = None,
    infer_additional_techniques: bool = True,
    selected_outputs: Optional[List[str]] = None,
) -> str:
    recommendations = resolve_activity_recommendations(activity_keys)
    selected_activities = recommendations["selected_activities"]
    output_instruction = (
        ", ".join(selected_outputs)
        if selected_outputs
        else "Infer the most useful outputs from the selected activities and source materials."
    )

    if selected_activities:
        activity_lines = "\n".join(
            f"    - {activity['chapter']}: {activity['label']}"
            for activity in selected_activities
        )
    else:
        activity_lines = "    - Infer activity from source materials."

    if selected_techniques:
        technique_instruction = f"""
    User-selected techniques:
    {", ".join(selected_techniques)}

    Apply the selected techniques where supported by the source materials."""
        if infer_additional_techniques:
            technique_instruction += """
    The AI may also infer and apply additional BABOK techniques when they improve
    analysis quality, coverage, or confidence. Explain notable added techniques
    in ai_recommendation_notes."""
        else:
            technique_instruction += """
    Do not add other techniques unless a source-material gap makes that necessary;
    if so, explain the exception in ai_recommendation_notes."""
    else:
        technique_instruction = """
    No user-selected techniques were provided. Infer and apply the most
    appropriate BABOK techniques from the selected activities and source
    materials."""

    return f"""
    Selected BABOK activities or source context:
{activity_lines}

    Cascaded techniques from the selected activities:
    {", ".join(recommendations["related_techniques"]) or "Infer from source materials."}
{technique_instruction}

    Relevant competencies:
    {", ".join(recommendations["core_competencies"]) or "Infer from source materials."}

    Output preference:
    {output_instruction}

    Add AI recommendation notes for missing inputs, recommended next BA
    activity, suggested validation steps, OCR/transcription needs, and any
    technique that should be used next.

    Generate confidence scores between 0 and 1 for inferred semantic insights
    and contradictions. Lower confidence when evidence comes from filenames,
    partial extraction, binary source metadata, or incomplete source coverage."""


def build_orchestration_context(
    domain: Optional[str],
    activity_keys: Optional[List[str]],
    selected_techniques: Optional[List[str]],
    infer_additional_techniques: bool,
    selected_outputs: Optional[List[str]],
    allow_ai_inference: bool,
    source_material_types: Optional[List[str]],
    project_type: str,
    strategic_analysis_enabled: bool = False,
    source_intent: str = "unknown",
    source_subtype: Optional[str] = None,
) -> Dict[str, object]:
    # Normalize UI selections into the canonical orchestration block used by the prompt.
    recommendations = resolve_activity_recommendations(activity_keys or [])
    selected_activities = recommendations["selected_activities"]
    selected_technique_set = set(selected_techniques or [])
    selected_chapters = unique_preserve_order(
        [str(activity["chapter"]) for activity in selected_activities]
    )
    inferred_notes = []

    if not selected_activities and allow_ai_inference:
        inferred_notes.append(
            "No BABOK activity was selected in the UI; infer likely activities from source materials and mark them as inferred."
        )
    if not selected_techniques and infer_additional_techniques:
        inferred_notes.append(
            "No techniques were selected in the UI; infer appropriate techniques from selected/inferred activities and source evidence."
        )
    if not selected_outputs and allow_ai_inference:
        inferred_notes.append(
            "No output preference was selected; infer output views from orchestration context and source maturity."
        )

    cascaded_techniques = recommendations["related_techniques"]
    effective_techniques = unique_preserve_order(
        [technique for technique in cascaded_techniques if technique in selected_technique_set]
        if selected_technique_set
        else []
    )

    return {
        "business_domain": domain or "infer",
        "babok_activities": [
            str(activity["label"]) for activity in selected_activities
        ],
        "babok_chapters": selected_chapters,
        "selected_techniques": effective_techniques,
        "core_competencies": recommendations["core_competencies"],
        "output_preferences": selected_outputs or [],
        "allow_ai_inference": allow_ai_inference,
        "allow_ai_technique_expansion": infer_additional_techniques,
        "source_material_types": unique_preserve_order(source_material_types or []),
        "strategic_analysis_enabled": project_type == "external"
        or strategic_analysis_enabled,
        "inference_notes": inferred_notes,
        "source_intent": source_intent,
        "source_subtype": source_subtype or "",
    }


def unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


## Further analysis to make the orchestration smarter.
SOURCE_INTENT_RULES = """
Source intent controls how the source material should be interpreted.

Do not automatically convert candidate qualifications, staffing conditions,
procurement clauses, rate limits, resumes, capability summaries, eligibility
rules, contract terms, or recruiter feedback into system/product requirements.

Classify them into engagement_context where appropriate:
- staffing_context
- eligibility_constraints
- capability_evidence
- procurement_constraints
- engagement_conditions

Only create requirements when the source explicitly describes a business need,
system behavior, operating process, compliance need, reporting need, integration,
data need, stakeholder need, or delivery outcome.

BABOK activities are analysis lenses. They do not override source intent.
For example, if source_intent is procurement and source_subtype is statement_of_work,
Discovery and Process Understanding should analyze the SOW context, scope,
constraints, process references, and delivery expectations. They should not
turn candidate qualifications into product requirements.
"""


def build_source_intent_prompt(
    source_intent: str = "unknown",
    source_subtype: Optional[str] = None,
) -> str:
    return f"""
Source interpretation:
- source_intent: {source_intent}
- source_subtype: {source_subtype or "not provided"}

{SOURCE_INTENT_RULES}
"""