from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Literal, Optional

from app.database import SessionLocal
from app.models import AnalysisArtifact, ArtifactVersion
from app.schemas.analysis import RELATIONSHIP_TYPES, RefinementRequest, TranscriptRequest
from app.services.analysis_context import (
    BA_ACTIVITY_AREAS,
    BABOK_FOCUS_AREAS,
    resolve_activity_recommendations,
)
from app.services.ai_service import analyze_transcript
from app.services.export_service import build_export
from app.services.traceability import build_traceability_matrix as build_canonical_traceability_matrix
from datetime import datetime, timezone

router = APIRouter()


class ExportRequest(BaseModel):
    format: Literal["pdf", "docx", "markdown", "image", "csv", "xlsx"]
    sections: List[str]


class ActivityRecommendationRequest(BaseModel):
    activity_keys: List[str] = []


def activity_labels_for_keys(activity_keys: List[str]) -> List[str]:
    # Keep route-level refinement metadata aligned with the same BABOK catalog used by the UI.
    lookup = {
        item["key"]: item["label"]
        for group in BA_ACTIVITY_AREAS
        for item in group["items"]
    }
    return [lookup[key] for key in activity_keys if key in lookup]


def unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def ensure_phase_history(analysis_json: dict, artifact: AnalysisArtifact) -> dict:
    orchestration = analysis_json.setdefault("analysis_orchestration", {})
    history = orchestration.get("activity_run_history") or []

    if history:
        return analysis_json

    # Older artifacts may predate phase tracking, so synthesize Phase 1 for the progression wizard.
    orchestration["refinement_phase"] = orchestration.get("refinement_phase") or 1
    orchestration["activity_run_history"] = [
        {
            "phase": 1,
            "version_id": artifact.current_version_id,
            "previous_version_id": None,
            "selected_activity_keys": (
                orchestration.get("selected_activity_keys")
                or artifact.selected_activity_keys
                or []
            ),
            "selected_activities": (
                orchestration.get("babok_activities")
                or artifact.selected_activity_labels
                or []
            ),
            "rerun_activity_keys": [],
            "rerun_activities": [],
            "selected_techniques": (
                orchestration.get("selected_techniques")
                or artifact.selected_techniques
                or []
            ),
            "source_files": artifact.source_files or [],
            "output_mode": "aggregated",
            "created_at": artifact.created_at.isoformat() if artifact.created_at else "",
            "note": "Initial analysis run.",
        }
    ]
    return analysis_json


def find_analysis_for_phase(
    artifact: AnalysisArtifact,
    phase: Optional[str],
    db: Session,
) -> tuple[dict, Optional[int]]:
    head_analysis = ensure_phase_history(dict(artifact.analysis_json or {}), artifact)
    if not phase or phase == "latest":
        return head_analysis, head_analysis.get("analysis_orchestration", {}).get("refinement_phase")

    try:
        requested_phase = int(phase)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Phase must be a number or latest") from error

    artifact_head_phase = head_analysis.get("analysis_orchestration", {}).get("refinement_phase")
    if requested_phase == artifact_head_phase:
        return head_analysis, requested_phase

    versions = (
        db.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact.id)
        .order_by(ArtifactVersion.created_at.desc())
        .all()
    )
    for version in versions:
        version_analysis = ensure_phase_history(dict(version.analysis_json or {}), artifact)
        version_phase = version_analysis.get("analysis_orchestration", {}).get("refinement_phase")
        if version_phase == requested_phase:
            return version_analysis, requested_phase

    raise HTTPException(status_code=404, detail=f"Phase {requested_phase} not found")


def get_analysis_phase(analysis_json: dict) -> int:
    # Versions belong to a phase; the phase number lives inside canonical orchestration metadata.
    return int(
        (analysis_json or {})
        .get("analysis_orchestration", {})
        .get("refinement_phase")
        or 1
    )


def artifact_version_numbers(db: Session, artifact_id: int) -> dict[int, int]:
    versions = (
        db.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.created_at.asc(), ArtifactVersion.id.asc())
        .all()
    )
    return {version.id: index + 1 for index, version in enumerate(versions)}


def version_label(version_id: int, version_numbers: dict[int, int]) -> dict:
    number = version_numbers.get(version_id, 1)
    return {"version_number": number, "display_name": f"Version {number}"}


ENTITY_TYPE_BY_PATH = {
    "business_objectives": "business_objective",
    "capabilities": "capability",
    "requirements": "requirement",
    "stakeholders": "stakeholder",
    "risks": "risk",
    "constraints": "constraint",
    "integrations": "integration",
    "data_entities": "data_entity",
    "processes": "process",
    "features": "feature",
    "user_stories": "user_story",
    "acceptance_criteria": "acceptance_criterion",
    "uat_scenarios": "uat_scenario",
    "controls": "control",
    "systems": "system",
    "data_flows": "data_flow",
}

DELIVERY_TRACEABILITY_TYPES = {
    "business_objective",
    "capability",
    "requirement",
    "feature",
    "user_story",
    "acceptance_criterion",
    "uat_scenario",
}


