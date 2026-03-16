# Phase 1 — Implementation Log

**Product:** LinguaMentor  
**Phase:** Phase 1 — Core Platform MVP  
**Author:** TETSOPGUIM Kefoueg Frank P.  
**Last Updated:** 2026-03-16  
**Status:** In Progress

---

## Overview

Phase 1 builds the core platform foundation that all user-facing features
sit on top of. It is divided into sequential tasks (P1–P9) where each task
unblocks the next. This document records what was built in each task, the
key decisions made, and the current state.

---

## P1 — Full PostgreSQL Schema

**Branch:** `feature/phase1-P1-database-schema`  
**Migration:** `scripts/migrations/003_phase1_schema.sql`  
**Status:** ✅ Complete

### What was built

Six entity domains covering all 14 PRD entities:

| Domain | Tables |
|---|---|
| Identity & Auth | `users`, `refresh_tokens` |
| Learner Profile | `learner_profiles`, `skill_vectors` |
| AI Evaluation | `writing_sessions`, `speaking_sessions` |
| Adaptive Engine | `daily_sessions`, `score_appeals` |
| Exam & Progress | `exam_attempts`, `exam_sections`, `readiness_snapshots`, `share_events` |
| AI Infrastructure | `ai_model_runs` |

### Key decisions

- All primary keys are UUID v4 — globally unique across services without
  coordination. Required because multiple services create records independently.
- All scores stored as `NUMERIC(4,2)` — never `FLOAT`. Prevents rounding
  drift in calibration comparisons (PRD §28.2).
- All timestamps UTC. No local timezone storage.
- Soft deletes on all user-facing entities. Hard deletes only on GDPR
  erasure requests.
- PII lives in `users` only. All other tables reference `user_id` FK.
- Every AI evaluation references an `ai_model_run_id` FK — no evaluation
  result can exist without a traceable AI execution record (PRD §28.2).
- `ai_model_runs.user_reference_id` is deliberately NOT a FK — anonymized
  records must survive GDPR user deletion without cascading.

---

## P2 — Alembic Async Migration Setup

**Branch:** `feature/phase1-P2-alembic`  
**Status:** ✅ Complete

### What was built

- `alembic/` directory initialized with async template
- `alembic/env.py` configured for asyncpg driver
- SQLAlchemy declarative models created in `app/models/` mirroring
  the full Phase 1 schema — used by Alembic autogenerate only
- `include_object` filter added to `env.py` to prevent Alembic from
  touching Phase 0 calibration tables (owned by raw SQL scripts)
- Baseline revision stamped against the existing schema

### Key decisions

- Runtime queries use raw asyncpg — not SQLAlchemy ORM. Faster and gives
  full control over SQL. SQLAlchemy models exist only for Alembic.
- `include_object` filter: tables that exist in the DB but have no model
  are left alone. Without this, Alembic generates DROP TABLE for all
  Phase 0 calibration and WER tables on every autogenerate run.
- `compare_server_default=True` — Alembic detects server default changes,
  not just column additions and removals.

### Files
```
services/writing-service/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── (baseline revision)
├── alembic.ini
└── app/
    └── models/
        ├── __init__.py
        ├── base.py          ← DeclarativeBase
        └── domain.py        ← All 14 entity models
```

---

## P3 — Auth Service

**Branch:** `feature/phase1-P3-auth` → merged  
**Branch:** `feature/phase1-P3-hardening` → merged  
**Status:** ✅ Complete

### What was built

Complete JWT RS256 authentication system covering all PRD §35.1 and §37.1
requirements.

#### Core auth endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register new account, issue tokens immediately |
| POST | `/api/v1/auth/login` | Authenticate, issue tokens |
| POST | `/api/v1/auth/refresh` | Token rotation — exchange refresh for new access token |
| POST | `/api/v1/auth/logout` | Blacklist access token, revoke refresh token |
| POST | `/api/v1/auth/password/reset` | Request reset email (stub — email not wired) |

#### MFA endpoints (admin accounts)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/auth/mfa/setup` | Initiate TOTP setup, returns QR URI |
| POST | `/api/v1/auth/mfa/setup/verify` | Confirm setup with first TOTP code |
| POST | `/api/v1/auth/mfa/verify` | Complete MFA login with TOTP code |

#### Session management endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/user/sessions` | List all active sessions |
| DELETE | `/api/v1/user/sessions/{id}` | Revoke a specific session |
| DELETE | `/api/v1/user/me` | GDPR erasure |

### Security properties

**Password hashing:** argon2id via `pwdlib`. Memory-hard, time-hard,
current gold standard. Replaces bcrypt/pbkdf2.

**JWT:** RS256 asymmetric signing. Private key signs (writing-service
only), public key verifies (all services). 15-minute access token
lifetime, 7-day refresh token lifetime (PRD §37.1).

