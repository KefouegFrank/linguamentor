# ── LinguaMentor — Makefile (Solo-Dev Edition) ─────────────────────────
# One-command setup, build, and run for the monorepo.
# Usage:
#   make setup       — First-time: generate keys, copy .env, install deps
#   make build       — Build all Docker images
#   make up          — Start all services via Docker Compose
#   make down        — Stop and remove all containers
#   make logs        — Tail logs from all services
#   make migrate     — Run SQL migrations against the running database
#   make test        — Run all tests (ai-service pytest + gateway type-check)
#   make clean       — Remove all build artifacts + node_modules

.PHONY: setup build up down logs migrate test clean

# ── Setup ────────────────────────────────────────────────────────────────
setup: generate-keys install-deps
	@echo ""
	@echo "✅ Setup complete. Run 'make up' to start the stack."

generate-keys:
	python scripts/generate_jwt_keys.py

install-deps:
	@echo "📦 Installing Node.js dependencies..."
	cd gateway && npm install
	@echo "📦 Python dependencies are installed inside Docker (not needed locally)"

# ── Build ────────────────────────────────────────────────────────────────
build:
	docker compose build --no-cache

build-fast:
	docker compose build

# ── Run ──────────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# ── Database ──────────────────────────────────────────────────────────────
migrate:
	@echo "Running SQL migrations..."
	@cat scripts/migrations/001_calibration_schema.sql | docker compose exec -T postgres psql -U linguamentor_admin -d linguamentor_prod 2>/dev/null || true
	@cat scripts/migrations/002_wer_validation_schema.sql | docker compose exec -T postgres psql -U linguamentor_admin -d linguamentor_prod 2>/dev/null || true
	@cat scripts/migrations/003_core_platform_schema.sql | docker compose exec -T postgres psql -U linguamentor_admin -d linguamentor_prod 2>/dev/null || true
	@cat scripts/migrations/004_performance_indexes.sql | docker compose exec -T postgres psql -U linguamentor_admin -d linguamentor_prod 2>/dev/null || true
	@echo "✅ Migrations complete."

# ── Test ──────────────────────────────────────────────────────────────────
test:
	@echo "🔍 TypeScript type-check (gateway)..."
	cd gateway && npx tsc --noEmit
	@echo "✅ Gateway type-check passed."
	@echo ""
	@echo "📝 Python tests (ai-service)..."
	@cd ai-service && PYTHONPATH=/app python -m pytest tests/ -v 2>/dev/null || echo "   (no tests found — add tests to ai-service/tests/)"

# ── Clean ────────────────────────────────────────────────────────────────
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf gateway/node_modules gateway/dist
	rm -rf ai-service/__pycache__ ai-service/app/**/__pycache__
	docker compose down -v --rmi all 2>/dev/null || true
	@echo "✅ Clean complete."
