# LinguaMentor AI Service

Production-grade FastAPI microservice that executes AI workloads (LLM, ASR, TTS, translation, summarization, grammar, scoring) for LinguaMentor. It consumes jobs from Redis and reports results back to the backend via a secure internal webhook.

## Features
- Async FastAPI app with `/health` and `/metrics` (Prometheus)
- Redis worker consuming list `ai-jobs` with backoff and configurable concurrency
- Modular handlers (LLM/ASR/TTS/echo) with provider adapters
- Secure callbacks to backend with `x-service-token` and idempotency
- Structured JSON logging (privacy-friendly hashing)

## Configuration (env vars)
- `REDIS_URL` (default `redis://redis:6379/0`)
- `REDIS_QUEUE_NAME` (default `ai-jobs`)
- `BACKEND_URL` (default `http://backend:4000`)
- `INTERNAL_SERVICE_TOKEN` (required in production)
- `MODEL_PROVIDER` (default `openai`)
- `OPENAI_API_KEY` (optional; enables OpenAI LLM)
- `WORKER_CONCURRENCY` (default `4`)
- `DISABLE_WORKER` (default `false`; set `true` to skip worker)
- `LOG_LEVEL` (default `info`)

## Local Run

API only (no Redis, to validate endpoints):
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
set DISABLE_WORKER=true
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

With Redis:
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
docker run --name redis -p 6379:6379 -d redis:7
set REDIS_URL=redis://localhost:6379/0
set BACKEND_URL=http://localhost:4000
set INTERNAL_SERVICE_TOKEN=dev-token
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Queue Contract
Push a JSON envelope to Redis list `ai-jobs`:
```
{
  "jobId": "<uuid>",
  "type": "llm|asr|tts|translate|summarize|grammar|score|echo",
  "payload": { ... }
}
```

The service processes the job and calls backend `POST /jobs/webhook` with headers:
- `x-service-token: INTERNAL_SERVICE_TOKEN`
- `x-timestamp: <ms since epoch>`
- `x-idempotency-key: <uuid>`
- `X-INTERNAL-TOKEN: INTERNAL_SERVICE_TOKEN` (compat)

Body:
```
{ "jobId": "...", "status": "completed|failed", "result?": {}, "error?": "...", "metadata?": {} }
```

## Docker
```
docker build -t lingua-ai-service ./ai-service
docker run --rm -p 8000:8000 \
  -e REDIS_URL=redis://host.docker.internal:6379 \
  -e BACKEND_URL=http://host.docker.internal:4000 \
  -e INTERNAL_SERVICE_TOKEN=dev-token \
  lingua-ai-service
```

Runs as non-root and uses `python:3.11-slim` base.

## Docker Compose (Dev)
```
cd ai-service
copy .env.example .env
docker compose up --build
```

Health: `http://localhost:8000/health`
Metrics: `http://localhost:8000/metrics`

To run API-only via compose, set `DISABLE_WORKER=true` in `.env`.

## Notes
- Do not log raw user data; logs include hashes only for sensitive fields.
- External model calls use async httpx with exponential backoff and timeouts.
- Workers are stateless and horizontally scalable.
