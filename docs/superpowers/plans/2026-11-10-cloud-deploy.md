# Cloud Deployment and Smoke Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MIRAGE deployable to Vercel, Railway and Supabase as documented, and give operators one command that proves a deployment works end to end.

**Architecture:** One new gateway module (`database_url`) applied in `Settings`; one validation rule; an escape in `migrations/env.py`; `PORT`-aware dual-stack start commands; a standalone smoke script (`scripts/smoke_deploy.py`) built from small check functions; a runbook.

**Tech Stack:** FastAPI, SQLAlchemy 2 + asyncpg, Alembic, httpx, websockets, pytest (asyncio auto), Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-10-cloud-deploy-design.md`

## Global Constraints

- Nothing prints a secret: no password, cookie, ticket, API key or database URL in script output or validation messages.
- Compose behaviour is unchanged: default ports stay 8000/8001/8002.
- Gateway commands run from `apps/gateway` with `python -m pytest`; ruff from the repo root: `ruff check .`.
- Commits: conventional messages, **no** `Co-Authored-By` or session trailers.
- No cloud resources are provisioned and no real credentials are used.

## Review Focus

1. `normalize_database_url` must not decode or re-encode the password: `p%40ss` stays `p%40ss`. Test in Task 1.
2. A `postgres://` URL must reach `DatabaseStore`, not the memory fallback. Test in Task 1.
3. The smoke script must FAIL (not skip) an `http://` URL unless `--allow-insecure`. Test in Task 4.
4. The stream check must send the web origin as `Origin`, or the gateway closes with 1008. Test in Task 4.

---

### Task 1: Database URL normalization

**Files:** create `apps/gateway/app/core/database_url.py`, `apps/gateway/tests/test_database_url.py`; modify `apps/gateway/app/core/config.py`.

- [ ] Write failing tests: `postgres://` and `postgresql://` → `postgresql+asyncpg://`; `sslmode=require` → `ssl=require`; explicit `ssl` wins and `sslmode` is dropped; other params kept in order; encoded password byte-identical; `sqlite+aiosqlite:///x`, `postgresql+asyncpg://...` without sslmode, `memory`, empty string unchanged; `Settings()` with `DATABASE_URL=postgres://...` yields the asyncpg URL.
- [ ] Run, see them fail (module missing).
- [ ] Implement with string operations: split scheme at `://`, split query at the first `?`, rewrite `sslmode` pairs with `str.partition("=")`.
- [ ] Wire into `Settings.database_url` default factory.
- [ ] Tests pass; commit `feat(gateway): accept Supabase connection strings as pasted`.

### Task 2: Alembic `%` escape and transaction-pooler rule

**Files:** modify `apps/gateway/migrations/env.py`, `apps/gateway/app/core/settings_validation.py`, `apps/gateway/tests/test_settings_validation.py`; create `apps/gateway/tests/test_migrations_env.py`.

- [ ] Failing test: running `alembic upgrade head` (via `alembic.command.upgrade` with a `Config` pointing at `alembic.ini`) against a temp SQLite file whose path contains `%25` succeeds and stamps the head.
- [ ] Failing test: production settings with `DATABASE_URL=postgresql+asyncpg://u:p@aws-0-x.pooler.supabase.com:6543/postgres` report an error naming `DATABASE_URL` and port 5432; port 5432 on the same host reports none; the error text does not contain the password.
- [ ] Implement: `config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))`; add the rule using `sqlalchemy.engine.make_url`.
- [ ] Tests pass; commit `fix(gateway): run migrations with encoded passwords, refuse the transaction pooler`.

### Task 3: Railway-ready images

**Files:** modify the three `Dockerfile`s and `apps/gateway/railway.json`; create `apps/gateway/tests/test_deploy_manifests.py`.

- [ ] Failing test: each Dockerfile's `CMD` contains `exec uvicorn`, `--host ${HOST:-0.0.0.0}` and `${PORT:-<default>}`; each `railway.json` uses `DOCKERFILE` and `/health`; gateway health timeout ≥ 30.
- [ ] Update `CMD`s, e.g. gateway: `["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --no-proxy-headers"]`.
- [ ] `python infra/check-compose.py` still passes; tests pass; commit `fix(deploy): honour PORT and HOST for Railway`.

### Task 4: Smoke script

**Files:** create `apps/gateway/scripts/smoke_deploy.py`, `apps/gateway/tests/test_smoke_deploy.py`.

Structure: `CheckResult(name, ok, detail)`; `SmokeConfig` dataclass from args + env; async check functions taking an `httpx.AsyncClient` (and a `connect` callable for the socket); `run_checks(config, client, connect) -> list[CheckResult]`; `main(argv) -> int` prints `PASS|FAIL <name padded> <detail>` and returns 1 on any failure.

- [ ] Failing tests with `httpx.MockTransport` for: gateway health pass/fail; web health; optional upstream health absent → no line, present → checked; real-app route needs `products`; decoy route needs `MIRAGE_DECOY_VARIANT=`; login sets cookie and sends `Origin`; operator API lists the user; stream check sends `Origin`, needs `snapshot`, rejects `ws://` without `--allow-insecure`; `http://` gateway URL fails without the flag; missing credentials fail login/API/stream; database check against a temp SQLite DB at head passes and at an older revision fails; `main` exit codes; captured output never contains password, cookie, ticket or database URL.
- [ ] Implement until green; `ruff check .`.
- [ ] Commit `feat(gateway): end-to-end deployment smoke test`.

### Task 5: Local proof

- [ ] `docker compose -f infra/docker-compose.yml up -d --build` with a scratch `.env` (random secrets) and an override publishing `db` on `127.0.0.1:55432` for the schema check.
- [ ] Create the first admin with `scripts/manage_operators.py` inside the gateway container.
- [ ] Run `smoke_deploy.py --allow-insecure` against `http://localhost:8000`, `http://localhost:3000`; all PASS, exit 0.
- [ ] Negative proof: stop `decoy`, rerun, see `route to decoy` FAIL and exit 1.
- [ ] Tear down; nothing from the scratch `.env` committed.

### Task 6: Runbook and docs

**Files:** create `docs/deployment.md`; modify `docs/configuration.md`, `.env.supabase.example`, `docs/PROPOSAL_ALIGNMENT.md`, `README.md` (link).

- [ ] Runbook: order, per-service variable tables with sources, Railway private vs public, migrations, first admin, smoke test, rollback, limitations.
- [ ] Configuration scaffold section points to the runbook.
- [ ] Proposal row → "Deployable, unverified"; remaining-work item 4 narrowed.
- [ ] Commit `docs: cloud deployment runbook and smoke test`.

### Task 7: PR

- [ ] Push `feat/cloud-deploy`, open PR to `main` with the local smoke output, wait for CI (gateway, decoy, real-app, lint + compose check, web, gitleaks) to go green.
