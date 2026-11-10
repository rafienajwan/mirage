# Cloud Deployment and Smoke Test — Design

Item 4 of "Remaining Proposal Work" in `docs/PROPOSAL_ALIGNMENT.md`: provision
Vercel, Railway and Supabase, run migrations, verify private and public
networking, and run an end-to-end HTTPS/WSS smoke test.

This change makes the repository deployable and testable. Provisioning the
accounts and running the test against live services is left to the owner of
those accounts; the proposal row stays unverified until that run passes.

## Problem

Measured on 2026-11-10 against `main` (`3df9a73`).

1. **Railway port.** Every Dockerfile hard-codes its port (8000, 8001, 8002).
   Railway injects `PORT` and routes its public domain and health check there.
   A service that ignores `PORT` only works if someone sets a matching target
   port by hand in the dashboard, which the docs never mention.
2. **Railway private network.** The two upstreams bind `0.0.0.0` (IPv4 only)
   with no way to change it. Railway's private network
   (`<service>.railway.internal`) is IPv6 in older environments, so the
   gateway cannot reach the real app or the decoy there.
3. **Supabase connection strings do not work as pasted.**
   - The dashboard gives `postgresql://` or `postgres://`. With
     `postgresql://` SQLAlchemy picks psycopg2, which is not installed. With
     `postgres://` it is worse: `app/storage/__init__.py` does not recognise
     the scheme and silently falls back to the in-memory store, so a
     "working" gateway loses every event on restart.
   - The strings carry `?sslmode=require`. SQLAlchemy's asyncpg dialect passes
     `sslmode` straight to `asyncpg.connect`, which has no such argument, so
     every connection fails.
   - Supabase passwords are often URL-encoded (`%40`, `%2F`). Alembic's
     `set_main_option` runs the URL through `ConfigParser` interpolation, so a
     `%` aborts `alembic upgrade head` and the gateway never starts.
   - The transaction pooler (port 6543) breaks asyncpg prepared statements.
     Nothing stops it from being configured.
4. **Supabase publishes the tables.** Supabase's Data API serves every table
   in the `public` schema, and its default grants let the `anon` role (whose
   key ships to browsers by design) read them. Alembic creates all MIRAGE
   tables there, including `operators.password_hash` and the attack log.
5. **Nothing proves a deployment works.** There is no end-to-end check for
   health, routing, the dashboard stream, operator login or schema version.
   `smoke_ml_shadow.py` tests ML scoring in-process only.
6. **No runbook.** `docs/configuration.md` has a short "Cloud Deployment
   Scaffold" section; there is no provisioning order, no per-service variable
   list, no first-admin step for Supabase, and no smoke-test step.

## Decisions

### Ports and binding

- Every image starts with
  `exec uvicorn ... --host ${HOST:-0.0.0.0} --port ${PORT:-<default>}` through
  `sh -c`. `exec` keeps uvicorn as PID 1 so it receives `SIGTERM`.
- The bind host is a variable, not `::`. Binding `::` was tried first and
  broke Compose: asyncio sets `IPV6_V6ONLY` on IPv6 listeners, so uvicorn on
  `::` refuses IPv4, and Docker port publishing and service-to-service calls
  use IPv4. The container health checks still passed (they hit `localhost`,
  which resolves to `::1`), so only the smoke test caught it. On Railway the
  two private upstreams set `HOST=::` for the IPv6 private network.
- Defaults stay 8000/8001/8002, so Compose and local runs are unchanged.
- `railway.json` keeps `/health`; timeout grows to 30 s for the gateway, whose
  start runs `alembic upgrade head` first.

### Database URL normalization

New `app/core/database_url.py`, `normalize_database_url(url) -> str`, applied
by `Settings.database_url`:

- `postgres://` and `postgresql://` become `postgresql+asyncpg://`;
  `postgresql+asyncpg://`, SQLite and the `memory` sentinel pass through.
- `sslmode` becomes asyncpg's `ssl` with the same value (`require`,
  `verify-full`, ...). An explicit `ssl` wins over `sslmode`.
- Other query parameters, the user, the URL-encoded password, host, port and
  database are preserved byte for byte (string surgery on the scheme and query
  only, never a decode/re-encode of credentials).

`migrations/env.py` escapes `%` as `%%` before `set_main_option`.

Production validation gains one rule: a `DATABASE_URL` whose port is `6543`
on a `*.pooler.supabase.com` host fails startup with a message pointing at the
session pooler (port 5432). The rule names the variable only, never its value.

### Row-level security

Migration `0012` enables row-level security on every table in the current
schema when the dialect is PostgreSQL (no-op on SQLite). With no policies,
`anon` and `authenticated` see no rows; the gateway connects as the table
owner, which RLS does not restrict. The runbook also tells operators to turn
off the Data API, since MIRAGE never uses it.

