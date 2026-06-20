# BA Artifacts Backend

## Local Redis

Enterprise-mode analysis coordination uses Redis for shared job status, rate limits, queue
capacity, and stale-job detection. Source-file bytes are not stored in Redis.

Option A, Docker Compose from the backend directory:

```bash
docker compose -f docker-compose.redis.yml up -d redis
```

Option B, Homebrew on macOS:

```bash
brew install redis
brew services start redis
```

Backend `.env` should include:

```env
REDIS_URL=redis://localhost:6379/0
ANALYSIS_REQUIRE_REDIS=false
ANALYSIS_JOB_STALE_SECONDS=7200
```

Use `ANALYSIS_REQUIRE_REDIS=true` in enterprise-like local testing when the backend should fail
fast if Redis is unavailable.

Verify the backend is using Redis:

```bash
redis-cli ping
venv/bin/python scripts/check_redis_control_plane.py
```

Then run the API normally, for example:

```bash
venv/bin/uvicorn app.main:app --reload
```