def entity_type_for_path(path: list[str]) -> str:
    for part in reversed(path):
        if part in ENTITY_TYPE_BY_PATH:
            return ENTITY_TYPE_BY_PATH[part]
    value = path[-1] if path else "entity"
    return value[:-1] if value.endswith("s") else value


def entity_registry(analysis_json: dict) -> dict[str, dict]:
    registry = {}

    def visit(value, path: list[str]):
        if isinstance(value, dict):
            if value.get("id") and "entity_relationships" not in path:
                entity_id = str(value["id"])
                entity_type = entity_type_for_path(path)
                registry[entity_id] = {
                    "id": entity_id,
                    "type": entity_type,
                    "name": (
                        value.get("name")
                        or value.get("description")
                        or value.get("story")
                        or value.get("scenario")
                        or entity_id
                    ),
                    "description": (
                        value.get("description")
                        or value.get("story")
                        or value.get("scenario")
                        or ""
                    ),
                    "category": path[0] if path else "canonical",
                    "group": path[-1] if path else "canonical",
                    "source_reference": value.get("source_reference") or "",
                    "confidence": value.get("confidence") or 0,
                    "raw": value,
                }
            for key, child in value.items():
                if key not in {"metadata", "entity_relationships"}:
                    visit(child, [*path, key])
        elif isinstance(value, list):
            for child in value:
                visit(child, path)

    visit(analysis_json or {}, [])
    return registry


def infer_relationship_type(source_type: str, target_type: str) -> str:
    mapping = {
        ("business_objective", "capability"): "drives",
        ("business_objective", "requirement"): "drives",
        ("capability", "requirement"): "supports",
        ("requirement", "integration"): "depends_on",
        ("requirement", "data_entity"): "consumes",
        ("requirement", "risk"): "impacts",
        ("requirement", "user_story"): "implements",
        ("feature", "user_story"): "implements",
        ("user_story", "acceptance_criterion"): "validates",
        ("acceptance_criterion", "uat_scenario"): "tests",
        ("constraint", "requirement"): "constrains",
        ("control", "risk"): "mitigates",
        ("stakeholder", "process"): "owns",
        ("stakeholder", "requirement"): "approves",
        ("stakeholder", "business_objective"): "sponsors",
        ("stakeholder", "capability"): "owns",
        ("stakeholder", "user_story"): "executes",
        ("integration", "data_entity"): "produces",
        ("integration", "system"): "integrates_with",
    }
    return mapping.get((source_type, target_type))


def relationship_description(
    source: dict,
    relationship_type: str,
    target: dict,
) -> str:
    verb = relationship_type.replace("_", " ")
    return f"{source['name']} {verb} {target['name']}."


def canonical_relationships(analysis_json: dict) -> list[dict]:
    semantic_model = (analysis_json or {}).get("semantic_model") or {}
    explicit = [
        *((analysis_json or {}).get("entity_relationships") or []),
        *(semantic_model.get("entity_relationships") or []),
    ]
    registry = entity_registry(analysis_json)
    relationships = []
    seen = set()

    for relationship in explicit:
        if not isinstance(relationship, dict):
            continue
        source = str(relationship.get("source_id") or relationship.get("source_entity_id") or "")
        target = str(relationship.get("target_id") or relationship.get("target_entity_id") or "")
        if not source or not target:
            continue
        source_entity = registry.get(source, {"name": source, "type": relationship.get("source_type") or "entity"})
        target_entity = registry.get(target, {"name": target, "type": relationship.get("target_type") or "entity"})
        source_type = relationship.get("source_type") or source_entity.get("type") or "entity"
        target_type = relationship.get("target_type") or target_entity.get("type") or "entity"
        inferred_type = infer_relationship_type(source_type, target_type)
        relationship_type = relationship.get("relationship_type")
        if relationship_type not in RELATIONSHIP_TYPES:
            relationship_type = inferred_type
        if not relationship_type:
            continue
        key = (source, target, relationship_type)
        if key in seen:
            continue
        seen.add(key)
        relationships.append({
            "source_id": source,
            "source_type": source_type,
            "relationship_type": relationship_type,
            "target_id": target,
            "target_type": target_type,
            "description": relationship.get("description") or relationship_description(
                source_entity, relationship_type, target_entity
            ),
            "source_reference": relationship.get("source_reference") or "",
            "confidence": relationship.get("confidence") or 0,
        })

    for entity_id, entity in registry.items():
        for target in entity["raw"].get("related_entities") or []:
            target = str(target)
            target_entity = registry.get(target)
            if not target_entity:
                continue
            relationship_type = infer_relationship_type(entity["type"], target_entity["type"])
            if not relationship_type:
                continue
            key = (entity_id, target, relationship_type)
            if not target or key in seen:
                continue
            seen.add(key)
            relationships.append({
                "source_id": entity_id,
                "source_type": entity["type"],
                "relationship_type": relationship_type,
                "target_id": target,
                "target_type": target_entity["type"],
                "description": relationship_description(entity, relationship_type, target_entity),
                "source_reference": entity.get("source_reference") or "",
                "confidence": entity.get("confidence") or 0,
            })
    return relationships