**JWT key caching:** Keys loaded from disk once at startup via
`init_jwt_keys()` in lifespan. Cached at module level in `security.py`.
Eliminates per-request disk I/O under load.

**Refresh token storage:** Only SHA-256 hash stored in DB — raw token
sent to client in HTTP-only cookie, never persisted. Compromised DB
cannot replay tokens.

**Token rotation:** Every refresh call revokes the presented token and
issues a new one. Prevents token reuse.

**Theft detection:** If a revoked refresh token is presented, ALL tokens
for that user are immediately revoked. Forces re-login on all devices.

**HTTP-only cookies:** Refresh token stored in `SameSite=Strict` HTTP-only
`Secure` cookie. Not accessible to JavaScript. CSRF-safe.

**Account lockout:** 5 failed login attempts triggers a 15-minute lockout.
`failed_login_attempts` and `locked_until` columns on `users` table.
Counter resets on successful login. Timing-safe: password verification
always runs even when user does not exist — prevents email enumeration
via response time differences.

**IP rate limiting:** Per-IP Redis counters on `/login` (10/15min) and
`/register` (5/hour). Complements account lockout — protects against
distributed attacks across many accounts from one IP.

**JWT blacklist:** Logged-out access tokens stored in Redis with TTL
matching remaining token lifetime. Key: `lm:jwt_blacklist:{token_hash}`.

**MFA:** TOTP-based (pyotp, RFC 6238). Required infrastructure for admin
accounts. Login returns `202 Accepted` + short-lived Redis challenge token
when MFA is enabled. TOTP code required to complete login. Works with
Google Authenticator, Authy, 1Password, etc.

**GDPR erasure:** PII anonymized in `users` table, all refresh tokens
revoked, `ai_model_runs.user_reference_id` cleared. AI audit trail
preserved with personal link severed (PRD §10.5).

### Alembic migration applied

Migration `20260316_add_email_verified_lockout_and_mfa` added to `users`:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `email_verified` | BOOLEAN | FALSE | Gates email-dependent features |
| `failed_login_attempts` | INTEGER | 0 | Brute force tracking |
| `locked_until` | TIMESTAMPTZ | NULL | Lockout expiry |
| `mfa_enabled` | BOOLEAN | FALSE | MFA active flag |
| `mfa_totp_secret` | VARCHAR(64) | NULL | TOTP seed (base32) |

### Files
```
services/writing-service/
├── app/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── router.py       ← All auth + session HTTP endpoints
│   │   ├── schemas.py      ← Pydantic request/response models
│   │   ├── security.py     ← Crypto: argon2id, RS256, TOTP, blacklist
│   │   └── service.py      ← Business logic: register, login, lockout, sessions
│   ├── middleware.py       ← CorrelationIdMiddleware (X-Request-ID)
│   ├── models/
│   │   ├── base.py
│   │   └── domain.py       ← Updated User model with 5 new columns
│   └── main.py             ← Updated: init_jwt_keys(), middleware registered
├── alembic/versions/
│   └── 20260316_add_email_verified_lockout_and_mfa_.py
└── scripts/
    └── generate_jwt_keys.py
```

### Known deferred items

| Item | Reason deferred | Resolution phase |
|---|---|---|
| Email verification flow | Requires SMTP / SendGrid | Phase 2 email integration |
| Password reset implementation | Same dependency | Phase 2 email integration |
| OAuth2 social login | Scope — adds Auth0/Supabase dependency | Post-MVP |
| Suspicious login detection | Requires IP geolocation service | Phase 3+ |

---

## P4 — Writing Evaluation Pipeline

**Status:** ⏳ Pending

---

## P5 — SRS Scheduler + Daily Micro-Session

**Status:** ⏳ Pending

---

## P6 — Score Appeal Flow

**Status:** ⏳ Pending

---

## P7 — Streaming SSE for Chat

**Status:** ⏳ Pending

---

## P8 — AIModelRun Logging

**Status:** ⏳ Pending

---

## P9 — Kubernetes Base Deployment + Helm Charts

**Status:** ⏳ Pending

---

## Current Phase 1 Progress
```
P1 · Full PostgreSQL schema              ✅ COMPLETE
P2 · Alembic async migration setup       ✅ COMPLETE
P3 · Auth service + hardening            ✅ COMPLETE
P4 · Writing evaluation pipeline         ⏳ PENDING
P5 · SRS scheduler + daily micro-session ⏳ PENDING
P6 · Score appeal flow                   ⏳ PENDING
P7 · Streaming SSE for chat              ⏳ PENDING
P8 · AIModelRun logging                  ⏳ PENDING
P9 · Kubernetes + Helm                   ⏳ PENDING
```
