# ADR 001 — Secrets Management Strategy

**Date:** 2026-03-11  
**Status:** Accepted  
**Author:** TETSOPGUIM Kefoueg Frank P.

---

## Context

LinguaMentor requires secrets to operate — database passwords, API keys for
OpenAI, Anthropic, ElevenLabs, Speechmatics, and JWT signing keys. These
secrets must be accessible to services at runtime but must never appear in
source code, Git history, Docker images, or any file that could be
accidentally exposed.

Three options were considered:

**Option A — Hardcode in source code**  
Immediately disqualified. Secrets in source code are visible to anyone with
repository access, cannot be rotated without a code change, and will appear
permanently in Git history even after deletion.

**Option B — .env files committed to Git**  
Also disqualified. Slightly less obvious than hardcoding but the same
fundamental problem — the secret lives in the repository.

**Option C — .env files locally, HashiCorp Vault in production**  
Selected. Gives developers a frictionless local experience while maintaining
production-grade secret management in staging and production environments.

---

## Decision

**Local development:** `.env` files on the developer's machine only.
Never committed to Git. The `.gitignore` at the monorepo root blocks all
`.env` files. Each service has a `.env.example` file committed to Git that
documents required variable names with no values — this is the contract
between the codebase and its operators.

**Production and staging:** HashiCorp Vault. Services authenticate to Vault
using their Kubernetes service account identity (via Vault's Kubernetes auth
method) and receive secrets at pod startup. No secrets exist in any config
file, Docker image, or Kubernetes manifest in production.

**The abstraction rule:** Application code reads secrets exclusively from
environment variables using `os.getenv()` or `pydantic-settings`. It never
reads from files directly and never assumes the source of the variable.
This means the same code works locally (where dotenv populates the
variables) and in production (where Vault/Kubernetes populates them).

---

## Consequences

- Every service must have a `.env.example` file maintained alongside its
  code. When a new environment variable is added, `.env.example` must be
  updated in the same commit.

- New developers cloning the repo must copy `.env.example` to `.env` and
  fill in values before running any service. The README documents this step.

- HashiCorp Vault must be provisioned before any service is deployed to
  staging. This is a Phase 1 infrastructure task — not deferred to later.

- Secret rotation in production requires updating the value in Vault only.
  No code changes, no redeployment, no Git commits. Services pick up rotated
  secrets on next pod restart.

- The `load_dotenv(override=False)` pattern is used in all services.
  `override=False` ensures that variables already set in the environment
  (by Vault or Kubernetes) are never overwritten by a stale `.env` file
  that might exist on the container filesystem.