def semantic_version_comparison(from_analysis: dict, to_analysis: dict) -> dict:
    before_entities = entity_registry(from_analysis)
    after_entities = entity_registry(to_analysis)
    before_relationships = {
        (item["source_id"], item["relationship_type"], item["target_id"]): item
        for item in canonical_relationships(from_analysis)
    }
    after_relationships = {
        (item["source_id"], item["relationship_type"], item["target_id"]): item
        for item in canonical_relationships(to_analysis)
    }

    entity_changes = []
    for entity_id in sorted(set(before_entities) | set(after_entities)):
        before = before_entities.get(entity_id)
        after = after_entities.get(entity_id)
        if before and after and before["raw"] == after["raw"]:
            continue
        status = "added" if not before else "removed" if not after else "modified"
        current = after or before
        changed_fields = []
        if before and after:
            changed_fields = [
                key
                for key in sorted(set(before["raw"]) | set(after["raw"]))
                if before["raw"].get(key) != after["raw"].get(key)
                and key not in {"metadata", "related_entities"}
            ]
        entity_changes.append({
            "status": status,
            "entity_id": entity_id,
            "entity_type": current["type"],
            "name": current["name"],
            "description": current["description"],
            "changed_fields": changed_fields,
        })

    relationship_changes = []
    for key in sorted(set(before_relationships) | set(after_relationships)):
        before = before_relationships.get(key)
        after = after_relationships.get(key)
        if before == after:
            continue
        status = "added" if not before else "removed" if not after else "modified"
        relationship_changes.append({"status": status, **(after or before)})

    intelligence_changes = []
    for section in (
        "process_intelligence",
        "test_intelligence",
        "impact_analysis",
        "executive_translation",
        "enterprise_intelligence",
    ):
        before = (from_analysis or {}).get(section) or {}
        after = (to_analysis or {}).get(section) or {}
        if before == after:
            continue
        changed_fields = [
            key
            for key in sorted(set(before) | set(after))
            if before.get(key) != after.get(key)
        ]
        intelligence_changes.append({
            "section": section,
            "changed_fields": changed_fields,
            "summary": f"{section.replace('_', ' ').title()} changed in {len(changed_fields)} areas.",
        })

    changed_sections = sorted({
        entity["entity_type"] for entity in entity_changes
    } | {
        "entity_relationships" for _ in relationship_changes
    } | {
        change["section"] for change in intelligence_changes
    })
    return {
        "section_names": changed_sections,
        "entity_changes": entity_changes,
        "relationship_changes": relationship_changes,
        "intelligence_changes": intelligence_changes,
    }


def build_traceability_links(relationships: list[dict], registry: dict[str, dict]) -> list[dict]:
    delivery_relationships = [
        relationship
        for relationship in relationships
        if relationship["source_type"] in DELIVERY_TRACEABILITY_TYPES
        and relationship["target_type"] in DELIVERY_TRACEABILITY_TYPES
    ]
    return [
        {
            **relationship,
            "source_name": registry.get(relationship["source_id"], {}).get("name", relationship["source_id"]),
            "target_name": registry.get(relationship["target_id"], {}).get("name", relationship["target_id"]),
        }
        for relationship in delivery_relationships
    ]


def enrich_relationships(analysis: dict) -> dict:
    analysis["entity_relationships"] = canonical_relationships(analysis)
    return analysis


def build_traceability_chains(matrix: list[dict], registry: dict[str, dict]) -> list[list[dict]]:
    outgoing = {}
    incoming = set()
    for relationship in matrix:
        outgoing.setdefault(relationship["source_id"], []).append(relationship)
        incoming.add(relationship["target_id"])
    roots = [source_id for source_id in outgoing if source_id not in incoming]
    chains = []

    def walk(entity_id: str, chain: list[dict], visited: set[str]):
        next_relationships = outgoing.get(entity_id) or []
        if not next_relationships or len(chain) >= 7:
            if chain:
                chains.append(chain)
            return
        for relationship in next_relationships:
            target_id = relationship["target_id"]
            if target_id in visited:
                continue
            walk(target_id, [*chain, relationship], {*visited, target_id})

    for root in roots:
        walk(root, [], {root})
    return chains[:100]


def serialize_artifact_response(
    artifact: AnalysisArtifact,
    analysis_json: dict,
    selected_phase: Optional[int] = None,
) -> dict:
    return {
        "id": artifact.id,
        "project_name": artifact.project_name,
        "project_type": artifact.project_type,
        "company_name": artifact.company_name,
        "industry": artifact.industry,
        "domain": artifact.domain,
        "analysis_focus_key": artifact.analysis_focus_key,
        "analysis_focus_chapter": artifact.analysis_focus_chapter,
        "analysis_focus_area": artifact.analysis_focus_area,
        "selected_activity_keys": artifact.selected_activity_keys,
        "selected_activity_labels": artifact.selected_activity_labels,
        "selected_techniques": artifact.selected_techniques,
        "infer_additional_techniques": artifact.infer_additional_techniques,
        "selected_outputs": artifact.selected_outputs,
        "source_files": artifact.source_files,
        "country": artifact.country,
        "analysis": analysis_json,
        "current_version_id": artifact.current_version_id,
        "selected_phase": selected_phase or get_analysis_phase(analysis_json),
        "created_at": artifact.created_at,
    }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/analyze-source-materials")
