# Per-Analyst Operator Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analysts sign in as themselves; labels, case changes, retraining and canary revocation record who did them; disabling an account ends access on the next request.

**Architecture:** Operators live in the gateway database with scrypt password hashes and a role. The web login checks credentials through a gateway endpoint and signs a session cookie that names the operator. The bridge forwards `X-Mirage-Operator` beside the API key, and a `require_operator` dependency resolves it on every operator route, writing attribution columns and an append-only audit table.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pytest; Next.js 16, Web Crypto HMAC, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-09-operator-accounts-design.md`

## Global Constraints

- No new Python or npm dependency. Hashing uses `hashlib.scrypt`, n=2^14, r=8, p=1, 16-byte salt, 32-byte key, format `scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>`.
- Password length 12–256. Username regex `^[a-z0-9][a-z0-9._-]{1,31}$`, lower-cased; `api-key` reserved.
- Roles: `analyst`, `admin`. Admin-only: `POST /dashboard/training-data/retrain`, `POST /dashboard/canary-assignments/{id}/revoke`, `GET /operators/audit`.
- Unknown or disabled operator header: same response as a bad API key (404 outside development, 401 in development).
- Valid key without header: `Operator("api-key", "admin")`.
- Gateway tests: `venv/Scripts/python.exe -m pytest -q` from `apps/gateway`. Ruff: `apps/gateway/venv/Scripts/python.exe -m ruff check .` from repo root. Web: `npm test`, `npm run lint`, `npx tsc --noEmit` from `apps/web`.
- Commits: conventional style, no `Co-Authored-By` or other attribution lines.

## Review Focus

1. Username case: `Alice` at login and `alice` in the database must be one operator; the header from the bridge is the stored lower-case name. Pinned in Task 3 (`test_login_is_case_insensitive`).
2. A browser-sent `X-Mirage-Operator` must never reach the gateway: the bridge builds headers from scratch. Pinned in Task 6 (`bridgeHeaders` test).
3. An operator disabled mid-session: the next bridged call gets the bad-key response. Pinned in Task 3 (`test_disabled_operator_is_refused`).
4. The rate limiter exemption still keys on the API key only; adding the header must not change it. Pinned in Task 3 (`test_operator_header_keeps_rate_limit_exemption`).
5. Old labeled events with `labeled_by = NULL` must still export and train. Pinned in Task 4 (`test_label_without_author_still_exports`).

---

### Task 1: Password hashing

**Files:**
- Create: `apps/gateway/app/core/passwords.py`
- Test: `apps/gateway/tests/test_passwords.py`

**Interfaces:**
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, encoded: str) -> bool`, `validate_password(password: str) -> None` (raises `ValueError`), `DUMMY_HASH: str` (a valid hash of a random value, computed once at import, for unknown-user timing).

- [ ] **Step 1: Write the failing tests**

```python
def test_round_trip(): assert verify_password("correct horse 1", hash_password("correct horse 1"))
def test_wrong_password(): assert not verify_password("wrong password!", hash_password("correct horse 1"))
def test_salted(): assert hash_password("same password!") != hash_password("same password!")
def test_format(): assert hash_password("x" * 12).startswith("scrypt$16384$8$1$")
@pytest.mark.parametrize("encoded", ["", "scrypt$", "bcrypt$1$2$3$a$b", "scrypt$16384$8$1$!!$!!", "scrypt$x$8$1$AA$AA", "scrypt$1048576$8$1$AA$AA"])
def test_malformed_hash_is_false(encoded): assert verify_password("anything goes", encoded) is False
@pytest.mark.parametrize("password", ["x" * 11, "x" * 257])
def test_length_bounds(password):
    with pytest.raises(ValueError): validate_password(password)
def test_bounds_accept(): validate_password("x" * 12); validate_password("x" * 256)
```

- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_passwords.py -q` — Expected: FAIL, `ModuleNotFoundError: app.core.passwords`.
- [ ] **Step 3: Implement** in `app/core/passwords.py`. Parse with `split("$")`; reject unless 6 parts, prefix `scrypt`, integer n/r/p; reject n above 2^16 so a tampered row cannot exhaust memory; wrap decode and `scrypt` in `try/except (ValueError, binascii.Error)` returning `False`. Compare with `hmac.compare_digest`.
- [ ] **Step 4: Run** the same command — Expected: all pass.
- [ ] **Step 5: Commit** `feat(auth): scrypt password hashing`.

### Task 2: Operator store, audit store, migration

**Files:**
- Create: `apps/gateway/app/schemas/operator.py`, `apps/gateway/migrations/versions/20261109_0011_operator_accounts.py`
- Modify: `apps/gateway/app/storage/db/models.py`, `apps/gateway/app/storage/db/repository.py`, `apps/gateway/app/storage/memory_store.py`, `apps/gateway/app/schemas/event.py` (`EventRecord.labeled_by: str | None = None`), `apps/gateway/app/schemas/actor.py` (`ActorCaseWorkflow.updated_by: str | None = None`)
- Test: `apps/gateway/tests/test_operator_store.py`

**Interfaces:**
- Produces (schemas): `OperatorRole = Literal["analyst", "admin"]`; `OperatorRecord(username: str, password_hash: str = Field(repr=False), role: OperatorRole, disabled: bool = False, created_at: datetime, updated_at: datetime)`; `AuditEntry(occurred_at: datetime, operator: str, action: str, target: str = "", detail: str = "")`; `USERNAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{1,31}$"`; `RESERVED_USERNAMES = frozenset({"api-key"})`.
- Produces (both stores): `get_operator(username) -> OperatorRecord | None`; `create_operator(record: OperatorRecord) -> None` (raises `ValueError("Operator already exists")` on duplicate); `update_operator(username, *, password_hash=None, role=None, disabled=None) -> OperatorRecord | None` (sets `updated_at`); `list_operators() -> list[OperatorRecord]` (by username); `record_audit(entry: AuditEntry) -> None`; `get_audit(limit: int = 100) -> list[AuditEntry]` (newest first).
- Produces: `update_event_label(..., labeled_by: str | None = None)`; `open_actor_case(..., updated_by: str | None = None)`; `update_actor_case(..., updated_by: str | None = None)` — stored and returned on the records.

- [ ] **Step 1: Write failing tests** in `tests/test_operator_store.py`, run against both the configured `app.storage.store` and a fresh `MemoryStore()` (follow `tests/test_repository.py` for the database store):
  - `test_create_get_list_operator`: create `alice` analyst; `get_operator("alice").role == "analyst"`; `list_operators()` names `["alice"]`.
  - `test_duplicate_operator_rejected`: second create raises `ValueError`.
  - `test_update_operator_disables_and_bumps_updated_at`.
  - `test_audit_newest_first`: three entries; `get_audit(2)` returns the last two, newest first.
  - `test_label_records_author`: `update_event_label(id, AnalystLabel.SUSPICIOUS, "", labeled_by="alice").labeled_by == "alice"`.
  - `test_case_update_records_author`: open then update with `updated_by="bob"`; `.updated_by == "bob"`.
  - `test_password_hash_not_in_repr`: `"scrypt" not in repr(record)`.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_operator_store.py -q` — Expected: FAIL on import of `app.schemas.operator`.
- [ ] **Step 3: Implement** `OperatorModel` (table `operators`) and `OperatorAuditModel` (table `operator_audit`) per the spec's column list; `EventModel.labeled_by` and `ActorCaseModel.updated_by` as nullable `String(32)`. The database `create_operator` maps `IntegrityError` to `ValueError`. Migration `20261109_0011` (`down_revision = "20260702_0010"`) creates both tables with indexes on `operators.username` (unique), `operator_audit.occurred_at` and `operator_audit.operator`, and adds both columns; downgrade reverses in order.
- [ ] **Step 4: Run** the test file, then the full suite — Expected: all pass.
- [ ] **Step 5: Verify migration** from `apps/gateway`: with `DATABASE_URL=sqlite+aiosqlite:///<scratch>/m.db`, run `venv/Scripts/python.exe -m alembic upgrade head`, then `-m alembic downgrade 20260702_0010`, then `upgrade head` — Expected: all three exit 0.
- [ ] **Step 6: Commit** `feat(auth): operator and audit storage`.

### Task 3: Identity dependency, operator routes, CLI

**Files:**
- Modify: `apps/gateway/app/core/security.py`, `apps/gateway/app/api/routes/{dashboard,decoy,inspect,simulate}.py`, the module that builds `api_router`
- Create: `apps/gateway/app/services/operators.py`, `apps/gateway/app/api/routes/operators.py`, `apps/gateway/scripts/manage_operators.py`
- Test: `apps/gateway/tests/test_operator_auth.py`, `apps/gateway/tests/test_manage_operators.py`

