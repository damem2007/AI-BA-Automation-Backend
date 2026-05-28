from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Literal

from app.database import SessionLocal
from app.models import AnalysisArtifact, ArtifactVersion
from app.schemas.analysis import TranscriptRequest
from app.services.analysis_context import (
    BA_ACTIVITY_AREAS,
    BABOK_FOCUS_AREAS,
    resolve_activity_recommendations,
)
from app.services.ai_service import analyze_transcript
from app.services.export_service import build_export
from datetime import datetime, timezone

router = APIRouter()


class ExportRequest(BaseModel):
    format: Literal["pdf", "docx", "markdown", "image", "csv", "xlsx"]
    sections: List[str]


class ActivityRecommendationRequest(BaseModel):
    activity_keys: List[str] = []

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/analyze-source-materials")
@router.post("/analyze-transcript")
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
        analysis_json=analysis.model_dump()
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    artifact.analysis_json = {
        **artifact.analysis_json,
        "artifact_id": str(artifact.id),
    }
    db.commit()
    db.refresh(artifact)

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
        "analysis": artifact.analysis_json,
        "created_at": artifact.created_at
     }

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
def get_artifact(artifact_id: int, db: Session = Depends(get_db)):
    artifact = (
        db.query(AnalysisArtifact)
        .filter(AnalysisArtifact.id == artifact_id)
        .first()
    )
    if not artifact:
        return {"error": "Artifact not found"}
    
    return{
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
        "transcript": artifact.transcript,
        "analysis": artifact.analysis_json,
        "current_version_id": artifact.current_version_id,
        "created_at": artifact.created_at,
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
def get_artifact_versions(artifact_id: int, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    total = (
        db.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact_id)
        .count()
    )

    versions = (
        db.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.restored_at.desc().nullslast(),
                  ArtifactVersion.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return {
       "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "items": [{
            "id": version.id,
            "artifact_id": version.artifact_id,
            "created_at": version.created_at,
            "restored_at": version.restored_at,
            "is_active": version.is_active,
        }
        for version in versions
       ]
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

    return {
        "id": version.id,
        "artifact_id": version.artifact_id,
        "analysis": version.analysis_json,
        "created_at": version.created_at
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

    new_version = ArtifactVersion(
        artifact_id=artifact.id,
        analysis_json=updated_analysis,
        version_type="update",
        is_active=True,
    )

    db.query(ArtifactVersion).filter(
        ArtifactVersion.artifact_id == artifact_id
    ).update({ArtifactVersion.is_active: False})
    db.add(new_version)
    db.flush()

    artifact.analysis_json = updated_analysis
    artifact.current_version_id = new_version.id

    db.commit()
    db.refresh(artifact)

    return {
        "message": "Artifact updated successfully",
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
