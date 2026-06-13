from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone
import json
import os
from typing import Optional
from app.schemas.analysis import CBAKFAnalysisOutput, StrategicAnalysis
from app.services.analysis_context import (
    build_activity_prompt,
    build_focus_prompt,
    build_orchestration_context,
    build_source_intent_prompt,
)
from app.services.source_materials import build_source_bundle, build_source_context

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=api_key)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4-mini")

def analyze_transcript(
    project_name: str,
    source_text: str,
    project_type: str = "internal",
    company_name: Optional[str] = None,
    industry: Optional[str] = None,
    domain: Optional[str] = None,
    initiative_type: Optional[str] = None,
    analysis_focus_key: Optional[str] = None,
    analysis_focus_chapter: Optional[str] = None,
    analysis_focus_area: Optional[str] = None,
    selected_activity_keys: Optional[list[str]] = None,
    selected_techniques: Optional[list[str]] = None,
    allow_ai_inference: bool = True,
    infer_additional_techniques: bool = True,
    selected_outputs: Optional[list[str]] = None,
    source_files: Optional[list[dict]] = None,
    strategic_analysis_enabled: bool = False,
    country: Optional[str] = None,
    source_intent: str = "unknown",
    source_subtype: Optional[str] = None,
    prior_analysis: Optional[dict] = None,
    refinement_instruction: Optional[str] = None,
) -> CBAKFAnalysisOutput:
   # Build canonical context before prompting so UI orchestration drives analysis.
   source_bundle = build_source_bundle(source_text, source_files)
   source_context = build_source_context(source_text, source_files, source_intent=source_intent,
    source_subtype=source_subtype,)
   source_material_types = [
       str(item.get("type"))
       for item in source_context["source_materials"]
       if item.get("type")
   ]
   orchestration_context = build_orchestration_context(
       domain=domain,
       activity_keys=selected_activity_keys,
       selected_techniques=selected_techniques,
       infer_additional_techniques=infer_additional_techniques,
       selected_outputs=selected_outputs,
       allow_ai_inference=allow_ai_inference,
       source_material_types=source_material_types,
       project_type=project_type,
       strategic_analysis_enabled=strategic_analysis_enabled,
       source_intent=source_intent,
      source_subtype=source_subtype,
   )
   project_metadata = {
       "project_name": project_name,
       "project_type": project_type,
       "industry": industry or "",
       "organization": company_name or "",
       "country": country or "",
       "domain": domain or "",
       "initiative_type": initiative_type or "",
       "created_at": datetime.now(timezone.utc).isoformat(),
       "analysis_version": "CBAKF-1.0",
   }
   context_prompt = build_context_prompt(
       project_metadata=project_metadata,
       orchestration_context=orchestration_context,
       source_context=source_context,
       project_type=project_type,
       company_name=company_name,
       industry=industry,
       domain=domain,
       initiative_type=initiative_type,
       analysis_focus_key=analysis_focus_key,
       analysis_focus_chapter=analysis_focus_chapter,
       analysis_focus_area=analysis_focus_area,
       selected_activity_keys=selected_activity_keys,
       selected_techniques=selected_techniques,
       allow_ai_inference=allow_ai_inference,
       infer_additional_techniques=infer_additional_techniques,
       selected_outputs=selected_outputs,
       strategic_analysis_enabled=strategic_analysis_enabled,
       country=country,
       source_intent=source_intent,
       source_subtype=source_subtype,
       prior_analysis=prior_analysis,
       refinement_instruction=refinement_instruction,
   )

   prior_context = ""
   if prior_analysis:
       # Refinement must build on the current canonical model rather than starting from a blank analysis.
       prior_context = (
           "\n\nCurrent saved canonical analysis to refine:\n"
           f"{json.dumps(prior_analysis, indent=2, default=str)}"
       )
   full_prompt = f"{context_prompt}{prior_context}\n\n{source_bundle}".strip()

   completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
             "role": "system",
             "content": """
                You are a senior enterprise Business Analyst operating inside
                a BABOK-aware Business Analysis Semantic Intelligence Platform.

                Treat every transcript, note, document, diagram, audio file,
                image, spreadsheet, and binary upload as source material.
                Do not assume transcript-only input and do not behave like a
                generic summarizer.

                Your output must be the Canonical Business Analysis Knowledge
                Framework (CBAKF): semantic entities, relationships, contextual
                metadata, analysis orchestration settings, and generated views.
                Output views are rendered perspectives, not the source of truth.

                The frontend orchestration context is authoritative. Use the
                selected project metadata, BABOK activities, cascaded/user
                selected techniques, inference toggles, output preferences,
                source material metadata, and strategic context to dynamically
                shape analysis depth and structure.

                Reason across source materials to reconstruct business context,
                workflows, semantic entities, relationships, business rules,
                actors, pain points, capabilities, needs, constraints,
                assumptions, contradictions, missing information, and confidence
                levels.

                Use the BABOK Guide v3 as contextual reference material, not as
                a restrictive or rigid checklist. Adapt BABOK concepts to the
                source materials, selected activity, selected techniques,
                domain, delivery context, evidence quality, and confidence
                level.

                Extract only evidence-supported information. Separate confirmed
                facts from assumptions. Do not invent missing requirements,
                fields, stakeholders, integrations, or process steps.

                Normalize entities, classify requirements correctly, avoid
                duplicate requirements, preserve source truth, and keep action
                points separate from decisions, open questions, tasks, and
                follow-ups.

                Populate semantic_model.recommendations with evidence-supported
                BA guidance, suggested next activities, weak coverage warnings,
                validation needs, and follow-up analysis recommendations.

                Every populated output must be detailed enough for a Business
                Analyst to use in delivery work. Descriptions should include
                what was found, why it matters, supporting evidence or source
                reference, delivery implication, and confidence. Requirements
                must be categorized across functional, non-functional,
                integration, security, reporting, data, usability, and
                compliance when evidence supports those distinctions. Do not
                leave delivery_analysis, governance_analysis, semantic_model,
                recommendations, or output_views thin when the source material
                supports richer BA artifacts.

                Keep integration requirement outputs distinct from integration
                system/interface objects. Use semantic_model.requirements.integration
                for integration requirements and prefer ids like REQ-INT-001.
                Use semantic_model.integrations for systems, applications,
                interfaces, APIs, handoffs, data exchanges, or external service
                objects and prefer ids like SYS-INT-001. Do not mix these two
                concepts.

                If orchestration selections are empty and AI inference is
                allowed, infer BABOK activities, techniques, competencies, and
                outputs from the evidence. Flag all inferred mappings in
                analysis_orchestration.inference_notes.

                Strategic analysis must only be populated when project_type is
                external or strategic_analysis_enabled is true. Otherwise keep
                strategic_analysis empty.
                """
            },
            {
              "role": "user",
              "content": f"Analyze these business analysis source materials:\n\n{full_prompt}"
            }
        ],
        response_format=CBAKFAnalysisOutput,
   )
   if not completion.choices:
       raise ValueError("OpenAI API returned no completion choices")
   
   message = completion.choices[0].message
   if message.parsed is None:
       # Model failed to parse into schema; log error details
       raise ValueError(
           f"Failed to parse response into CBAKFAnalysisOutput. "
           f"Raw content: {message.content}"
       )
   
   analysis = message.parsed
   # Re-apply UI/source truth because the model may enrich, but not redefine, orchestration.
   return enforce_orchestration_source_of_truth(
       analysis,
       project_metadata=project_metadata,
       orchestration_context=orchestration_context,
       source_context=source_context,
   )


