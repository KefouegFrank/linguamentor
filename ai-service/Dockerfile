# ── LinguaMentor AI Service ────────────────────────────────────────────
# Multi-stage build: Python 3.11 slim, FastAPI + Uvicorn
# Exposes port 8000, connects to Postgres + Redis
#
# Build context is the monorepo root so we can COPY shared/.
# Source paths are prefixed with ai-service/.

FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY ai-service/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime image ───────────────────────────────────────────────────────
FROM python:3.11-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/usr/bin/tini", "--"]

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH \
    PYTHONPATH=/app

COPY ai-service/alembic.ini ./alembic.ini
COPY ai-service/alembic/ ./alembic/
COPY ai-service/app/ ./app/
COPY shared/ ./shared/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
