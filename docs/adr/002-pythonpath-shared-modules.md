# ADR 002 — PYTHONPATH for Shared Module Resolution

**Date:** 2026-03-11  
**Status:** Accepted  
**Author:** TETSOPGUIM Kefoueg Frank P.

---

## Context

LinguaMentor is a Python monorepo with multiple independent microservices
that share common utilities — specifically database and Redis connection
logic in `shared/db_utils/`. Every Python service needs to import from
`shared/` without duplicating the code.

The challenge: Python's import system resolves modules relative to the
paths in `sys.path`. When a service runs from its own directory
(`services/writing-service/`), Python has no automatic knowledge that
the monorepo root exists or that `shared/` lives there.

---

## What we tried first

**pip editable install (`pip install -e`)**

The initially attempted approach was to package `shared/` as an installable
Python package with a `pyproject.toml` and install it into each service's
virtual environment in editable mode (`pip install -e ../../shared`).

This approach failed on Python 3.12 on Windows. The newer setuptools
editable install mechanism registers a path hook
(`__editable__.linguamentor_shared-0.1.0.finder.__path_hook__`) rather
than adding the source directory directly to `sys.path`. The hook maps
the package under the name `linguamentor_shared` (the project name with
underscores) rather than `shared` (the actual folder name Python needs
to resolve the import `from shared.db_utils.connection import ...`).

Multiple variations of `pyproject.toml` configuration were attempted.
None resolved the name mismatch reliably across Python 3.12 on Windows.

---

## Decision

Use `PYTHONPATH` to add the monorepo root to Python's module search path.
```bash
# Windows
set PYTHONPATH=C:\path\to\linguamentor

# Mac/Linux
export PYTHONPATH=/path/to/linguamentor
```

With the monorepo root in `PYTHONPATH`, Python finds `shared/` as a
top-level package and all imports resolve correctly:
```python
from shared.db_utils.connection import create_postgres_pool  # works
```

---

## Why this is the correct long-term approach

`PYTHONPATH` is not a workaround — it is the standard mechanism Python
provides for exactly this use case. It is how production systems built
on Python monorepos solve shared module resolution:

- **Docker:** `ENV PYTHONPATH=/app` in the Dockerfile. Set once,
  works for every service built from that base image.

- **Kubernetes:** Set in the pod spec environment variables block.
  Consistent across all replicas and environments.

- **GitHub Actions CI:** Set in the workflow env block. Every test
  run has the correct path without any pip install step.

- **Local development:** Set once in the shell profile (`.bashrc`,
  `.zshrc`, or Windows system environment variables) and never
  think about it again.

The editable install approach adds a pip install step to every
environment setup and introduces a dependency on setuptools behaviour
that changed between versions. `PYTHONPATH` has no such dependency —
it is a Python core feature that has not changed since Python 2.

---

## Consequences

- Every developer working on this project must set `PYTHONPATH` to
  the monorepo root before running any Python service. This is
  documented in the README and in each service's `.env.example`.

- Every `Dockerfile` for a Python service must include:
  `ENV PYTHONPATH=/app`
  where `/app` is the directory inside the container that contains
  both `services/` and `shared/`.

- Every GitHub Actions workflow that runs Python services or tests
  must set `PYTHONPATH` in the workflow environment.

- The `pyproject.toml` in `shared/` is retained for documentation
  purposes but is not used for installation. It describes the
  package metadata and dependencies that consumers of `shared/`
  must have installed.
