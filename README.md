# LinguaMentor

AI-Orchestrated Language Proficiency Evaluation and Adaptation System.

LinguaMentor is not a vocabulary app. It teaches, evaluates, adapts, and
predicts exam readiness — autonomously, at scale, aligned to the rubrics
of IELTS, TOEFL, and DELF examinations.

---

## What's in this repo

This is a monorepo. Everything lives here — frontend, API gateway, and all
AI microservices. One repo, multiple independently deployable services.
```
apps/
  web/                    → Next.js 14 frontend (PWA)

services/
  api-gateway/            → Node.js + Fastify (traffic, auth, rate limiting)
  writing-service/        → Python FastAPI (essay scoring, CEFR classification)
  voice-service/          → Python FastAPI (ASR, LLM, TTS pipeline)
  adaptive-engine/        → Python FastAPI (skill vector, SRS scheduling)
  readiness-engine/       → Python FastAPI (band projection, confidence intervals)
  srs-scheduler/          → Python FastAPI (spaced repetition pre-generation)
  calibration-monitor/    → Python FastAPI (Pearson correlation drift alerts)
  ai-orchestrator/        → Python FastAPI (prompt assembly, model routing)

shared/
  db_utils/               → PostgreSQL and Redis connection utilities
                            imported by all Python services via PYTHONPATH

infrastructure/
  docker-compose.yml      → Local dev: PostgreSQL 16 + Redis 7

docs/
  adr/                    → Architecture Decision Records
  prd/                    → Product Requirements Document
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, Tailwind CSS, PWA |
| API Gateway | Node.js, Fastify, TypeScript |
| AI Services | Python 3.12, FastAPI, Uvicorn |
| Primary database | PostgreSQL 16 |
| Cache / session store | Redis 7 |
| Message queue | BullMQ on Redis |
| Container orchestration | Kubernetes + Helm |
| CI/CD | GitHub Actions → Docker multi-stage → Argo Rollouts |
| Observability | Prometheus, Grafana, Loki, Jaeger |
| Secrets | HashiCorp Vault |
| LLM primary | OpenAI GPT-4o |
| LLM fallback | Anthropic Claude 3.5 Sonnet |
| ASR | OpenAI Whisper (primary), Speechmatics (fallback) |
| TTS | ElevenLabs (primary), Azure Neural TTS (fallback) |

---

## Prerequisites

Before running anything locally, make sure you have:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — running
- [Node.js 20 LTS](https://nodejs.org/) or higher
- [Python 3.11+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/)

---

## Running locally

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/linguamentor.git
cd linguamentor
```

### 2. Start infrastructure (PostgreSQL + Redis)
```bash
docker compose -f infrastructure/docker-compose.yml up -d
```

Verify both containers are healthy:
```bash
docker compose -f infrastructure/docker-compose.yml ps
```

Both `lm_postgres` and `lm_redis` should show status `healthy`.

### 3. Initialise the database

Run once on a fresh database:
```bash
docker compose -f infrastructure/docker-compose.yml exec postgres \
  psql -U lm_user -d linguamentor -f /dev/stdin < scripts/init-db.sql
```

### 4. Configure environment variables

Each service has a `.env.example` file. Copy it to `.env` and fill in values:
```bash
# Root — shared variables
cp .env.example .env

# Writing service
cp services/writing-service/.env.example services/writing-service/.env
```

Edit each `.env` file with your local credentials. The database credentials
match what's in `infrastructure/docker-compose.yml`.

### 5. Set PYTHONPATH (required for all Python services)

All Python services import from `shared/`. Python needs to know where the
monorepo root is to resolve that import.

**Windows:**
```bash
set PYTHONPATH=C:\path\to\linguamentor
```

**Mac/Linux:**
```bash
export PYTHONPATH=/path/to/linguamentor
```

Add this to your shell profile (`.bashrc`, `.zshrc`) or system environment
variables so you don't have to set it every session.

See `docs/adr/002-pythonpath-shared-modules.md` for the full reasoning
behind this approach.

### 6. Run a Python service
```bash
cd services/writing-service

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the service
uvicorn app.main:app --reload --port 8001
```

Verify it's running:
```bash
curl http://localhost:8001/health
curl http://localhost:8001/ready
```

---

## Verify all connections
```bash
cd scripts
python test_connections.py
```

All checks should pass before starting any service.

---

## Branching strategy

| Branch | Purpose |
|---|---|
| `main` | Production only. Every commit triggers deployment. |
| `develop` | Integration branch. All features merge here first. |
| `feature/*` | Short-lived. One branch per task. Merged via PR. |

Never commit directly to `main`. Never commit directly to `develop`.
Always work on a `feature/` branch and merge via pull request.

---

## Architecture decisions

Major technical decisions are documented in `docs/adr/`. Read these before
making changes to understand why things are built the way they are.

| ADR | Decision |
|---|---|
| 001 | Secrets management strategy |
| 002 | PYTHONPATH for shared module resolution |

---

## Calibration requirement

No user-facing AI evaluation feature goes live without Pearson correlation
≥ 0.85 confirmed between AI scores and certified human grader scores across
all exam types. This is non-negotiable. See `docs/adr/` and the Master PRD
Section 60 for the full calibration protocol.

---

## Author

TETSOPGUIM Kefoueg Frank P.
Software Engineer — Full Stack | Product Owner | Lead Developer