**Interfaces:**
- Consumes: Task 1 functions; Task 2 store methods and schemas.
- Produces: `Operator` frozen dataclass `(username: str, role: OperatorRole)`; `API_KEY_OPERATOR = Operator("api-key", "admin")`; `require_operator(api_key=Security(_api_key_header), operator=Security(_operator_header)) -> Operator` with `_operator_header = APIKeyHeader(name="X-Mirage-Operator", auto_error=False)`; `require_admin(operator: Operator = Depends(require_operator)) -> Operator`.
- Produces (service): `normalize_username(value: str) -> str` (strip, lower, regex, reserved → `ValueError`); `create_operator(username, password, role) -> OperatorRecord`; `authenticate(username, password) -> Operator | None` (always runs exactly one `verify_password`, against `DUMMY_HASH` when the user is missing, disabled or the name is invalid); `audit(operator: Operator, action: str, target: str = "", detail: str = "") -> None` (truncates target to 128, detail to 500).
- Produces (routes): `POST /api/v1/operators/login` body `OperatorLoginRequest(username: str max 64, password: str max 256)` → `{"username", "role"}` or 401 `{"detail": "Invalid credentials"}`; `GET /api/v1/operators` → `{"operators": [{"username", "role"}]}`, enabled only; `GET /api/v1/operators/audit?limit=1..500` (default 100, admin) → `{"entries": [...]}`.

- [ ] **Step 1: Write failing tests** in `tests/test_operator_auth.py`. Production env via `dataclasses.replace(config.settings, app_env="production", api_key="k"*32)` monkeypatched as in `tests/test_security.py`; create operators through the service:
  - `test_key_without_header_is_api_key_admin`: `GET /api/v1/operators/audit` with key only → 200.
  - `test_enabled_operator_resolves`: analyst `alice` header → `GET /api/v1/operators` 200.
  - `test_unknown_operator_is_404` and `test_disabled_operator_is_refused` → 404 with a valid key.
  - `test_analyst_forbidden_on_admin_routes`: alice → retrain 403, revoke 403, audit 403, each `detail == "Admin role required"`.
  - `test_login_success_returns_role` and writes audit `login`.
  - `test_login_failures_are_identical`: unknown user, wrong password and disabled user each give 401 with identical JSON; audit rows `login_failed`.
  - `test_login_is_case_insensitive`: `"Alice"` logs in as `alice`.
  - `test_login_requires_api_key`: no key → 404.
  - `test_operator_header_keeps_rate_limit_exemption`: with `rate_limit_per_minute=1`, three keyed calls with an operator header all succeed.
- [ ] **Step 2: Write failing CLI tests** in `tests/test_manage_operators.py`, calling `manage_operators.main(argv, stdin=io.StringIO(...))`, which returns the exit code:
  - `create alice --role analyst --password-stdin` with stdin `"long enough pw\n"` → 0; then `list` prints `alice analyst enabled`.
  - Duplicate → 1 with message `Operator already exists`; `create api-key` → 1; `create Bad!` → 1; short password → 1; no `Traceback` in stderr.
  - `disable alice` makes `authenticate("alice", ...)` return `None`; `enable` restores it.
  - `reset-password alice --password-stdin` changes the accepted password; `set-role alice admin` changes the role.
  - `test_password_not_accepted_from_argv`: `create bob --password secret123456` → exit 2 (argparse error).
  Without `--password-stdin` the CLI calls `getpass.getpass` twice and requires both to match.
- [ ] **Step 3: Run** both files — Expected: FAIL on imports.
- [ ] **Step 4: Implement.** Move the body of `require_api_key` into `_check_api_key(api_key: str | None) -> None`; `require_operator` calls it first. An unknown or disabled header raises the exact exception the bad-key path raises for the current `app_env`. Replace every router's `Depends(require_api_key)` with `require_operator`, and delete `require_api_key` if nothing else uses it. The retrain and revoke handlers take `operator: Operator = Depends(require_admin)`. The login route sits on its own router with `dependencies=[Depends(_check_api_key)]` behind a thin `Security` wrapper. The CLI runs the service with `asyncio.run` against `app.storage.store` and prints one line per error to stderr.
- [ ] **Step 5: Run** both files, then the full suite — Expected: all pass; existing key-only tests keep passing as `api-key`/admin.
- [ ] **Step 6: Commit** `feat(auth): per-operator identity on the operator API`.

### Task 4: Attribution and audit on mutations

