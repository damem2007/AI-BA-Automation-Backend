import json
import base64
import binascii
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Literal, Optional

from app.database import SessionLocal
from app.models import AnalysisArtifact, ArtifactVersion, ProjectTeam, Team, TeamMembership
from app.schemas.auth import CurrentUser
from app.schemas.analysis import (
    RELATIONSHIP_TYPES,
    RefinementRequest,
    TranscriptRequest,
)
from app.services.analysis_context import (
    BA_ACTIVITY_AREAS,
    BABOK_FOCUS_AREAS,
    resolve_activity_recommendations,
)
from app.services.ai_service import analyze_transcript
from app.services.auth import get_current_user, require_permission
from app.services.analysis_jobs import analysis_jobs
from app.services.analysis_limits import (
    public_limits,
    validate_analysis_request,
)
from app.services.export_service import build_export
from app.services.traceability import build_traceability_matrix as build_canonical_traceability_matrix
from app.services.source_uploads import (
    discard_staged_upload,
    stage_upload,
    staged_upload_metrics,
)
from app.services.project_generator import (
    generate_artifact_avatar,
    generate_project_code,
    normalize_project_code,
)
from datetime import datetime, timezone

router = APIRouter(dependencies=[Depends(get_current_user)])


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


def incremental_item_key(item) -> str:
    if isinstance(item, dict):
        if item.get("source_id") and item.get("relationship_type") and item.get("target_id"):
            return (
                f"relationship:{item['source_id']}:{item['relationship_type']}:{item['target_id']}"
            )
        for key in ("id", "name", "category", "endpoint_or_interface", "description"):
            if item.get(key):
                return f"{key}:{str(item[key]).strip().lower()}"
    return json.dumps(item, sort_keys=True, default=str)


def merge_incremental_value(previous, current):
    """Preserve established findings while accepting richer refinement evidence."""
    if isinstance(previous, dict) and isinstance(current, dict):
        return {
            key: merge_incremental_value(previous.get(key), current.get(key))
            if key in previous and key in current
            else current.get(key, previous.get(key))
            for key in set(previous) | set(current)
        }
    if isinstance(previous, list) and isinstance(current, list):
        merged = list(previous)
        positions = {
            incremental_item_key(item): index
            for index, item in enumerate(merged)
        }
        for item in current:
            key = incremental_item_key(item)
            if key in positions:
                index = positions[key]
                merged[index] = merge_incremental_value(merged[index], item)
            else:
                positions[key] = len(merged)
                merged.append(item)
        return merged
    return previous if current in (None, "", [], {}) else current


def preserve_cumulative_intelligence(previous_analysis: dict, updated_analysis: dict) -> dict:
    cumulative = dict(updated_analysis)
    for section in (
        "semantic_model",
        "delivery_analysis",
        "process_intelligence",
        "test_intelligence",
        "impact_analysis",
    ):
        cumulative[section] = merge_incremental_value(
            (previous_analysis or {}).get(section) or {},
            (updated_analysis or {}).get(section) or {},
        )
    cumulative["entity_relationships"] = merge_incremental_value(
        canonical_relationships(previous_analysis),
        canonical_relationships(updated_analysis),
    )
    return cumulative


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


TRACEABILITY_STOP_WORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "is", "of", "on",
    "or", "that", "the", "this", "to", "with", "system", "shall", "must", "should",
}


def semantic_entity_tokens(entity: dict) -> set[str]:
    text = f"{entity.get('name') or ''} {entity.get('description') or ''}".lower()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text)
        if len(token) > 2 and token not in TRACEABILITY_STOP_WORDS
    }


def reusable_entity_matches(current_registry: dict[str, dict], context_registry: dict[str, dict]) -> list[dict]:
    matches = []
    for current in current_registry.values():
        current_tokens = semantic_entity_tokens(current)
        if not current_tokens:
            continue
        for existing in context_registry.values():
            if current["type"] != existing["type"]:
                continue
            existing_tokens = semantic_entity_tokens(existing)
            if not existing_tokens:
                continue
            intersection = current_tokens & existing_tokens
            union = current_tokens | existing_tokens
            similarity = len(intersection) / len(union) if union else 0
            containment = len(intersection) / min(len(current_tokens), len(existing_tokens))
            if similarity < 0.5 and containment < 0.75:
                continue
            matches.append({
                "current_id": current["id"],
                "current_name": current["name"],
                "existing_id": existing["id"],
                "existing_name": existing["name"],
                "entity_type": current["type"],
                "similarity": round(max(similarity, containment), 2),
                "match_reason": f"Shared business concepts: {', '.join(sorted(intersection)[:6])}",
                "current_source_reference": current.get("source_reference") or "",
                "existing_source_reference": existing.get("source_reference") or "",
            })
    return sorted(matches, key=lambda item: item["similarity"], reverse=True)[:20]


