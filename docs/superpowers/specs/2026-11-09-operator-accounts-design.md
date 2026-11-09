# Per-Analyst Operator Accounts — Design

Sub-project 5 of the repository hardening effort (2026-11-06 review).
Depends on sub-project 3 (deployment hardening) and sub-project 4 (ML
pipeline integrity, which made analyst labels the promotion yardstick).

## Goal

Every analyst signs in as themselves, every state-changing operator action
records who took it, and disabling an account ends that analyst's access on
their next request.

## Problem

Measured on 2026-11-09 against `main` (`7b7667f`).

1. **One shared password.** The web login compares one
   `MIRAGE_OPERATOR_PASSWORD`. The session cookie holds `exp`, `iat` and
   `nonce`, no identity.
2. **The gateway never knows who acts.** The bridge
   (`apps/web/src/app/api/gateway/[...path]/route.ts`) adds the shared
   `MIRAGE_API_KEY`; `require_api_key` returns nothing about the caller.
3. **Unattributed labels.** `EventModel` stores `analyst_label`,
   `analyst_note` and `labeled_at`, not who labeled. Since sub-project 4 the
   promotion gate depends on these labels.
4. **Unattributed case work.** `ActorCaseModel.assigned_to` is free text and
   case updates do not record who made them.
5. **No audit trail.** Retraining and canary revocation leave no record of who
   triggered them.
6. **No revocation.** Removing one analyst means rotating the shared password
   for everyone.

## Decisions

| Topic | Decision |
|---|---|
| Account store | New `operators` table in the gateway database. |
| Password hashing | `hashlib.scrypt`, n=2^14, r=8, p=1, 16-byte random salt, 32-byte key; stored as `scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>`; compared with `hmac.compare_digest`. No new dependency. |
| Password policy | At least 12 characters, at most 256. |
| Username | `^[a-z0-9][a-z0-9._-]{1,31}$`, stored lower-case, unique. `api-key` is reserved. |
| Roles | `analyst`: read everything, label events, open and update cases, simulate, inspect. `admin`: analyst plus retrain and canary revocation. |
| Account management | CLI `apps/gateway/scripts/manage_operators.py`: `create`, `disable`, `enable`, `reset-password`, `set-role`, `list`. Passwords read with `getpass` or `--password-stdin`, never argv. No admin UI. |
| Identity transport | Bridge forwards `X-Mirage-Operator: <username>` with the API key. The gateway trusts the header only behind a valid API key. |
| Key-only callers | Valid API key, no operator header: principal `api-key`, role `admin` (scripts, smoke tests). Attribution records `api-key`. |
| Unknown or disabled operator | Same response as a bad API key (404 outside development, 401 in development). |
| Attribution | `events.labeled_by`, `actor_cases.updated_by`; `assigned_to` must name an existing enabled operator or be empty. |
| Audit | New append-only `operator_audit` table, one row per state-changing operator call. |
| Shared password | `MIRAGE_OPERATOR_PASSWORD` removed from web, compose, env examples and docs. |

## Components

### Gateway: operator store (`app/storage/db/models.py`, `repository.py`, `memory_store.py`, migration `0011`)

- `OperatorModel`: `id`, `username` (unique, index), `password_hash`,
  `role` (`analyst` | `admin`), `disabled` (bool, default false),
  `created_at`, `updated_at` (`UTCDateTime`).
- `OperatorAuditModel`: `id`, `occurred_at` (index), `operator` (String 32,
  index), `action` (String 48), `target` (String 128), `detail` (String 500).
- `EventModel.labeled_by` (String 32, nullable) and
  `ActorCaseModel.updated_by` (String 32, nullable). Old rows read back as
  `None`; the UI shows "unknown".
- Store methods (both backends): `get_operator(username)`,
  `create_operator(...)`, `update_operator(username, **fields)`,
  `list_operators()`, `record_audit(entry)`, `get_audit(limit)`.
- Migration `20261109_0011_operator_accounts.py` adds both tables and both
  columns; downgrade drops them.

### Gateway: passwords (`app/core/passwords.py`)

- `hash_password(password: str) -> str` and
  `verify_password(password: str, encoded: str) -> bool`. `verify_password`
  returns `False` for a malformed hash and never raises.
- `validate_password(password: str) -> None` raises `ValueError` outside the
  12–256 length range.

### Gateway: identity (`app/core/security.py`)

- `Operator` frozen dataclass: `username: str`, `role: Literal["analyst",
  "admin"]`.