**Files:**
- Modify: `apps/gateway/app/api/routes/dashboard.py`, `apps/gateway/app/services/actor_clusters.py` (`open_actor_case_from_recommendation` and `update_actor_case_workflow` gain `updated_by: str`)
- Test: `apps/gateway/tests/test_operator_attribution.py`

**Interfaces:**
- Consumes: Task 3 `require_operator`, `require_admin`, `audit`, `normalize_username`; Task 2 store keyword arguments.
- Produces: audit actions `label_event` (target event id, detail label), `case_open` and `case_update` (target case id, detail status), `retrain` (target the run's artifact name or id from `RetrainingRun`), `canary_revoke` (target assignment id), plus Task 3's `login` / `login_failed`.

- [ ] **Step 1: Write failing tests:**
  - `test_label_sets_labeled_by_and_audits`: alice labels → event `labeled_by == "alice"`; one audit row `label_event` by alice.
  - `test_label_missing_event_writes_no_audit`: 404 and zero audit rows.
  - `test_case_open_and_update_record_author`: `updated_by` is the caller; audit rows `case_open` then `case_update`.
  - `test_unknown_assignee_is_422`: `assigned_to="nobody"` → 422 with detail `Unknown assignee`; an empty string is allowed.
  - `test_retrain_and_revoke_audit_admin`: admin calls each; a successful call writes one audit row; a failing retrain (409 on too few labels) writes none.
  - `test_label_without_author_still_exports`: an event labeled through the store with `labeled_by=None` appears in the training-data export.
- [ ] **Step 2: Run** — Expected: FAIL (`labeled_by` is None, no audit rows).
- [ ] **Step 3: Implement.** Handlers take `operator: Operator = Depends(require_operator)` (or `require_admin`), pass `operator.username` to the store, and call `audit(...)` only after success. A non-empty `assigned_to` must match an enabled operator via `get_operator(normalize_username(...))`; otherwise raise `HTTPException(422, "Unknown assignee")`. Store the normalized name.
- [ ] **Step 4: Run** the file and the full suite — Expected: all pass.
- [ ] **Step 5: Commit** `feat(auth): attribute labels and case work, audit operator actions`.

### Task 5: Web session carries the operator

**Files:**
- Modify: `apps/web/src/lib/operator-auth.ts`, `apps/web/src/lib/operator-auth.test.ts`, `apps/web/src/lib/login-throttle.ts`, `apps/web/src/lib/login-throttle.test.ts`, `apps/web/src/app/api/auth/login/route.ts`
- Create: `apps/web/src/app/api/auth/session/route.ts`

**Interfaces:**
- Produces: `type OperatorIdentity = { sub: string; role: "analyst" | "admin" }`; `createOperatorSession({ secret, now, nonce, operator }: CreateTokenOptions & { operator: OperatorIdentity }): Promise<string>`; `readOperatorSession(token: string, secret: string, now: number): Promise<OperatorIdentity | null>` (null when the signature, audience, time or claims fail, when `sub` fails `/^[a-z0-9][a-z0-9._-]{1,31}$/`, or when the role is not one of the two); `verifyOperatorSession` becomes `(await readOperatorSession(...)) !== null`, so `proxy.ts` and the stream-ticket route need no change. `loginClientKey` gains a `username` argument and keys on client address plus `username.trim().toLowerCase()`.
- Produces: `GET /api/auth/session` → `{ username, role }` or 401, `Cache-Control: no-store`.

- [ ] **Step 1: Write failing tests.** In `operator-auth.test.ts`: round-trip returns `{ sub: "alice", role: "analyst" }`; a token with the old claim shape (no `sub`) → null; `sub` `"Bad!"` → null; role `"root"` → null; tampered payload → null. In `login-throttle.test.ts`: the same address with `"Alice"` and `"alice"` gives one key; different usernames give different keys.
- [ ] **Step 2: Run** `npm test` in `apps/web` — Expected: FAIL.
- [ ] **Step 3: Implement.** The login route reads `{ username, password }`, rejects non-strings or over-length values (64/256) with 400, and POSTs to `${MIRAGE_INTERNAL_API_URL}/api/v1/operators/login` with `X-Mirage-API-Key`. A gateway 401 gives `{"detail":"Invalid credentials"}` 401 and records a throttle failure; any other non-2xx or network error gives 503 `Operator authentication is not configured` (unchanged copy); success sets the cookie from `createOperatorSession` with the returned identity. Remove `MIRAGE_OPERATOR_PASSWORD` and `passwordMatches`.
- [ ] **Step 4: Run** `npm test`, `npx tsc --noEmit`, `npm run lint` — Expected: all pass.
- [ ] **Step 5: Commit** `feat(web): operator sessions name the analyst`.

### Task 6: Bridge forwards the operator; UI shows authorship and roles

**Files:**
- Modify: `apps/web/src/lib/gateway-bridge.ts`, `apps/web/src/lib/gateway-bridge.test.ts`, `apps/web/src/app/api/gateway/[...path]/route.ts`, `apps/web/src/lib/api.ts`, `apps/web/src/lib/api-types.ts`, `apps/web/src/lib/api-map.ts`, `apps/web/src/lib/api-map.test.ts`, `apps/web/src/app/login/page.tsx`, `apps/web/src/app/dashboard/page.tsx`, `apps/web/src/components/dashboard/ActorTriagePanel.tsx`, `apps/web/src/components/dashboard/CanaryAssignmentsPanel.tsx`, and the component that renders event labels (`grep -rn labelEvent apps/web/src`)

**Interfaces:**
- Consumes: Task 5 `readOperatorSession`, `OPERATOR_SESSION_COOKIE`, `/api/auth/session`; gateway routes from Task 3.
- Produces: `bridgeHeaders({ apiKey, operator, contentType }: { apiKey: string; operator: string; contentType: string | null }): Record<string, string>` returning exactly `X-Mirage-API-Key`, `X-Mirage-Operator`, and `Content-Type` when given. `isAllowedBridgeRequest` also allows `GET operators`. `fetchOperators(): Promise<OperatorSummary[]>`; `fetchSession(): Promise<{ username: string; role: "analyst" | "admin" }>`; `FeedEvent.labeledBy: string | null`; the case workflow type gains `updatedBy: string | null`.

- [ ] **Step 1: Write failing tests.** In `gateway-bridge.test.ts`: `bridgeHeaders` returns exactly the expected keys; `isAllowedBridgeRequest("GET", ["operators"])` is true, `("GET", ["operators","audit"])` false, `("POST", ["operators","login"])` false. In `api-map.test.ts`: an event with `labeled_by: "alice"` maps to `labeledBy: "alice"`, a missing one to `null`.
- [ ] **Step 2: Run** `npm test` — Expected: FAIL.
- [ ] **Step 3: Implement.** The bridge route reads and verifies the session cookie with `readOperatorSession`; without a valid session it returns 401 `{"detail":"Not authenticated"}`; it builds outgoing headers only through `bridgeHeaders`. Login page: a username field (`autoComplete="username"`) above the password field. Dashboard: fetch the session once; show `Signed in as <username>` beside the existing sign-out; show `by <labeledBy ?? "unknown">` on labeled events; the case assignee becomes a `<select>` of `fetchOperators()` with an empty "Unassigned" option; the retrain button and canary revoke buttons render only for `role === "admin"`. Reuse existing styles; add no other visual elements.
- [ ] **Step 4: Run** `npm test`, `npx tsc --noEmit`, `npm run lint`, `npm run build` — Expected: all pass.
- [ ] **Step 5: Commit** `feat(web): forward the operator and show authorship`.

### Task 7: Config and docs

**Files:**
- Modify: `apps/web/.env.example`, `.env.example`, `infra/docker-compose.yml`, `docs/configuration.md`, `README.md`, `docs/PROPOSAL_ALIGNMENT.md`, `docs/architecture.md` (only where it describes the shared password)

- [ ] **Step 1:** `git grep -n MIRAGE_OPERATOR_PASSWORD -- . ':!docs/superpowers'` — remove every hit.
- [ ] **Step 2:** Document first-admin bootstrap (`docker compose exec gateway python scripts/manage_operators.py create admin --role admin`, which prompts twice, plus the local `venv` form), the roles per route in the README auth table, and the API-key impersonation limit in `docs/configuration.md`.
- [ ] **Step 3:** Add a Safe Claims bullet to `docs/PROPOSAL_ALIGNMENT.md`: signs analysts in individually and records who labeled each event, changed each case, retrained a model or revoked a canary.
- [ ] **Step 4: Run** the grep again (Expected: no hits), `python infra/check-compose.py` (Expected: exit 0), the full gateway suite, ruff, and `npm test`.
- [ ] **Step 5: Commit** `docs: operator accounts setup and roles`.
