# Changelog

## 2026-07-02 - BA flow intelligence productization

### Added

- Canonical `requirements_quality` section for requirements clarity, testability, acceptance
  coverage, exception paths, data rules, conflicts, and sign-off readiness.
- Canonical `approval_governance` section for approval levels, RACI candidates, decision rights,
  sign-off sequence, assigned approvers/roles, and unresolved approval risks.
- Canonical `diagram_artifacts` section for Mermaid-ready BA/BSA visual artifacts such as process,
  system, data, journey, architecture, timeline, requirement, and governance diagrams.
- Persistent artifact approval assignments with assignee, requester, approval level, status, due
  date, notes, tenant lineage, and artifact-scoped candidate lookup.
- Migration `k7b5c1d9e023` for approval assignment workflow storage and lookup indexes.
- Project-level `signoff_configuration` for switching individual module sign-offs on or off per
  project while preserving final artifact sign-off as the end-of-workflow gate.
- Migration `l8c2f5a1d734` for persisted project sign-off configuration.

### Changed

- Analysis prompting now treats UAT planning as a first-class delivery output, including positive,
  negative, edge, regression, API/interface, reconciliation, reporting, role/access, control, and
  readiness coverage.
- Refinement merging now preserves and incrementally improves requirements quality, approval
  governance, and diagram artifacts across phases.
- The intelligence endpoint now returns requirements quality, approval governance, and diagram
  artifacts alongside test, impact, process, executive, and enterprise intelligence.
- Artifact APIs now support approval assignment list, create, candidate lookup, and status update
  operations under `/analysis-artifacts/{id}/approvals`.
- Project and artifact responses now include effective sign-off configuration so intelligence
  modules can respect disabled project sign-off checkpoints.
- Export service now supports `diagram_artifacts`, preserving Mermaid syntax in Markdown exports
  and including diagram artifact content in other export formats.

## 2026-07-01 - First-class project governance

### Added

- Durable `projects` table as the parent for analysis artifacts, with tenant-unique project code,
  avatar metadata, owner, archive state, and project details.
- `analysis_artifacts.project_id` so every artifact is an analysis output under a project.
- Project-scoped team assignment through `project_teams.project_id`, replacing artifact-level
  governance as the active authorization model.
- `GET /projects` and `POST /projects` APIs for governed project creation and project library
  access.
- Migration `h4d1a2b3c901` to create projects, backfill existing artifacts into project parents,
  and move team mappings to the project layer.
- Migration `i5e2b7c9d104` to remove duplicated project presentation fields from
  `analysis_artifacts`.
- `PATCH /projects/{project_id}` for parent project rename and metadata updates.
- Migration `j6a4f0e8c912` with composite indexes for project library pagination, artifact
  listing, team-based access checks, artifact rollups, and version history ordering.

### Changed

- New analysis can target an existing project with `project_id`; access is checked against the
  project owner, assigned teams, tenant, and `view_all_projects` permission.
- Archive, restore, archive impact, settings mapping, project listing, and artifact serialization
  now use project-level teams.
- Artifact API responses hydrate project name, code, and avatar from the parent `projects` row
  instead of storing redundant values on each artifact.
- The enterprise governance fixture now verifies project listing, team inheritance, archive, and
  restore against first-class projects.
- `GET /projects` and `GET /analysis-artifacts` now return paginated, searchable responses with
  batched project/team serialization to avoid full-table loads and per-row lookup loops.
- `/analysis-artifacts-overview` now counts versions with a scoped aggregate and builds recent
  artifact project metadata in one batch.
- Traceability source projections now include artifact, project, project code, source system, and
  source container context so internal evidence is user-meaningful and ready for future external
  knowledge-base provenance.

### Verified

- Backend imports pass for models and routes.
- `scripts/test_enterprise_governance_fixture.py` passes JWT, mapping, access, archive, and
  restore coverage.
- Python compile check passes with an isolated pycache.
- Live Alembic state upgrades to `j6a4f0e8c912 (head)`.
- Fresh base-to-head migration now succeeds against a temporary SQLite database, including the
  first-class project schema and query indexes.

### Fixed

- Removed the unused `empty_project_analysis_payload()` helper from `app/routes/analyze.py`
  because first-class project creation no longer needs an empty analysis stub.
- Applied the first-class project migration to the configured live database so
  `/analysis-artifacts-overview` no longer fails on missing `analysis_artifacts.project_id`.
- Repaired the historical migration chain so fresh environments create the base artifact tables
  before later migrations alter them.
- Converted older constraint, JSON, timestamp, and nullable-column migration operations to
  portable Alembic patterns where needed for local clean-db verification.

## 2026-06-20 - Project identity and resilient onboarding

### Added

- Tenant-unique project codes supplied during analysis creation or generated securely for API clients.
- Persisted project avatar initials and color, returned by artifact, overview, archive, team, mapping,
  version-restore, and traceability projections.
- Pending-onboarding resend endpoint for local reset links and SSO instructions.
- Single-active-token enforcement when issuing or resending password-reset invitations.
- Migration `f2b7d901e753` for project identity and avatar metadata.

### Changed

- SMTP delivery failures no longer roll back account creation; onboarding remains
  `email_pending_configuration` and can be retried.

### Verified

- The isolated governance fixture verifies onboarding status, resend behavior, active-token count,
  and project identity data in team mapping.

## 2026-06-20 - Tenant governance, hybrid identity, and project access

### Added

- Hybrid JWT authentication for local users and tenant-approved OIDC identity providers.
- Global local root administrator, tenant-scoped users, custom roles, permissions, password policy,
  password expiry, one-time reset tokens, onboarding email, and active/inactive account controls.