- `require_operator(api_key, operator_header) -> Operator`: runs the existing
  key check, then:
  - no header: `Operator("api-key", "admin")`;
  - header names an enabled operator: that operator;
  - otherwise: the bad-key response.
  In development without a configured key, a header still resolves to its
  operator when it exists; a missing header gives `Operator("api-key",
  "admin")`.
- `require_admin(operator = Depends(require_operator)) -> Operator`: 403
  `"Admin role required"` for `analyst`.
- Every router that uses `require_api_key` today uses `require_operator`
  instead; `require_api_key` stays as the key-check helper it calls.
  `/training-data/retrain` and `/canary-assignments/{id}/revoke` use
  `require_admin`.

### Gateway: login (`app/api/routes/operators.py`)

- `POST /api/v1/operators/login` behind the API key only (the bridge calls
  it before a session exists). Body `{username, password}`. Success:
  `{username, role}`. Unknown user, disabled user or wrong password: 401
  `"Invalid credentials"`, with the hash verified against a fixed dummy hash
  for unknown users so timing does not reveal which usernames exist. Writes an
  audit row (`login` or `login_failed`, target the submitted username
  truncated to 32 characters).
- `GET /api/v1/operators` (any operator): `[{username, role}]` of enabled
  operators, for the assignee picker.
- `GET /api/v1/operators/audit?limit=` (admin): newest audit rows first.

### Gateway: attribution and audit (`dashboard.py`, services)

- Label route sets `labeled_by` and records `label_event`.
- Case open and update set `updated_by`, validate `assigned_to`, and record
  `case_open` / `case_update`. An unknown assignee is 422.
- Retrain records `retrain` with the run id; canary revoke records
  `canary_revoke` with the assignment id.
- Audit writes happen in the same request after the action succeeds; a failed
  action writes no audit row.

### Web (`apps/web`)

- Login form: username and password fields. The login route calls the
  gateway login server-side with the API key, and keeps the login throttle,
  now keyed by client IP plus lower-cased username.
- Session payload adds `sub` (username) and `role`. A cookie without `sub`
  is invalid, so every pre-existing session is logged out once.
- The bridge forwards `X-Mirage-Operator: <sub>` from the verified session.
  The browser can never set that header: the bridge builds the outgoing
  headers itself.
- UI: "Signed in as `<username>`" with sign-out; event labels show
  `labeled_by`; the case assignee is a select of operators; retrain and
  revoke controls are hidden for `analyst`. The gateway still enforces roles.

### Docs

- `docs/configuration.md`, `.env.example` files, `infra/docker-compose.yml`:
  drop `MIRAGE_OPERATOR_PASSWORD`; document the CLI and first-admin
  bootstrap.
- README auth table: roles per route.
- `docs/PROPOSAL_ALIGNMENT.md` Safe Claims: per-analyst sign-in and
  attributed labels and actions.
- Security note: a holder of `MIRAGE_API_KEY` can act as any operator. The
  key is the bridge's service credential and never reaches the browser.

## Error handling

- Malformed stored hash: login fails with 401, never 500.
- Database unavailable during operator lookup: 503, same as other store
  failures.
- CLI: duplicate username, reserved name, bad username, short password and
  unknown user exit non-zero with one clear line; no traceback.

## Testing

Each change gets a test that fails before it.

- Passwords: round-trip; wrong password false; malformed hash false; two
  hashes of one password differ; length bounds.
- CLI: create then list; duplicate and reserved names rejected; disable then
  login 401; reset-password changes the accepted password; password not
  accepted from argv.
- Identity: no header gives `api-key`/admin; enabled operator resolves;
  disabled and unknown operators get 404 in production; analyst gets 403 on
  retrain and revoke, 200 on label.
- Login route: success returns role; unknown user and wrong password both
  401 with the same body; audit rows written.
- Attribution: label sets `labeled_by`; case update sets `updated_by`;
  unknown assignee 422; one audit row per successful mutation, none on
  failure.
- Migration: upgrade and downgrade on SQLite.
- Web: session without `sub` rejected; login posts username and password;
  throttle keyed per username; bridge forwards `X-Mirage-Operator` from the
  session and ignores a client-sent one.

## Success criteria

1. All gateway and web tests pass; CI green.
2. `MIRAGE_OPERATOR_PASSWORD` appears nowhere outside historical specs and
   plans.
3. Two operators can sign in separately; a label made by each shows its
   author; disabling one ends their session on the next request.
4. Every state-changing operator route writes an audit row.

## Out of scope

- SSO/OIDC, multi-factor authentication, password change from the UI.
- Audit and event retention.
- Per-request signing between the bridge and the gateway.