@router.post("/analyze")
def analyze(request: TranscriptRequest, db: Session = Depends(get_db)):
    source_text = request.source_text if request.source_text is not None else request.transcript

    try:
        # Return controlled API errors so upload failures are visible to the frontend.
        analysis=  analyze_transcript(
            project_name=request.project_name,
            source_text=source_text,
            project_type=request.project_type,
            company_name=request.company_name,
            industry=request.industry,
            domain=request.domain,
            initiative_type=request.initiative_type,
            analysis_focus_key=request.analysis_focus_key,
            analysis_focus_chapter=request.analysis_focus_chapter,
            analysis_focus_area=request.analysis_focus_area,
            selected_activity_keys=request.selected_activity_keys,
            selected_techniques=request.selected_techniques,
            allow_ai_inference=request.allow_ai_inference,
            infer_additional_techniques=request.infer_additional_techniques,
            selected_outputs=request.selected_outputs,
            source_files=[
                source_file.model_dump()
                for source_file in request.source_files or []
            ],
            strategic_analysis_enabled=request.strategic_analysis_enabled,
            country=request.country,
            source_intent=request.source_intent,
            source_subtype=request.source_subtype,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Analysis service failed: {error}",
        ) from error
    analysis_payload = enrich_relationships(analysis.model_dump())
    initial_orchestration = analysis_payload.setdefault("analysis_orchestration", {})
    # Initial analysis is recorded as phase one so artifact refinement has a visible BABOK breadcrumb.
    initial_orchestration.setdefault("refinement_phase", 1)
    initial_orchestration.setdefault(
        "activity_run_history",
        [
            {
                "phase": 1,
                "version_id": None,
                "previous_version_id": None,
                "selected_activity_keys": request.selected_activity_keys or [],
                "selected_activities": request.selected_activity_labels or [],
                "rerun_activity_keys": [],
                "rerun_activities": [],
                "selected_techniques": request.selected_techniques or [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "note": "Initial canonical analysis run.",
            }
        ],
    )
    initial_orchestration.setdefault("rerun_warnings", [])

    artifact = AnalysisArtifact(
        project_name=request.project_name,
        project_type=request.project_type,
        company_name=request.company_name,
        industry=request.industry,
        domain=request.domain,
        analysis_focus_key=request.analysis_focus_key,
        analysis_focus_chapter=request.analysis_focus_chapter,
        analysis_focus_area=request.analysis_focus_area,
        selected_activity_keys=request.selected_activity_keys,
        selected_activity_labels=request.selected_activity_labels,
        selected_techniques=request.selected_techniques,
        infer_additional_techniques=request.infer_additional_techniques,
        selected_outputs=request.selected_outputs,
        source_files=[
            {
                "name": source_file.name,
                "type": source_file.type,
                "size": source_file.size,
            }
            for source_file in request.source_files or []
        ],
        country=request.country,
        transcript=source_text,
        analysis_json=analysis_payload
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    artifact.analysis_json = {
        **artifact.analysis_json,
        "artifact_id": str(artifact.id),
    }
    initial_version = ArtifactVersion(
        artifact_id=artifact.id,
        analysis_json=artifact.analysis_json,
        version_type="initial",
        is_active=True,
    )
    db.add(initial_version)
    db.flush()
    # Phase 1 is a first-class version so later ?phase=1 navigation stays stable.
    history = artifact.analysis_json.get("analysis_orchestration", {}).get("activity_run_history") or []
    if history:
        history[0]["version_id"] = initial_version.id
        artifact.analysis_json["analysis_orchestration"]["activity_run_history"] = history
    else:
        # Fallback: synthesize Phase 1 history if missing
        artifact.analysis_json.setdefault("analysis_orchestration", {})["activity_run_history"] = [
            {
                "phase": 1,
                "version_id": initial_version.id,
                "previous_version_id": None,
                "selected_activity_keys": request.selected_activity_keys or [],
                "selected_activities": request.selected_activity_labels or [],
                "rerun_activity_keys": [],
                "rerun_activities": [],
                "selected_techniques": request.selected_techniques or [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "note": "Initial canonical analysis run.",
            }
        ]
    
    initial_version.analysis_json = artifact.analysis_json
    artifact.current_version_id = initial_version.id
    db.commit()
    db.refresh(artifact)

    return serialize_artifact_response(artifact, artifact.analysis_json, 1)

@router.get("/analysis-artifacts")
def get_artifacts(db: Session = Depends(get_db)):
    artifacts = (
        db.query(AnalysisArtifact)
        .order_by(AnalysisArtifact.created_at.desc())
        .all()
    )
    return[
        {
            "id": artifact.id,
            "project_name": artifact.project_name,
            "project_type": artifact.project_type,
            "company_name": artifact.company_name,
            "industry": artifact.industry,
            "domain": artifact.domain,
            "analysis_focus_key": artifact.analysis_focus_key,
            "analysis_focus_chapter": artifact.analysis_focus_chapter,
            "analysis_focus_area": artifact.analysis_focus_area,
            "selected_activity_keys": artifact.selected_activity_keys,
            "selected_activity_labels": artifact.selected_activity_labels,
            "selected_techniques": artifact.selected_techniques,
            "infer_additional_techniques": artifact.infer_additional_techniques,
            "selected_outputs": artifact.selected_outputs,
            "source_files": artifact.source_files,
            "country": artifact.country,
            "created_at": artifact.created_at,
        }
        for artifact in artifacts
    ]


@router.get("/analysis-artifacts-overview")
def get_artifacts_overview(db: Session = Depends(get_db)):
    artifacts = db.query(AnalysisArtifact).order_by(AnalysisArtifact.created_at.desc()).all()
    versions = db.query(ArtifactVersion).all()
    total_requirements = 0
    total_risks = 0
    total_open_questions = 0
    total_relationships = 0
    domain_counts = {}

    for artifact in artifacts:
        analysis = artifact.analysis_json or {}
        semantic = analysis.get("semantic_model") or {}
        requirements = semantic.get("requirements") or {}
        total_requirements += sum(
            len(items) for items in requirements.values() if isinstance(items, list)
        )
        total_risks += len(semantic.get("risks") or [])
        total_open_questions += len(semantic.get("open_questions") or [])
        total_relationships += len(canonical_relationships(analysis))
        domain = artifact.domain or "Unspecified"
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    return {
        "total_projects": len({artifact.project_name for artifact in artifacts}),
        "total_artifacts": len(artifacts),
        "total_versions": len(versions),
        "total_requirements": total_requirements,
        "total_risks": total_risks,
        "total_open_questions": total_open_questions,
        "total_relationships": total_relationships,
        "domain_distribution": [
            {"name": name, "count": count}
            for name, count in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True)
        ],
        "recent_artifacts": [
            {
                "id": artifact.id,
                "project_name": artifact.project_name,
                "domain": artifact.domain,
                "created_at": artifact.created_at,
                "phase": get_analysis_phase(artifact.analysis_json or {}),
            }
            for artifact in artifacts[:6]
        ],
    }

@router.get("/analysis-context/focus-areas")
def get_focus_areas():
    return BABOK_FOCUS_AREAS


@router.get("/analysis-context/activities")
def get_activity_areas():
    return BA_ACTIVITY_AREAS


@router.post("/analysis-context/activity-recommendations")
def get_activity_recommendations(request: ActivityRecommendationRequest):
    return resolve_activity_recommendations(request.activity_keys)

@router.get("/analysis-artifacts/{artifact_id}")
def get_artifact(
    artifact_id: int,
    phase: Optional[str] = None,
    db: Session = Depends(get_db),
):
    artifact = (
        db.query(AnalysisArtifact)
        .filter(AnalysisArtifact.id == artifact_id)
        .first()
    )
    if not artifact:
        return {"error": "Artifact not found"}

    selected_analysis, selected_phase = find_analysis_for_phase(artifact, phase, db)
    
    response = serialize_artifact_response(artifact, selected_analysis, selected_phase)
    response["transcript"] = artifact.transcript
    return response


@router.post("/analysis-artifacts/{artifact_id}/refine")
def refine_artifact(
    artifact_id: int,
    request: RefinementRequest,
    db: Session = Depends(get_db),
):
    artifact = (
        db.query(AnalysisArtifact)
        .filter(AnalysisArtifact.id == artifact_id)
        .first()
    )

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if (
        request.current_version_id is not None
        and artifact.current_version_id is not None
        and request.current_version_id != artifact.current_version_id
    ):
        # Refinement must start from the newest saved version so BA progression does not branch silently.
        raise HTTPException(
            status_code=409,
            detail="Artifact changed after this page loaded. Refresh before starting a refinement run.",
        )

    previous_analysis = artifact.analysis_json or {}
    previous_analysis = ensure_phase_history(dict(previous_analysis), artifact)
    previous_orchestration = previous_analysis.get("analysis_orchestration", {})
    previous_history = previous_orchestration.get("activity_run_history") or []
    previous_version_id = artifact.current_version_id

    if previous_history and not previous_history[-1].get("version_id"):
        baseline_snapshot = ArtifactVersion(
            artifact_id=artifact.id,
            analysis_json=previous_analysis,
            version_type="phase_snapshot",
            is_active=False,
        )
        db.add(baseline_snapshot)
        db.flush()
        # Legacy artifacts may not have a saved Phase 1 version; create one before refinement advances.
        previous_history[-1]["version_id"] = baseline_snapshot.id
        previous_orchestration["activity_run_history"] = previous_history
        previous_analysis["analysis_orchestration"] = previous_orchestration
        baseline_snapshot.analysis_json = previous_analysis
        previous_version_id = baseline_snapshot.id
    previous_activity_labels = previous_orchestration.get("babok_activities") or artifact.selected_activity_labels or []
    previous_activity_keys = previous_orchestration.get("selected_activity_keys") or artifact.selected_activity_keys or []
    requested_activity_keys = request.selected_activity_keys or []
    # Re-selected activities are allowed, but they are tracked as deliberate re-analysis.
    rerun_activity_keys = [
        key for key in requested_activity_keys if key in set(previous_activity_keys)
    ]
    rerun_activity_labels = activity_labels_for_keys(rerun_activity_keys)
    effective_activity_keys = requested_activity_keys

    if request.include_previous_activities:
        # The checkbox folds prior phases into the current lens for deeper refinement.
        effective_activity_keys = unique_preserve_order(
            [*previous_activity_keys, *requested_activity_keys]
        )
        rerun_activity_keys = [
            key for key in effective_activity_keys if key in set(previous_activity_keys)
        ]
        rerun_activity_labels = activity_labels_for_keys(rerun_activity_keys)

    if request.refinement_output_mode == "phase_only":
        refinement_instruction = (
            "This is an incremental BA refinement/progression run. Use the current "
            "saved canonical analysis as baseline/input context, but return a "
            "phase-focused result for the selected refinement activities. Preserve "
            "traceability to prior findings and flag re-analysis where a previously "
            "run activity is included again."
        )
    else:
        refinement_instruction = (
            "This is an incremental BA refinement/progression run. Use the current "
            "saved canonical analysis as the baseline/input data, aggregate prior "
            "confirmed findings with new source evidence, and return the updated "
            "canonical artifact as a cumulative BA analysis. Flag re-analysis where "
            "a previously run activity is included again."
        )

    uploaded_source_files = [
        source_file.model_dump()
        for source_file in request.source_files or []
    ]
    stored_source_files = artifact.source_files or []
    combined_source_file_metadata = [
        *stored_source_files,
        *[
            {
                "name": source_file.name,
                "type": source_file.type,
                "size": source_file.size,
            }
            for source_file in request.source_files or []
        ],
    ]

    try:
        analysis = analyze_transcript(
            project_name=artifact.project_name,
            source_text=artifact.transcript,
            project_type=artifact.project_type,
            company_name=artifact.company_name,
            industry=artifact.industry,
            domain=artifact.domain,
            analysis_focus_key=artifact.analysis_focus_key,
            analysis_focus_chapter=artifact.analysis_focus_chapter,
            analysis_focus_area=artifact.analysis_focus_area,
            selected_activity_keys=effective_activity_keys,
            selected_techniques=request.selected_techniques,
            allow_ai_inference=request.allow_ai_inference,
            infer_additional_techniques=request.infer_additional_techniques,
            selected_outputs=request.selected_outputs,
            # New phase uploads are included as fresh evidence while prior analysis remains the baseline.
            source_files=[*stored_source_files, *uploaded_source_files],
            strategic_analysis_enabled=(
                previous_orchestration.get("strategic_analysis_enabled", False)
            ),
            country=artifact.country,
            prior_analysis=previous_analysis,
            refinement_instruction=refinement_instruction,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Refinement service failed: {error}",
        ) from error

    updated_analysis = enrich_relationships(analysis.model_dump())
    orchestration = updated_analysis.setdefault("analysis_orchestration", {})
    history = list(previous_orchestration.get("activity_run_history") or [])
    phase = len(history) + 1
    warnings = []

    if rerun_activity_labels:
        warnings.append(
            "Re-analysis requested for previously run BABOK activities: "
            + ", ".join(rerun_activity_labels)
        )

    run_record = {
        # Version id is filled after the ArtifactVersion row is flushed.
        "phase": phase,
        "version_id": None,
        "previous_version_id": previous_version_id,
        "selected_activity_keys": effective_activity_keys,
        "selected_activities": activity_labels_for_keys(effective_activity_keys),
        "rerun_activity_keys": rerun_activity_keys,
        "rerun_activities": rerun_activity_labels,
        "selected_techniques": request.selected_techniques or [],
        "source_files": [
            {
                "name": source_file.name,
                "type": source_file.type,
                "size": source_file.size,
            }
            for source_file in request.source_files or []
        ],
        "output_mode": request.refinement_output_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Incremental refinement run aggregated into the canonical artifact."
            if request.refinement_output_mode == "aggregated"
            else "Incremental refinement run focused on this phase output."
        ),
    }
    history.append(run_record)
    orchestration["refinement_phase"] = phase
    orchestration["activity_run_history"] = history
    orchestration["rerun_warnings"] = warnings
    orchestration["inference_notes"] = unique_preserve_order(
        [
            *(orchestration.get("inference_notes") or []),
            *warnings,
        ]
    )

    new_version = ArtifactVersion(
        artifact_id=artifact.id,
        analysis_json=updated_analysis,
        version_type="refinement",
        is_active=True,
    )
    db.query(ArtifactVersion).filter(
        ArtifactVersion.artifact_id == artifact_id
    ).update({ArtifactVersion.is_active: False})
    db.add(new_version)
    db.flush()

    run_record["version_id"] = new_version.id
    updated_analysis["analysis_orchestration"]["activity_run_history"][-1] = run_record
    updated_analysis["artifact_id"] = str(artifact.id)
    new_version.analysis_json = updated_analysis

    artifact.analysis_json = updated_analysis
    artifact.current_version_id = new_version.id
    artifact.selected_activity_keys = effective_activity_keys
    artifact.selected_activity_labels = activity_labels_for_keys(effective_activity_keys)
    artifact.selected_techniques = request.selected_techniques
    artifact.infer_additional_techniques = request.infer_additional_techniques
    artifact.selected_outputs = request.selected_outputs
    artifact.source_files = combined_source_file_metadata

    db.commit()
    db.refresh(artifact)

    return {
        "message": "Artifact refinement completed successfully",
        "artifact": serialize_artifact_response(artifact, artifact.analysis_json, phase),
    }

@router.post("/analysis-artifacts/{artifact_id}/export")
def export_artifact(
    artifact_id: int,
    request: ExportRequest,
    db: Session = Depends(get_db),
):
    artifact = (
        db.query(AnalysisArtifact)
        .filter(AnalysisArtifact.id == artifact_id)
        .first()
    )

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        content, filename, media_type = build_export(
            artifact.project_name,
            artifact.analysis_json,
            request.sections,
            request.format,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

@router.get("/analysis-artifacts/{artifact_id}/versions")
def get_artifact_versions(
    artifact_id: int,
    page: int = 1,
    page_size: int = 20,
    phase: Optional[int] = None,
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    all_versions = (
        db.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.restored_at.desc().nullslast(),
                  ArtifactVersion.created_at.desc())
        .all()
    )

    if phase is not None:
        # Version history is scoped by phase because edits create versions inside a phase.
        all_versions = [
            version
            for version in all_versions
            if get_analysis_phase(version.analysis_json or {}) == phase
        ]

    total = len(all_versions)
    # The active marker must point to the newest version in the phase, even when the user is on page 2+.
    latest_version_for_phase = all_versions[0].id if phase is not None and all_versions else None
    versions = all_versions[offset : offset + page_size]
    version_numbers = artifact_version_numbers(db, artifact_id)

    return {
       "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "items": [{
            "id": version.id,
            "artifact_id": version.artifact_id,
            "version_type": version.version_type,
            "phase": get_analysis_phase(version.analysis_json or {}),
            "created_at": version.created_at,
            "restored_at": version.restored_at,
            "is_active": (
                version.id == latest_version_for_phase
                if phase is not None
                else version.is_active
            ),
            **version_label(version.id, version_numbers),
        }
        for version in versions
       ]
    }
