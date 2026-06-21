# ADR 002 — PYTHONPATH for Shared Module Resolution

**Date:** 2026-03-11  
**Last Updated:** 2026-06-21  
**Status:** Accepted  
**Author:** TETSOPGUIM Kefoueg Frank P.

---

## Context

LinguaMentor is a Python monorepo with shared utilities in `shared/db_utils/`.
The Python AI service (`ai-service/`) needs to import from `shared/` without
duplicating the code. Since the restructuring to solo-dev topology, the service
lives at `ai-service/` rather than `services/writing-service/`, but the same
PYTHONPATH approach applies.

---

## Decision

Use `PYTHONPATH` to add the monorepo root to Python's module search path:
```bash
export PYTHONPATH=/home/frank/frank-workspace/linguamentor
```

With the monorepo root in `PYTHONPATH`, Python finds `shared/` as a
top-level package:
```python
from shared.db_utils.connection import create_postgres_pool  # works
```

`PYTHONPATH` is the standard mechanism Python provides for this use case:
- **Docker:** `ENV PYTHONPATH=/app` in the Dockerfile (pointing to monorepo root)
- **Coolify/Dokploy:** Set in the service environment
- **Local development:** Set once in shell profile

---

## Consequences

- Every Python service Dockerfile must include: `ENV PYTHONPATH=/app`
- The `ai-service/Dockerfile` correctly sets this.
- No pip editable install needed — avoids setuptools compatibility issues.