def serialize_artifact_response(
    artifact: AnalysisArtifact,
    analysis_json: dict,
    selected_phase: Optional[int] = None,
    db: Optional[Session] = None,
) -> dict:
    teams = artifact_team_summaries(db, artifact.id) if db else []
    return {
        "id": artifact.id,
        "project_name": artifact.project_name,
        "project_code": artifact.project_code,
        "avatar_initials": artifact.avatar_initials,
        "avatar_color": artifact.avatar_color,
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
        "team_id": artifact.team_id,
        "owner_user_id": artifact.owner_user_id,
        "is_archived": artifact.is_archived,
        "teams": teams,
        "analysis": analysis_json,
        "current_version_id": artifact.current_version_id,
        "selected_phase": selected_phase or get_analysis_phase(analysis_json),
        "created_at": artifact.created_at,
    }


def artifact_team_summaries(db: Session, artifact_id: int) -> list[dict]:
    teams = db.query(Team).join(ProjectTeam, ProjectTeam.team_id == Team.id).filter(
        ProjectTeam.artifact_id == artifact_id,
        Team.is_archived.is_(False),
    ).order_by(Team.name.asc()).all()
    palette = ["#147d92", "#7c3aed", "#b45309", "#047857", "#be123c", "#3f6212"]
    icons = ["users", "blocks", "workflow", "layers", "briefcase", "network"]
    return [
        {
            "id": team.id,
            "name": team.name,
            "color": palette[team.id % len(palette)],
            "icon": icons[team.id % len(icons)],
        }
        for team in teams
    ]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def accessible_artifacts_query(
    db: Session,
    user: CurrentUser,
    include_archived: bool = False,
):
    query = db.query(AnalysisArtifact).filter(AnalysisArtifact.is_deleted.is_(False))
    if not include_archived:
        query = query.filter(AnalysisArtifact.is_archived.is_(False))
    if not user.is_global:
        query = query.filter(AnalysisArtifact.tenant_id == user.tenant_id)
    if not user.is_global and "view_all_projects" not in user.permissions:
        team_ids = db.query(TeamMembership.team_id).filter(TeamMembership.user_id == user.id)
        project_ids = db.query(ProjectTeam.artifact_id).filter(ProjectTeam.team_id.in_(team_ids))
        query = query.filter(
            (AnalysisArtifact.owner_user_id == user.id)
            | (AnalysisArtifact.id.in_(project_ids))
        )
    return query


def get_accessible_artifact(
    db: Session,
    artifact_id: int,
    user: CurrentUser,
    include_archived: bool = False,
) -> AnalysisArtifact:
    artifact = accessible_artifacts_query(db, user, include_archived).filter(
        AnalysisArtifact.id == artifact_id
    ).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


def validate_team_assignment(db: Session, team_ids: list[int], user: CurrentUser) -> list[Team]:
    if not team_ids:
        return []
    teams = db.query(Team).filter(
        Team.id.in_(team_ids),
        Team.tenant_id == user.tenant_id,
        Team.is_archived.is_(False),
    ).all()
    if {team.id for team in teams} != set(team_ids):
        raise HTTPException(status_code=422, detail="One or more selected teams are not available")
    for team in teams:
        if not team.allow_multiple_projects and db.query(ProjectTeam).filter(
            ProjectTeam.team_id == team.id
        ).first():
            raise HTTPException(
                status_code=409,
                detail=f"{team.name} is limited to one project. Enable multi-project work in Team settings.",
            )
    if user.is_global:
        return teams
    member_team_ids = {
        value[0]
        for value in db.query(TeamMembership.team_id).filter(
            TeamMembership.user_id == user.id,
            TeamMembership.team_id.in_(team_ids),
        ).all()
    }
    if member_team_ids != set(team_ids):
        raise HTTPException(status_code=403, detail="Selected team access is required")
    return teams


