from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class AnalysisArtifact(Base):
    __tablename__ = "analysis_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String, nullable=False)
    project_type = Column(String, nullable=False, default="internal", server_default="internal")
    company_name = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    analysis_focus_key = Column(String, nullable=True)
    analysis_focus_chapter = Column(String, nullable=True)
    analysis_focus_area = Column(String, nullable=True)
    selected_activity_keys = Column(JSON, nullable=True)
    selected_activity_labels = Column(JSON, nullable=True)
    selected_techniques = Column(JSON, nullable=True)
    infer_additional_techniques = Column(Boolean, default=True)
    selected_outputs = Column(JSON, nullable=True)
    source_files = Column(JSON, nullable=True)
    country = Column(String, nullable=True)
    transcript = Column(Text, nullable=False)
    analysis_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False)
    current_version_id = Column(Integer, nullable=True, index=True)


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"

    id = Column(Integer, primary_key=True, index=True)
    artifact_id = Column(Integer, nullable=False, index=True)
    analysis_json = Column(JSON, nullable=False)
    version_type = Column(String, default="snapshot")
    is_active = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    restored_at = Column(DateTime(timezone=True), nullable=True, index=True)
    current_version_id = Column(Integer, nullable=True, index=True)
