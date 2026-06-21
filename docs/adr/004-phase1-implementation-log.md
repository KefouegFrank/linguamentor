# Phase 1 — Implementation Log

**Product:** LinguaMentor  
**Phase:** Phase 1 — Core Platform MVP  
**Author:** TETSOPGUIM Kefoueg Frank P.  
**Last Updated:** 2026-06-21  
**Status:** ~55% Complete (Solo-Dev Topology)

---

## Overview

Phase 1 builds the core platform foundation. This log was originally written
for the K8s-era microservice topology. On 2026-06-18 the project was
re-baselined to the Solo-Dev topology (see Solo-Dev PRD). The tasks below
have been updated to reflect the actual current implementation and the
correct solo-dev directory structure.

---

## Topology Change Note

All code now lives at the monorepo root, not under `services/`:

| Old path | New path |
|---|---|
| `services/api-gateway/` | → `gateway/` |
| `services/writing-service/` | → `ai-service/` |
| `services/` (empty parent) | → deleted |
| `gateway-node/` | → deleted (superseded by `gateway/`) |
| `ai-service-python/` | → deleted (skeleton merged into `ai-service/`) |
| `worker-bullmq/` | → deleted (worker co-located in `ai-service/app/queue/`) |

---

## P1 — Full PostgreSQL Schema

**Migrations:** `scripts/migrations/003_core_platform_schema.sql`,  
`scripts/migrations/004_performance_indexes.sql`  
**Alembic:** `ai-service/alembic/versions/` (3 migration files)  
**Status:** ✅ Complete

### What was built

Six entity domains, 14+ tables:

| Domain | Tables |
|---|---|
| Identity & Auth | `users`, `refresh_tokens` |
| Learner Profile | `learner_profiles`, `skill_vectors` |
| AI Evaluation | `writing_sessions`, `speaking_sessions` |
| Adaptive Engine | `daily_sessions`, `score_appeals` |
| Exam & Progress | `exam_attempts`, `exam_sections`, `readiness_snapshots`, `share_events` |
| AI Infrastructure | `ai_model_runs` |

### Key decisions

- All PKs are UUID v4. Scores as `NUMERIC(4,2)` (never float). All timestamps UTC.
- Soft deletes on user-facing entities. Hard deletes only on GDPR erasure.
- PII lives in `users` only. `ai_model_runs.user_reference_id` is NOT a FK
  (survives GDPR deletion without cascading).

---

## P2 — Alembic Async Migration Setup

**Location:** `ai-service/alembic/`  
**Status:** ✅ Complete

### What was built

- `alembic/` initialized with async template, asyncpg driver in `env.py`
- SQLAlchemy declarative models in `ai-service/app/models/domain.py` — for Alembic only
- `include_object` filter prevents Alembic from touching Phase 0 calibration tables
- 3 migration versions applied

---

## P3 — Auth Service

**Location:** `ai-service/app/auth/`  
**Status:** ✅ Complete

Complete RS256 JWT auth system covering all PRD §35.1 and §37.1 requirements.

| Endpoint | Description |
|---|---|
| `POST /api/v1/auth/register` | Register + issue tokens |
| `POST /api/v1/auth/login` | Authenticate + issue tokens |
| `POST /api/v1/auth/refresh` | Token rotation |
| `POST /api/v1/auth/logout` | Blacklist + revoke |
| `POST /api/v1/auth/password/reset` | Stub — email not wired |
| `GET /api/v1/auth/mfa/setup` | TOTP setup |
| `POST /api/v1/auth/mfa/setup/verify` | Confirm TOTP |
| `POST /api/v1/auth/mfa/verify` | MFA login completion |
| `GET /api/v1/user/sessions` | List active sessions |
| `DELETE /api/v1/user/sessions/{id}` | Revoke session |
| `DELETE /api/v1/user/me` | GDPR erasure |

**Security:** argon2id passwords, RS256 JWT (15-min access, 7-day refresh),
refresh rotation with theft detection, account lockout (5 failures, 15-min),
IP rate limiting (10/login, 5/register), JWT blacklist in Redis, MFA for admin.

---

## P4 — Writing Evaluation Pipeline

**Status:** ✅ Complete

### What was built