def build_context_prompt(
    project_metadata: dict,
    orchestration_context: dict,
    source_context: dict,
    project_type: str,
    company_name: Optional[str],
    industry: Optional[str],
    domain: Optional[str],
    initiative_type: Optional[str],
    analysis_focus_key: Optional[str],
    analysis_focus_chapter: Optional[str],
    analysis_focus_area: Optional[str],
    selected_activity_keys: Optional[list[str]],
    selected_techniques: Optional[list[str]],
    allow_ai_inference: bool,
    infer_additional_techniques: bool,
    selected_outputs: Optional[list[str]],
    strategic_analysis_enabled: bool,
    country: Optional[str],
    source_intent: str = "unknown",
    source_subtype: Optional[str] = None,
    prior_analysis: Optional[dict] = None,
    refinement_instruction: Optional[str] = None,
) -> str:
    domain_context = domain or "Infer the business domain from the source materials and project context."
    country_context = f"\n    Country/Region: {country}" if country else ""
    focus_context = build_focus_prompt(
        focus_key=analysis_focus_key,
        focus_chapter=analysis_focus_chapter,
        focus_area=analysis_focus_area,
    )
    source_intent_context = build_source_intent_prompt(
    source_intent=source_intent,
    source_subtype=source_subtype,
    )
    activity_context = build_activity_prompt(
        activity_keys=selected_activity_keys or [],
        selected_techniques=selected_techniques,
        infer_additional_techniques=infer_additional_techniques,
        selected_outputs=selected_outputs,
    )
    orchestration_json = json.dumps(orchestration_context, indent=2, default=str)
    metadata_json = json.dumps(project_metadata, indent=2, default=str)
    source_context_json = json.dumps(source_context, indent=2, default=str)
    strategic_enabled = project_type == "external" or strategic_analysis_enabled
    inference_instruction = (
        "AI inference is enabled; infer missing BABOK mappings only when supported by source evidence and flag them."
        if allow_ai_inference
        else "AI inference is disabled; do not infer missing BABOK mappings beyond explicit UI selections."
    )
    # The model receives the canonical scaffold as data, not only prose guidance.
    canonical_instruction = f"""
    Canonical Business Analysis Knowledge Framework target:
    - artifact_id
    - project_metadata
    - analysis_orchestration
    - source_context
    - semantic_model
    - entity_relationships
    - process_intelligence
    - test_intelligence
    - impact_analysis
    - executive_translation
    - enterprise_intelligence
    - strategic_analysis
    - delivery_analysis
    - governance_analysis
    - output_views

    Project metadata from UI:
{metadata_json}

{source_intent_context}

    Analysis orchestration from UI:
{orchestration_json}

    Source context built from provided source materials:
{source_context_json}

    Use these three JSON blocks as source-of-truth scaffolding. Preserve their
    explicit values in the output and enrich only with evidence-supported
    semantic findings. {inference_instruction}

    Produce detailed BA-ready outputs, not short labels. Each relevant semantic
    entity should describe evidence, impact, relationships, and next-step
    implications where supported by the source material.

    Generate entity_relationships only after extracting the canonical model.
    Relationships must connect meaningful business analysis entities, not merely
    names appearing in the same source. Do not use generic related_to unless no
    specific relationship applies. Prefer: drives, supports, depends_on,
    constrains, implements, validates, tests, mitigates, owns, consumes,
    produces, integrates_with, and impacts.

    Prioritize relationships between objectives and capabilities, capabilities
    and requirements, requirements and integrations/data entities/risks/user
    stories, user stories and acceptance criteria, acceptance criteria and UAT
    scenarios, constraints and affected requirements, and risks and mitigations.
    Each relationship must include source_id, source_type, relationship_type,
    target_id, target_type, a business-specific description, confidence, and
    source_reference. Assign stable IDs to delivery entities including features,
    user stories, acceptance criteria, and UAT scenarios.

    Populate process_intelligence, test_intelligence, impact_analysis,
    executive_translation, and enterprise_intelligence from evidence-supported
    findings. Enterprise intelligence must identify controls, systems,
    integrations, data flows, and integration controls where supported.

    Refinement mode:
    {refinement_instruction or "This is an initial analysis run."}
    If this is a refinement run, preserve still-valid prior findings, improve
    or expand weak areas, add new evidence-supported findings, and avoid
    discarding previous semantic entities unless the source or refinement
    context clearly supersedes them.

    Strategic analysis enabled: {str(strategic_enabled).lower()}
    """

    if project_type != "external":
        return f"""
    This is an internal business analysis initiative.

    Business Domain: {domain_context}
    Initiative Type: {initiative_type or "Infer when supported by source materials."}
{canonical_instruction}
{focus_context}
{activity_context}

    Use the business domain to interpret terminology, stakeholders,
    constraints, risks, compliance considerations, and workflow patterns.
    Keep the analysis lean and implementation-focused.
    """

    return f"""
    This is an external business analysis initiative.

    Company: {company_name or "Not provided"}
    Industry: {industry or "Not provided"}
    Business Domain: {domain_context}
    Initiative Type: {initiative_type or "Infer when supported by source materials."}{country_context}
{canonical_instruction}
{focus_context}
{activity_context}

    Keep Core Analysis separate from Strategic Intelligence.

    Include Strategic Intelligence sections:
    - SWOT analysis
    - PESTEL analysis
    - BABOK BACCM analysis
    - market and stakeholder considerations

    Do not invent company-specific facts that are not supported by the source materials
    or the provided context. Mark unknowns as assumptions or open questions.
    """


