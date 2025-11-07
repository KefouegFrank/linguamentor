---
description: Repository Information Overview
alwaysApply: true
---

# LinguaMentor Repository Information

## Repository Summary

**LinguaMentor** is a monorepo for an AI-driven language learning platform. It comprises a Node.js/TypeScript backend API, Next.js frontend application, Python FastAPI microservice for AI orchestration, and infrastructure configuration using Terraform and Kubernetes.

## Repository Structure

- **backend/** - Express.js API with JWT authentication, PostgreSQL database via Prisma ORM
- **frontend/** - Next.js 16 React web client with TypeScript
- **ai-service/** - Python 3.11 FastAPI microservice for LLM and AI orchestration
- **infra/** - Infrastructure-as-Code with Terraform, Kubernetes manifests, and CI/CD configuration
- **.anima/** - Design system and workspace configuration

## Projects

### Backend (Node.js/TypeScript)

**Configuration File**: `backend/package.json`

#### Language & Runtime

**Language**: TypeScript  
**Runtime**: Node.js 20+  
**Build System**: TypeScript Compiler (tsc)  
**Package Manager**: pnpm (v10.20.0)

#### Dependencies

**Main Dependencies**:
- `@prisma/client` (^5.7.1) - ORM for PostgreSQL
- `express` (^4.18.2) - Web framework
- `jsonwebtoken` (^9.0.2) - JWT authentication
- `bcryptjs` (^2.4.3) - Password hashing
- `zod` (^3.22.4) - Schema validation
- `helmet` (^7.1.0) - Security headers
- `cors` (^2.8.5) - CORS middleware
- `express-rate-limit` (^7.1.5) - Rate limiting
- `nodemailer` (^6.9.7) - Email service
- `google-auth-library` (^9.4.1) - OAuth support

**Development Dependencies**:
- `typescript` (^5.2.2), `ts-node` (^10.9.1)
- `eslint` with TypeScript support
- `prettier` (^3.1.0) - Code formatting
- `prisma` (5.6.0) - Database migrations
- `nodemon` (^3.0.1) - Development hot-reload

#### Build & Installation

```bash
pnpm install
pnpm run prisma:generate
pnpm run build              # TypeScript compilation to dist/
pnpm run dev               # ts-node development server
pnpm run start             # Node.js production start
```

#### Docker

**Dockerfile**: Multi-stage build with development and production targets  
**Development Image**: Node.js 20-slim with hot-reload via volume mounts  
**Production Image**: Node.js 20-slim with production dependencies only, non-root user  
**Compose**: `docker-compose.dev.yml` (with PostgreSQL 16) and `docker-compose.prod.yml`  
**Ports**: 4000 (backend), 5432 (database)

#### Database

**System**: PostgreSQL 16  
**ORM**: Prisma  
**Schema**: `prisma/schema.prisma` - User authentication, lessons, sessions, assessments, analytics, achievements  
**Key Tables**: users, lessons, sessions, assessments, ai_interactions, analytics_summaries, achievements, admin_logs

### Frontend (Next.js/TypeScript)

**Configuration File**: `frontend/package.json`

#### Language & Runtime

**Language**: TypeScript  
**Runtime**: Node.js 20+ (Next.js 16)  
**Build System**: Next.js Build  
**Package Manager**: pnpm

#### Dependencies

**Main Dependencies**:
- `next` (16.0.1) - React framework
- `react` (19.2.0), `react-dom` (19.2.0)

**Development Dependencies**:
- `typescript` (^5), ESLint, Prettier
- `eslint-config-next` (16.0.1)

#### Build & Installation

```bash
pnpm install
pnpm run build    # Next.js production build
pnpm run dev      # Development server (port 3000)
pnpm run start    # Production server
```

#### Docker

**Dockerfile**: Alpine-based Node.js 20 with pnpm dependencies  
**Port**: 3000  
**Build**: Two-stage (deps isolation, runtime)

### AI Service (Python)

**Configuration File**: `ai-service/requirements.txt`

#### Language & Runtime

**Language**: Python  
**Version**: Python 3.11  
**Package Manager**: pip  
**Virtual Environment**: `.venv` (recommended)

#### Dependencies

**Main Stack**:
- `fastapi` (0.121.0) - Web framework
- `uvicorn` (0.38.0) - ASGI server
- `pydantic` (2.12.4) - Data validation
- `python-dotenv` (1.2.1) - Environment configuration
- `httpx` (0.28.1) - HTTP client
- `PyYAML` (6.0.3) - YAML parsing

#### Build & Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Docker

**Dockerfile**: Python 3.11-slim  
**Entry**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`  
**Port**: 8000  
**User**: Non-root (nobody)

#### Main Entry Point

**File**: `ai-service/app/main.py`  
**Type**: FastAPI application with root health check endpoint

### Infrastructure

**Components**:
- **Terraform/**: Infrastructure-as-Code for cloud deployment
- **k8s/**: Kubernetes manifests for orchestration
- **ci/**: Continuous Integration/Deployment pipeline configuration

## Key Configuration Files

- **Backend**: `tsconfig.json`, `eslint.config.mts`, `docker-compose.dev.yml`, `docker-compose.prod.yml`
- **Frontend**: `tsconfig.json`, `next.config.ts`, `eslint.config.mjs`
- **AI Service**: `requirements.txt`, `Dockerfile`
- **Repository**: Root-level `.gitignore`, `.gitattributes`

## Development Workflows

**Local Development**:
- Backend: `pnpm run dev` (requires PostgreSQL running)
- Frontend: `pnpm run dev` (localhost:3000)
- AI Service: `python -m venv .venv && pip install -r requirements.txt && uvicorn app.main:app`

**Docker Development**:
- Backend: `pnpm run dev:docker` (orchestrates backend + PostgreSQL)
- Frontend: Docker build with Alpine base
- AI Service: Docker with Python 3.11

**Code Quality**:
- **Backend**: `pnpm run lint` (ESLint), `pnpm run format` (Prettier)
- **Frontend**: `pnpm run lint` (ESLint)
