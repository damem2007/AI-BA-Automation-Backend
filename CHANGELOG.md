# Changelog

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