### Smoke test

`apps/gateway/scripts/smoke_deploy.py`. Standard library plus `httpx`,
`websockets` (already installed via `uvicorn[standard]`), and SQLAlchemy and
Alembic for the schema check, so it runs from a gateway checkout without new
dependencies. It runs these checks in order and prints one line each:

```
PASS gateway health          https://gw.example/health -> 200
FAIL web health              https://web.example/login -> 502
```

| Check | How |
| --- | --- |
| `gateway health` | `GET <gateway>/health` returns 200 and `status` is `ok`/`healthy` |
| `web health` | `GET <web>/login` returns 200 |
| `real-app health`, `decoy health` | `GET <url>/health`, only when a direct URL is given; on Railway they are private and covered by the routing checks |
| `route to real app` | `GET <gateway>/api/v1/proxy/api/products` returns 200 JSON with a `products` list (only the real app serves that) |
| `route to decoy` | `GET <gateway>/api/v1/proxy/.env` with a scanner user agent returns 200 text containing `MIRAGE_DECOY_VARIANT=` (only the decoy writes that) |
| `operator login` | `POST <web>/api/auth/login` with `Origin: <web>` returns 200 and sets the `mirage_operator_session` cookie |
| `operator API` | `GET <web>/api/gateway/operators` with that cookie returns 200 and lists the login user; this crosses web bridge → gateway → database |
| `dashboard stream` | `GET <web>/api/dashboard-stream-ticket` returns a `wss://` URL (or `ws://` with `--allow-insecure`) and a ticket; connecting with `Origin: <web>` yields a `snapshot` message within 10 s |
| `database migrated` | `SELECT version_num FROM alembic_version` over `DATABASE_URL` equals the single Alembic head in `apps/gateway/migrations` |

Rules:

- Inputs come from flags or the matching environment variables:
  `SMOKE_GATEWAY_URL`, `SMOKE_WEB_URL`, `SMOKE_REAL_APP_URL`,
  `SMOKE_DECOY_URL`, `SMOKE_OPERATOR_USERNAME`, `SMOKE_OPERATOR_PASSWORD`,
  `DATABASE_URL`. The password is read only from the environment, never a
  flag, so it stays out of shell history and process listings.
- HTTPS and WSS are required unless `--allow-insecure` is passed (for the
  local Compose proof). An `http://` URL without the flag is a FAIL, not a
  silent downgrade.
- A missing input fails its check; every check always prints a line; exit
  status is 1 if any check failed, else 0. Output never contains secrets: the
  password, cookie, ticket and database URL are never echoed (the database
  check prints only host and revision).
- The routing checks send two proxy requests, and the decoy request is
  recorded as an attack event. The runbook says so.

Unit tests drive the check functions with `httpx.MockTransport` and a fake
socket factory; the database check runs against a temporary SQLite database
stamped with the head revision. The Compose stack is the integration proof.

### Runbook

`docs/deployment.md`: provisioning order (Supabase → Railway upstreams →
Railway gateway → Vercel → gateway `FRONTEND_ORIGIN` update → first admin →
smoke test), every variable per service with its source, private versus
public networking on Railway, migrations against Supabase, first admin, the
smoke test, and the known limitations (Vercel login throttle, Railway proxy
addresses and `TRUSTED_PROXIES`). `docs/configuration.md`'s scaffold section
shrinks to a pointer at the runbook. `.env.supabase.example` gains the missing
variables and a smoke-test block.

### Proposal row

`PROPOSAL_ALIGNMENT.md` moves the deployment row from "Configuration scaffold"
to "Deployable, unverified": manifests, runbook and smoke test exist and the
smoke test passes against the local Compose stack; no live run yet. The
remaining-work item stays, narrowed to "provision and run the smoke test".

## Out of scope

- Provisioning, live credentials, custom domains.
- Running migrations from CI or a release step (the gateway runs them on
  start, as today).
- Supabase transaction-pooler support.
- A shared login throttle for serverless Vercel.

## Testing

- `test_database_url.py`: scheme rewrite, `sslmode` translation, encoded
  password preserved, pass-throughs, explicit `ssl` precedence.
- Migration env: a URL with `%` survives `set_main_option`.
- `test_settings_validation.py`: transaction-pooler rule.
- `test_smoke_deploy.py`: each check passes and fails as specified; exit code;
  no secret appears in output; insecure URLs rejected without the flag.
- `test_deploy_manifests.py`: each Dockerfile honours `PORT` and `HOST`,
  uses `exec`; each `railway.json` has a `/health` check.
- Local proof: Compose stack up, first admin created, smoke test passes with
  `--allow-insecure`; output pasted into the PR.