def resolve_project_identity(
    db: Session,
    project_name: str,
    requested_code: Optional[str],
    tenant_id: str,
) -> tuple[str, str, str]:
    project_code = normalize_project_code(requested_code or "")
    if project_code and not 3 <= len(project_code) <= 32:
        raise HTTPException(
            status_code=422,
            detail="Project code must contain 3 to 32 letters, numbers, or hyphens",
        )
    if project_code and db.query(AnalysisArtifact).filter(
        AnalysisArtifact.tenant_id == tenant_id,
        AnalysisArtifact.project_code == project_code,
    ).first():
        raise HTTPException(status_code=409, detail="Project code already exists in this organization")
    while not project_code:
        candidate = generate_project_code(project_name)
        if not db.query(AnalysisArtifact).filter(
            AnalysisArtifact.tenant_id == tenant_id,
            AnalysisArtifact.project_code == candidate,
        ).first():
            project_code = candidate
    avatar_color, avatar_initials = generate_artifact_avatar(project_name)
    return project_code, avatar_initials, avatar_color


def run_initial_analysis(request: TranscriptRequest, db: Session, actor: CurrentUser):
    validate_analysis_request(request)
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
        for source_file in request.source_files or []:
            if source_file.storage_id:
                discard_staged_upload(source_file.storage_id)
        raise HTTPException(
            status_code=502,
            detail=f"Analysis service failed: {error}",
        ) from error
    for source_file in request.source_files or []:
        if source_file.storage_id:
            discard_staged_upload(source_file.storage_id)
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

    selected_team_ids = list(dict.fromkeys(request.team_ids or ([request.team_id] if request.team_id else [])))
    project_code, avatar_initials, avatar_color = resolve_project_identity(
        db, request.project_name, request.project_code, actor.tenant_id
    )
    artifact = AnalysisArtifact(
        project_name=request.project_name,
        project_code=project_code,
        avatar_initials=avatar_initials,
        avatar_color=avatar_color,
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
        analysis_json=analysis_payload,
        owner_user_id=actor.id,
        team_id=selected_team_ids[0] if selected_team_ids else None,
        tenant_id=actor.tenant_id,
    )
    db.add(artifact)
    db.flush()
    for team_id in selected_team_ids:
        db.add(ProjectTeam(artifact_id=artifact.id, team_id=team_id, tenant_id=actor.tenant_id, assigned_by=actor.id))
    db.commit()
    db.refresh(artifact)
    artifact.analysis_json = {
        **artifact.analysis_json,
        "artifact_id": str(artifact.id),
    }
    initial_version = ArtifactVersion(
        artifact_id=artifact.id,
        tenant_id=artifact.tenant_id,
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

    return serialize_artifact_response(artifact, artifact.analysis_json, 1, db)


def stage_request_source_files(request: TranscriptRequest) -> tuple[TranscriptRequest, list[str]]:
    """Replace base64 request payloads with bounded RAM references before queueing."""
    staged_ids = []
    staged_files = []
    try:
        for source_file in request.source_files or []:
            if not source_file.content_base64:
                staged_files.append(source_file)
                continue
            try:
                content = base64.b64decode(source_file.content_base64, validate=True)
            except (binascii.Error, ValueError) as error:
                raise HTTPException(
                    status_code=422,
                    detail=f"{source_file.name} contains invalid base64 content.",
                ) from error
            storage_id = stage_upload(content)
            staged_ids.append(storage_id)
            staged_files.append(
                source_file.model_copy(
                    update={
                        "size": len(content),
                        "content_base64": None,
                        "storage_id": storage_id,
                    }
                )
            )
    except Exception:
        for storage_id in staged_ids:
            discard_staged_upload(storage_id)
        raise
    return request.model_copy(update={"source_files": staged_files}, deep=True), staged_ids


@router.post("/analyze-source-materials")
@router.post("/analyze")
def analyze(request: TranscriptRequest, db: Session = Depends(get_db)):
    # Compatibility endpoint. New clients should use the background generate + poll API.
    raise HTTPException(status_code=410, detail="Use /analyze/generate for authenticated analysis jobs")


@router.post("/analyze/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_analysis(
    request: TranscriptRequest,
    http_request: Request,
    user: CurrentUser = Depends(require_permission("create_analysis")),
    db: Session = Depends(get_db),
):
    validate_analysis_request(request)
    selected_team_ids = list(dict.fromkeys(request.team_ids or ([request.team_id] if request.team_id else [])))
    validate_team_assignment(db, selected_team_ids, user)
    client_host = http_request.client.host if http_request.client else "unknown"
    client_key = f"{user.tenant_id}:{user.subject}:{client_host}"
    request_snapshot, staged_ids = stage_request_source_files(request)

    def work():
        db = SessionLocal()
        try:
            return run_initial_analysis(request_snapshot, db, user)
        finally:
            db.close()

    try:
        job = analysis_jobs.submit(
            client_key,
            work,
            owner_subject=user.subject,
            tenant_id=user.tenant_id,
        )
    except Exception:
        for storage_id in staged_ids:
            discard_staged_upload(storage_id)
        raise
    return {**job, "status_url": f"/analyze/jobs/{job['job_id']}"}


@router.get("/analyze/jobs/{job_id}")
def get_analysis_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    job = analysis_jobs.get(job_id)
    if user.role != "superadmin" and (
        job.get("owner_subject") != user.subject or job.get("tenant_id") != user.tenant_id
    ):
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


@router.get("/analyze/jobs")
def get_analysis_job_metrics(_: CurrentUser = Depends(require_permission("manage_projects"))):
    return analysis_jobs.metrics()


@router.get("/analysis-config/limits")
def get_analysis_limits():
    return {**public_limits(), **analysis_jobs.metrics(), **staged_upload_metrics()}


@router.get("/analysis-artifacts")
def get_artifacts(
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    artifacts = (
        accessible_artifacts_query(db, user)
        .order_by(AnalysisArtifact.created_at.desc())
        .all()
    )
    return[
        {
            "id": artifact.id,
            "project_name": artifact.project_name,
            "project_code": artifact.project_code,
            "avatar_initials": artifact.avatar_initials,
            "avatar_color": artifact.avatar_color,
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
            "team_id": artifact.team_id,
            "owner_user_id": artifact.owner_user_id,
            "is_archived": artifact.is_archived,
            "teams": artifact_team_summaries(db, artifact.id),
            "created_at": artifact.created_at,
        }
        for artifact in artifacts
    ]


@router.get("/analysis-artifacts-overview")
def get_artifacts_overview(
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    artifacts = accessible_artifacts_query(db, user).order_by(AnalysisArtifact.created_at.desc()).all()
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
                "project_code": artifact.project_code,
                "avatar_initials": artifact.avatar_initials,
                "avatar_color": artifact.avatar_color,
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
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    artifact = get_accessible_artifact(db, artifact_id, user)

    selected_analysis, selected_phase = find_analysis_for_phase(artifact, phase, db)
    
    response = serialize_artifact_response(artifact, selected_analysis, selected_phase, db)
    response["transcript"] = artifact.transcript
    return response


@router.post("/analysis-artifacts/{artifact_id}/refine")
def refine_artifact(
    artifact_id: int,
    request: RefinementRequest,
    user: CurrentUser = Depends(require_permission("edit_artifacts")),
    db: Session = Depends(get_db),
):
    artifact = get_accessible_artifact(db, artifact_id, user)

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
            tenant_id=artifact.tenant_id,
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
        for source_file in request.source_files or []:
            if source_file.storage_id:
                discard_staged_upload(source_file.storage_id)
        raise HTTPException(
            status_code=502,
            detail=f"Refinement service failed: {error}",
        ) from error
    for source_file in request.source_files or []:
        if source_file.storage_id:
            discard_staged_upload(source_file.storage_id)

    updated_analysis = preserve_cumulative_intelligence(
        previous_analysis,
        analysis.model_dump(),
    )
    updated_analysis = enrich_relationships(updated_analysis)
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
        tenant_id=artifact.tenant_id,
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
        "artifact": serialize_artifact_response(artifact, artifact.analysis_json, phase, db),
    }

@router.post("/analysis-artifacts/{artifact_id}/export")
def export_artifact(
    artifact_id: int,
    request: ExportRequest,
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    artifact = get_accessible_artifact(db, artifact_id, user)

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
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    get_accessible_artifact(db, artifact_id, user)
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
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    get_accessible_artifact(db, artifact_id, user)
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
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db)
):
    get_accessible_artifact(db, artifact_id, user)
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
def get_artifact_traceability(
    artifact_id: int,
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    artifact = get_accessible_artifact(db, artifact_id, user)

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

    # Reusable evidence is projected only when canonical entities overlap semantically.
    context_palette = ["#147d92", "#7c3aed", "#b45309", "#047857", "#be123c", "#3f6212"]
    context_artifacts = accessible_artifacts_query(db, user).filter(
        AnalysisArtifact.id != artifact_id
    ).order_by(AnalysisArtifact.created_at.desc()).limit(20).all()
    existing_project_context = []
    for context_artifact in context_artifacts:
        context_analysis = context_artifact.analysis_json or {}
        context_registry = entity_registry(context_analysis)
        context_relationships = canonical_relationships(context_analysis)
        shared_entities = reusable_entity_matches(registry, context_registry)
        if not shared_entities:
            continue
        matched_existing_ids = {match["existing_id"] for match in shared_entities}
        relationship_evidence = []
        for relationship in context_relationships:
            if not ({relationship["source_id"], relationship["target_id"]} & matched_existing_ids):
                continue
            relationship_evidence.append({
                **relationship,
                "source_name": context_registry.get(relationship["source_id"], {}).get("name", relationship["source_id"]),
                "target_name": context_registry.get(relationship["target_id"], {}).get("name", relationship["target_id"]),
            })
        color = context_palette[len(existing_project_context) % len(context_palette)]
        entity_types = sorted({match["entity_type"].replace("_", " ") for match in shared_entities})
        existing_project_context.append(
            {
                "project_id": context_artifact.id,
                "project_name": context_artifact.project_name,
                "project_code": context_artifact.project_code,
                "avatar_initials": context_artifact.avatar_initials,
                "avatar_color": context_artifact.avatar_color,
                "source_color": color,
                "source_files": context_artifact.source_files or [],
                "link_summary": (
                    f"{len(shared_entities)} reusable canonical alignment"
                    f"{'s' if len(shared_entities) != 1 else ''} across {', '.join(entity_types)}."
                ),
                "shared_entities": shared_entities,
                "relationship_evidence": relationship_evidence[:20],
                "reuse_guidance": [
                    "Validate matched evidence against the current project's source material before reuse.",
                    "Reuse confirmed controls, tests, and dependency paths where the linked requirement remains equivalent.",
                ],
            }
        )

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
        "existing_project_context": existing_project_context,
        "coverage": {
            "total_entities": len(nodes),
            "linked_entities": len([node for node in nodes if node["id"] in linked_ids]),
            "unlinked_entities": [node["id"] for node in nodes if node["id"] not in linked_ids],
            "relationship_count": len(relationships),
            "source_referenced_entities": len(
                [node for node in nodes if node.get("source_reference")]
            ),
        },
    }


@router.get("/analysis-artifacts/{artifact_id}/intelligence")
def get_artifact_intelligence(
    artifact_id: int,
    user: CurrentUser = Depends(require_permission("view_artifacts")),
    db: Session = Depends(get_db),
):
    artifact = get_accessible_artifact(db, artifact_id, user)

    analysis = artifact.analysis_json or {}
    return {
        "artifact_id": artifact_id,
        "process_intelligence": analysis.get("process_intelligence") or {},
        "test_intelligence": analysis.get("test_intelligence") or {},
        "impact_analysis": analysis.get("impact_analysis") or {},
        "executive_translation": analysis.get("executive_translation") or {},
        "enterprise_intelligence": analysis.get("enterprise_intelligence") or {},
    }

@router.post("/analysis-artifacts/{artifact_id}/versions/{version_id}/restore")
def restore_artifact_version(
    artifact_id: int,
    version_id: int,
    user: CurrentUser = Depends(require_permission("edit_artifacts")),
    db: Session = Depends(get_db)
):
    artifact = get_accessible_artifact(db, artifact_id, user)

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
        tenant_id=artifact.tenant_id,
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
            "project_code": artifact.project_code,
            "avatar_initials": artifact.avatar_initials,
            "avatar_color": artifact.avatar_color,
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
    user: CurrentUser = Depends(require_permission("edit_artifacts")),
    db: Session = Depends(get_db)
):
    artifact = get_accessible_artifact(db, artifact_id, user)

    updated_analysis = enrich_relationships(updated_analysis)
    updated_phase = get_analysis_phase(updated_analysis)
    artifact_head_phase = get_analysis_phase(artifact.analysis_json or {})
    new_version = ArtifactVersion(
        artifact_id=artifact.id,
        tenant_id=artifact.tenant_id,
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
            db,
        ),
    }