- `POST /api/v1/writing/evaluate` — async essay submission (returns `job_id`, 202 Accepted)
- `GET /api/v1/writing/result/{session_id}` — poll for scores
- BullMQ worker with 3 retries, exponential backoff, DLQ routing
- Idempotent processing (WHERE status='pending' guard prevents double-processing)
- Skill vector update after each evaluation (EMA with α=0.2, PRD §23.1)
- Readiness snapshot creation after each evaluation
- Calibration transparency: version + correlation shown on every report
- Free tier monthly limit: 3 evaluations/mo (PRD §5.1)
- Minimum word count per exam type (IELTS 150, TOEFL 100, DELF 80)

### Key files
```
ai-service/app/routers/writing.py       ← POST /evaluate, GET /result
ai-service/app/queue/worker.py          ← BullMQ processor + DLQ
ai-service/app/queue/queues.py          ← 5 queues + default job options
ai-service/app/writing/cefr.py          ← Band → CEFR mapping
ai-service/app/writing/skill_vector.py  ← EMA update logic
```

---

## P5 — SRS Scheduler + Daily Micro-Session

**Status:** ⏳ Pending — queue defined, no generation logic

Queue `lm:srs:generation` exists in `queues.py`. Skill vector has SRS interval
fields per dimension. No daily-session generation logic written yet.

---

## P6 — Score Appeal Flow

**Status:** ✅ Complete

- `POST /api/v1/writing/appeal/{session_id}` — triggers secondary evaluation
- Queue `lm:writing:appeal` with priority backoff (2 retries, fixed 3s delay)
- Uses different prompt config + temperature for secondary scoring
- Unique constraint prevents duplicate appeals per session

---

## P7 — Streaming SSE for Chat

**Status:** ❌ Not started — all AI responses are async/poll. Required for Phase 2.

---

## P8 — AIModelRun Logging

**Status:** ✅ Complete

Full traceability per PRD §11.5: model_name, model_version, prompt_hash,
task_type, latency_ms, calibration_version, persona_config, provider_name.
NOTE: `input_token_count` and `output_token_count` are written as None by the
worker — needs wiring to populate from provider response.

---

## P9 — Deployment & Infrastructure

**Status:** ✅ Complete (Solo-Dev Edition)

**What was built:**
- `docker-compose.yml` with 4 services (gateway, ai-service, postgres, redis)
- Multi-stage Dockerfiles for `gateway/` and `ai-service/`
- Docker secrets for JWT key pair
- Healthcheck on every service
- Makefile with setup/build/up/down/logs/migrate/test targets
- `gateway/Dockerfile`: Node 20 Alpine, Fastify, 2-stage build
- `ai-service/Dockerfile`: Python 3.11-slim, FastAPI + Uvicorn, 2-stage build
- Gateway proxy routes consolidated to single ai-service upstream
- Prompt-injection filter (OWASP LLM01:2025 patterns)

### P9 replaced by Solo-Dev infra

| Old (K8s) | New (Solo-Dev) |
|---|---|
| Kubernetes + Helm + Terraform | Docker Compose + Coolify/Dokploy |
| 13 microservices | 3 units (gateway, ai-service, worker) |
| HPA / pod auto-scaling | Vertical scale + documented horizontal path |
| ArgoCD / blue-green | Health-checked rolling restart |
| HashiCorp Vault | Coolify/Dokploy secrets + Docker secrets |

---

## Current Phase 1 Progress
```
P1 · Full PostgreSQL schema              ✅ COMPLETE
P2 · Alembic async migration setup       ✅ COMPLETE
P3 · Auth service + hardening            ✅ COMPLETE
P4 · Writing evaluation pipeline         ✅ COMPLETE
P5 · SRS scheduler + daily micro-session ⏳ PENDING
P6 · Score appeal flow                   ✅ COMPLETE
P7 · Streaming SSE for chat              ❌ NOT STARTED
P8 · AIModelRun logging                  ✅ COMPLETE (token counts need wiring)
P9 · Docker Compose + deployment         ✅ COMPLETE (Solo-Dev Edition)
```

## Remaining Phase 1 Items (beyond original P1-P9)
- 4D CEFR placement endpoint (POST /placement)
- Drift monitor cron (weekly correlation check)
- Persona prompt injection in production mode
- Frontend (Next.js PWA) — largest remaining gap
- Per-user AI cost ceiling
- Tests (zero test files exist)
- Production CORS config
- Circuit breaker for AI provider failover