@router.get("/analysis-artifacts/{artifact_id}/versions/compare")
def compare_artifact_versions(
    artifact_id: int,
    from_version_id: Optional[int] = None,
    to_version_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    versions = (
        db.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.created_at.asc(), ArtifactVersion.id.asc())
        .all()
    )
    if len(versions) < 2:
        raise HTTPException(status_code=400, detail="At least two versions are required to compare")

    by_id = {version.id: version for version in versions}
    from_version = by_id.get(from_version_id) if from_version_id else versions[-2]
    to_version = by_id.get(to_version_id) if to_version_id else versions[-1]
    if not from_version or not to_version:
        raise HTTPException(status_code=404, detail="One or both versions were not found")

    numbers = artifact_version_numbers(db, artifact_id)
    comparison = semantic_version_comparison(
        from_version.analysis_json or {},
        to_version.analysis_json or {},
    )
    return {
        "artifact_id": artifact_id,
        "from_version": {"id": from_version.id, **version_label(from_version.id, numbers)},
        "to_version": {"id": to_version.id, **version_label(to_version.id, numbers)},
        "changed_sections": len(comparison["section_names"]),
        **comparison,
    }


@router.get("/analysis-artifacts/{artifact_id}/versions/{version_id}")
def get_artifact_version(
    artifact_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    version = (
        db.query(ArtifactVersion)
        .filter(
            ArtifactVersion.artifact_id == artifact_id,
            ArtifactVersion.id == version_id
        )
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    version_numbers = artifact_version_numbers(db, artifact_id)
    return {
        "id": version.id,
        "artifact_id": version.artifact_id,
        "analysis": version.analysis_json,
        "created_at": version.created_at,
        "phase": get_analysis_phase(version.analysis_json or {}),
        **version_label(version.id, version_numbers),
    }


@router.get("/analysis-artifacts/{artifact_id}/traceability")
def get_artifact_traceability(artifact_id: int, db: Session = Depends(get_db)):
    artifact = db.query(AnalysisArtifact).filter(AnalysisArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    analysis = artifact.analysis_json or {}
    registry = entity_registry(analysis)
    nodes = [
        {key: value for key, value in node.items() if key != "raw"}
        for node in registry.values()
    ]
    relationships = canonical_relationships(analysis)
    traceability_links = build_traceability_links(relationships, registry)
    traceability_matrix = build_canonical_traceability_matrix({
        **analysis,
        "entity_relationships": relationships,
    })
    traceability_chains = build_traceability_chains(traceability_links, registry)
    linked_ids = {
        entity_id
        for relationship in relationships
        for entity_id in (
            relationship["source_id"],
            relationship["target_id"],
        )
    }
    source_links = {}
    for node in nodes:
        source = node.get("source_reference") or "No source reference"
        source_links.setdefault(source, []).append(node["id"])

    return {
        "artifact_id": artifact_id,
        "nodes": nodes,
        "relationships": relationships,
        "traceability_matrix": traceability_matrix,
        "traceability_links": traceability_links,
        "traceability_chains": traceability_chains,
        "source_traceability": [
            {"source_reference": source, "entity_ids": entity_ids}
            for source, entity_ids in source_links.items()
        ],
        "coverage": {
            "total_entities": len(nodes),
            "linked_entities": len([node for node in nodes if node["id"] in linked_ids]),
            "unlinked_entities": [node["id"] for node in nodes if node["id"] not in linked_ids],
            "relationship_count": len(relationships),
            "source_referenced_entities": len(
                [node for node in nodes if node.get("source_reference")]
            ),
        },
        "intelligence": {
            "process": analysis.get("process_intelligence") or {},
            "test": analysis.get("test_intelligence") or {},
            "impact": analysis.get("impact_analysis") or {},
            "executive_translation": analysis.get("executive_translation") or {},
            "enterprise": analysis.get("enterprise_intelligence") or {},
        },
    }

@router.post("/analysis-artifacts/{artifact_id}/versions/{version_id}/restore")
def restore_artifact_version(
    artifact_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    artifact = (
        db.query(AnalysisArtifact)
        .filter(AnalysisArtifact.id == artifact_id)
        .first()
    )

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    version = (
        db.query(ArtifactVersion)
        .filter(
            ArtifactVersion.artifact_id == artifact_id,
            ArtifactVersion.id == version_id
        )
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    current_snapshot = ArtifactVersion(
        artifact_id=artifact.id,
        analysis_json=artifact.analysis_json,
        version_type="pre_restore_snapshot",
        is_active=False,
    )

    db.add(current_snapshot)

    artifact.analysis_json = version.analysis_json
    artifact.current_version_id = version.id
    version.restored_at = datetime.now(timezone.utc)
    db.query(ArtifactVersion).filter(
        ArtifactVersion.artifact_id == artifact_id
    ).update({ArtifactVersion.is_active: False})
    version.is_active = True

    db.commit()
    db.refresh(artifact)

    return {
        "message": "Version restored successfully",
        "artifact": {
            "id": artifact.id,
            "project_name": artifact.project_name,
            "project_type": artifact.project_type,
            "company_name": artifact.company_name,
            "industry": artifact.industry,
            "domain": artifact.domain,
            "analysis_focus_key": artifact.analysis_focus_key,
            "analysis_focus_chapter": artifact.analysis_focus_chapter,
            "analysis_focus_area": artifact.analysis_focus_area,
            "selected_activity_keys": artifact.selected_activity_keys,
            "selected_activity_labels": artifact.selected_activity_labels,
            "selected_techniques": artifact.selected_techniques,
            "infer_additional_techniques": artifact.infer_additional_techniques,
            "selected_outputs": artifact.selected_outputs,
            "source_files": artifact.source_files,
            "country": artifact.country,
            "analysis": artifact.analysis_json,
            "current_version_id": artifact.current_version_id,
            "created_at": artifact.created_at
        }
    }

@router.put("/analysis-artifacts/{artifact_id}")
def update_artifact(
    artifact_id: int,
    updated_analysis: dict,
    db: Session = Depends(get_db)
):
    artifact = (
        db.query(AnalysisArtifact)
        .filter(AnalysisArtifact.id == artifact_id)
        .first()
    )

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    updated_analysis = enrich_relationships(updated_analysis)
    updated_phase = get_analysis_phase(updated_analysis)
    artifact_head_phase = get_analysis_phase(artifact.analysis_json or {})
    new_version = ArtifactVersion(
        artifact_id=artifact.id,
        analysis_json=updated_analysis,
        version_type="update",
        is_active=updated_phase == artifact_head_phase,
    )

    if updated_phase == artifact_head_phase:
        db.query(ArtifactVersion).filter(
            ArtifactVersion.artifact_id == artifact_id
        ).update({ArtifactVersion.is_active: False})
    db.add(new_version)
    db.flush()

    if updated_phase == artifact_head_phase:
        # Editing the artifact head advances the current run; older phase edits only create versions inside that phase.
        artifact.analysis_json = updated_analysis
        artifact.current_version_id = new_version.id

    db.commit()
    db.refresh(artifact)

    return {
        "message": "Artifact updated successfully",
        "artifact": serialize_artifact_response(
            artifact,
            updated_analysis if updated_phase != artifact_head_phase else artifact.analysis_json,
            updated_phase,
        ),
    }