def enforce_orchestration_source_of_truth(
    analysis: CBAKFAnalysisOutput,
    project_metadata: dict,
    orchestration_context: dict,
    source_context: dict,
) -> CBAKFAnalysisOutput:
    # Persisted canonical metadata must match the request even if the model inferred more.
    analysis.project_metadata = analysis.project_metadata.model_copy(
        update=project_metadata
    )
    analysis.analysis_orchestration = analysis.analysis_orchestration.model_copy(
        update=orchestration_context
    )
    analysis.source_context = analysis.source_context.model_copy(update=source_context)

    if not orchestration_context.get("strategic_analysis_enabled"):
        analysis.strategic_analysis = StrategicAnalysis()

    return analysis


# prompt = f"""
  #    Act as a senior enterprise Business Analyst.
#    Analyze this meeting transcript and extract:
#    - Business summary
#    - User stories
#    - Acceptance criteria
  #  - Risks
  #  - Assumptions
  #  - Dependencies
  #  - Open questions
#  - UAT scenarios

#  Transcript:
  #  {transcript}
#    response = client.chat.completions.create(
  #      model="gpt-4.1-mini",
        #model="gpt-5-nano",
  #      messages=[
   ##         {"role": "system", "content": "You are a senior business analyst."},
   #         {"role": "user", "content": prompt}
   #     ]
#  )
#    return response.choices[0].message.parsed
