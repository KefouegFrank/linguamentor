# ADR 001 — Secrets Management Strategy

**Date:** 2026-03-11  
**Last Updated:** 2026-06-21  
**Status:** Accepted (Updated — Solo-Dev Edition)  
**Author:** TETSOPGUIM Kefoueg Frank P.

---

## Context

LinguaMentor requires secrets to operate — database passwords, API keys for
OpenAI, Anthropic, and JWT signing keys. These secrets must be accessible to
services at runtime but must never appear in source code, Git history, or
Docker images.

Three options were considered:

**Option A — Hardcode in source code**  
Immediately disqualified. Secrets in source code are visible to anyone with
repository access and appear permanently in Git history.

**Option B — .env files committed to Git**  
Also disqualified. The same fundamental problem as Option A.

**Option C — .env files locally, platform secret store in production**  
Selected. Gives developers frictionless local experience with production-grade
secret management via Coolify/Dokploy secrets or Docker secrets.

---

## Decision (Solo-Dev Edition)

**Local development:** `.env` file at monorepo root, never committed to Git.
`.gitignore` blocks it. `.env.example` is committed and serves as the contract
between code and operators.

**Production (revised):** Coolify/Dokploy built-in secret store, NOT HashiCorp Vault.
Vault requires a dedicated server and adds operational complexity that is
unjustified for a solo operator. Docker Compose secrets (wired in
`docker-compose.yml`) handle the single-box deployment. Coolify/Dokploy secrets
handle the managed deployment. Both inject values as environment variables —
the application code never changes.

**The abstraction rule (kept):** Application code reads secrets exclusively from
environment variables via `pydantic-settings`. It never reads files directly
and never assumes the source of the variable. The same code works locally
(where `.env` populates variables) and in production (where Coolify/Dokploy
or Docker secrets populate them).

---

## Consequences

- `.env.example` must be updated in the same commit as any new env variable.
- New developers: `cp .env.example .env`, fill values, `make setup`.
- Docker Compose uses `secrets:` block for JWT key pair mounted from `./secrets/`.
- No HashiCorp Vault to provision — Coolify/Dokploy secret store is the target.
- Secret rotation in production: update Coolify/Dokploy secret, restart service.