- Identity-provider configuration and batch synchronization, including safe handling when a
  directory email is already owned by a local account.
- Many-to-many project/team assignments with tenant policy for single-team or multi-team projects.
- Per-team multi-project policy: projects may have multiple teams, while each team controls whether
  it may be assigned across multiple projects.
- Team membership inheritance so users see projects assigned to their teams; global users and
  roles with `view_all_projects` retain governed portfolio access.
- Tenant-scoped archive and restore for projects, teams, and users.
- Dependency-aware archive previews that retain versions, assignments, memberships, and ownership
  links without creating orphan records.
- Semantic cross-project traceability that reports only materially aligned canonical entities and
  explains source, similarity, relationship evidence, and reuse guidance.
- Global organization registry and tenant-scoped uniqueness for identities, roles, teams, and OIDC
  providers, with tenant lineage on versions and mapping tables.
- Authenticated profile password changes and tenant-aware local login.
- Migrations through `e1a6c8f0d642` and a repeatable isolated governance fixture.

### Verified

- Alembic reports `e1a6c8f0d642 (head)`.
- `scripts/test_enterprise_governance_fixture.py` passes JWT login, mapping availability, access
  inheritance, per-team project policy, profile password change, organization creation, archive
  impact/list/restore, and semantic evidence matching without touching the configured database.

### Suggested Commit Message

```text
feat(governance): add tenant RBAC, team project access, and hybrid identity

- enforce JWT, tenant, role, team, and project authorization boundaries
- add custom roles, password lifecycle, onboarding, and OIDC directory sync
- add many-to-many project teams with per-team multi-project policy
- add dependency-aware archive/restore and semantic cross-project traceability
- verify governance flows with an isolated end-to-end fixture
```

## 2026-06-15 - Enterprise analysis control plane and memory-only ingestion

### Added

- Redis-capable enterprise control plane for analysis job state, queue capacity, stale-job
  handling, and shared rate limiting.
- Local in-memory control-plane fallback for development when `REDIS_URL` is not configured or
  Redis is unavailable and `ANALYSIS_REQUIRE_REDIS=false`.
- Cluster-visible job status through the shared control plane, so polling can work across API
  instances when Redis is enabled.
- Redis token-bucket style rate limiting using sorted-set windows and atomic Lua operations.
- Cluster-wide active job capacity using Redis sorted sets and stale-job expiry.
- Configurable stale-job timeout with `ANALYSIS_JOB_STALE_SECONDS`.
- Local Redis configuration via backend `docker-compose.redis.yml`.
- Backend Redis smoke-check script at `scripts/check_redis_control_plane.py`.
- RAM-only source staging with explicit memory budget and TTL.
- Browser-to-API Base64 request flow that avoids FastAPI multipart spooling and server file
  persistence.
- Modality-aware source normalization:
  - Local in-memory extraction for PDF, DOCX, XLSX, TXT, CSV, Markdown, RTF, XML, and BPMN.
  - Vision extraction for supported images.
  - Audio transcription for supported audio.
  - Visual fallback for scanned or low-text PDFs.
- Deterministic source ordering, content hashes, extraction methods, and extraction-status
  metadata.
- Canonical relationship model, stakeholder-aware traceability projection, test intelligence,
  impact analysis, process intelligence, executive translation, and enterprise intelligence.
- Cumulative refinement merge logic so later phases improve intelligence without degrading
  prior confirmed findings.

### Changed

- Moved analysis generation to a generate-and-poll model:
  - `POST /analyze/generate`
  - `GET /analyze/jobs/{job_id}`
- Kept `POST /analyze` and `/analyze-source-materials` as synchronous compatibility routes.
- Replaced process-local-only job state with a control-plane abstraction.
- Replaced local-only rate counters with Redis-backed shared counters when Redis is configured.
- Extended `/analysis-config/limits` to expose actual control-plane metrics, capacity usage, and
  memory-staging metrics.
- Removed multipart upload handling from the analysis source path to avoid server-side temporary
  file spooling.
- Kept uploaded source-file bytes out of Redis and out of PostgreSQL.
- Added `redis==5.2.1` to backend dependencies.
- Added local backend `.env` Redis settings so local runs use Redis when the service is started.

### Operational Notes

- Source-file bytes are not persisted by the application. They temporarily exist in browser
  memory, request memory, bounded API-process RAM, and provider-side processing.
- Redis stores operational metadata only: job status, capacity controls, rate-limit counters,
  and short-lived job results/status payloads.
- PostgreSQL stores project/artifact metadata, canonical analysis JSON, source metadata,
  intelligence edits, and version snapshots.
- With `REDIS_URL` configured, job status and rate limits are shared across API instances.
- Worker execution and source bytes are still memory-local to the instance that accepted the
  request. If that instance dies mid-analysis, the job is marked failed after the stale timeout
  and the user should retry.
- Set `ANALYSIS_REQUIRE_REDIS=true` in enterprise environments when local fallback should be
  treated as a startup failure.

### Suggested Commit Message

```text
feat(analysis): add enterprise control plane and memory-only multimodal ingestion

- add Redis-backed job state, rate limits, capacity controls, and stale-job handling
- preserve no-source-file-storage with bounded RAM staging and deterministic cleanup
- normalize documents, images, audio, and scanned PDFs into provenance-aware evidence
- expose control-plane, queue, limit, and memory-staging metrics
- add canonical relationships, traceability projection, and cumulative intelligence refinement
```
