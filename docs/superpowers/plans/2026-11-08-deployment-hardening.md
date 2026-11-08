# Deployment and Auth Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a production MIRAGE deployment safe by default: fail closed, no fingerprints, real client IPs, bounded state, pinned model files, route exemptions, throttled login, segmented network.

**Architecture:** Small new gateway modules (`client_ip`, `settings_validation`, `artifact_integrity`, `payload_exemptions`) wired into the existing proxy route, rate limiter, proxy client, ML loaders and app factory; one new web module (`login-throttle`); compose, Dockerfile and CI changes.

**Tech Stack:** FastAPI, httpx, pytest (asyncio auto), Next.js 16 route handlers, node:test, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-08-deployment-hardening-design.md`

## Global Constraints

- `development` is the default `APP_ENV` and keeps today's behavior; every other value fails closed for auth; only `production` runs startup validation.
- Messages from validation name variables, never their values.
- Code touched in this plan reads settings at call time as `config.settings` (`from app.core import config`), so tests swap them with `monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, <field>=<value>))`. `Settings` stays a frozen dataclass.
- Defaults: `RATE_LIMIT_MAX_CLIENTS=10000`, `PROXY_MAX_RESPONSE_BYTES=10485760`, login throttle 5 per client / 50 global per 15 minutes, 10,000 client keys.
- Gateway commands run from `apps/gateway` with `venv/Scripts/python.exe -m pytest` (CI: `pytest`); ruff from the repo root: `ruff check .`.
- Commits: conventional messages, **no** `Co-Authored-By` or session trailers.

## Review Focus

1. IPv6 peers and `X-Forwarded-For` entries with ports or spaces (`"203.0.113.9:1234"`, `" 198.51.100.7 "`): spaces are stripped, and an entry with a port counts as malformed (the walk stops). Test in Task 1.
2. A rate-limited client that is evicted at the cap must not get a fresh budget while the cap is under no pressure: eviction happens only when a *new* key arrives at the cap. Test in Task 2.
3. Upstream streaming errors mid-body (connection reset) still return 502, not a 500 or a truncated 200. Test in Task 3.
4. A path exemption must not apply when the method differs only in case: methods compare uppercased, so `post` in the rule matches `POST`. Test in Task 5.
5. In production, the WebSocket stream and `/health` keep working for compose health checks and the dashboard (no accidental 404 on `/health`). Test in Task 7.

---

### Task 1: Real client IP

**Files:**
- Create: `apps/gateway/app/core/client_ip.py`, `apps/gateway/tests/test_client_ip.py`
- Modify: `apps/gateway/app/core/config.py` (field `trusted_proxies: str`, env `TRUSTED_PROXIES`, default `""`), `apps/gateway/app/api/routes/proxy.py:49`, `apps/gateway/Dockerfile` (CMD adds `--no-proxy-headers`)

**Interfaces:**
- Produces: `parse_trusted_proxies(raw: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]` (raises `ValueError` on a bad entry; empty or whitespace input gives `()`); `client_ip(request: starlette.requests.Request) -> str` (returns `"unknown"` when there is no peer).

- [ ] **Step 1: Write failing tests** in `tests/test_client_ip.py`, building `Request` objects from ASGI scopes (`{"type": "http", "client": (peer, 1234), "headers": [(b"x-forwarded-for", b"...")]}`) with settings swapped per the Global Constraints:
  - `test_untrusted_peer_ignores_forged_header`: peer `203.0.113.5`, XFF `1.2.3.4`, no trusted proxies → `"203.0.113.5"`.
  - `test_trusted_peer_returns_rightmost_untrusted_hop`: trusted `10.0.0.0/8`, peer `10.0.0.2`, XFF `"198.51.100.7, 203.0.113.9, 10.0.0.3"` → `"203.0.113.9"`.
  - `test_all_hops_trusted_returns_leftmost`: trusted `10.0.0.0/8`, peer `10.0.0.2`, XFF `"10.0.0.9, 10.0.0.3"` → `"10.0.0.9"`.
  - `test_trusted_peer_without_header_returns_peer`.
  - `test_malformed_entry_stops_walk`: trusted `10.0.0.0/8`, peer `10.0.0.2`, XFF `"198.51.100.7, garbage, 10.0.0.3"` → `"10.0.0.3"`.
  - `test_entry_with_port_is_malformed`: XFF `"203.0.113.9:1234"` behind a trusted peer → peer address; `test_spaces_are_stripped`: `" 198.51.100.7 "` → `"198.51.100.7"`.
  - `test_ipv6_trusted_proxy`: trusted `fd00::/8`, peer `fd00::1`, XFF `"2001:db8::5"` → `"2001:db8::5"`.
  - `test_parse_trusted_proxies`: `"10.0.0.1, 172.16.0.0/12"` gives 2 networks; `""` gives `()`; `"nope"` raises `ValueError`.
  - In `tests/test_proxy.py`, `test_proxy_logs_forwarded_client_ip`: trusted `127.0.0.0/8` plus the test client's peer (`ASGITransport` uses `("127.0.0.1", 123)`), XFF `203.0.113.9` → the stored event's `ip_address == "203.0.113.9"`.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_client_ip.py tests/test_proxy.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `client_ip.py` per the spec walk: parse the setting on each call (cheap, a few entries) or cache with `functools.lru_cache` keyed on the raw string. Replace `request.client.host` in `proxy.py` with `client_ip(request)`. Add `--no-proxy-headers` to the uvicorn command in the Dockerfile.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then run the full gateway suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat(gateway): resolve client IPs through trusted proxies`.

### Task 2: Bounded rate limiter

**Files:**
- Modify: `apps/gateway/app/core/rate_limit.py`, `apps/gateway/app/core/config.py` (field `rate_limit_max_clients: int`, env `RATE_LIMIT_MAX_CLIENTS`, default `10000`)
- Create: `apps/gateway/tests/test_rate_limit.py`

**Interfaces:**
- Consumes: `client_ip(request)` (Task 1).
- Produces: `RateLimitMiddleware(app, requests_per_minute: int, max_clients: int = 10000, clock: Callable[[], float] = time.monotonic)`; attribute `requests: OrderedDict[str, deque[float]]`.

- [ ] **Step 1: Write failing tests.** Use a minimal Starlette app with one `/api/v1/x` route wrapped in the middleware and an injected fake clock. Vary peers via `ASGITransport(client=(ip, 1))`.
  - `test_blocks_after_limit`: limit 2 → the third request gets 429 with `Retry-After: 60`.
  - `test_clients_are_independent`.
  - `test_expired_bucket_is_deleted`: one request, advance the clock 61 s, request from another IP → the first IP's key is absent from `requests`.
  - `test_cap_evicts_least_recently_used`: `max_clients=2`; requests from A, B, A, then C → the keys are `{A, C}`.
  - `test_cap_prefers_expired_buckets`: `max_clients=2`; A, advance 61 s, B, then C → A was purged and B survives.
  - `test_no_eviction_below_cap`: `max_clients=3`; A hits its limit, B and C arrive → A is still blocked.
  - `test_keys_on_client_ip`: with a trusted proxy, two different XFF clients from the same peer get separate buckets.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_rate_limit.py -q`. Expected: FAIL (unexpected `max_clients` / `clock` keyword).
- [ ] **Step 3: Implement.** On each request: get the bucket via `requests.get`, then `move_to_end`; prune old timestamps and delete the key if the bucket is empty before appending. On a new key at the cap, purge every key whose newest timestamp is older than the cutoff; if still at the cap, `popitem(last=False)`. `configure_rate_limit` passes `max_clients` from settings.
- [ ] **Step 4: Run** the test file. Expected: PASS. Then the full suite. Expected: all pass.
- [ ] **Step 5: Commit** `fix(gateway): bound rate limiter memory and key on client IP`.

### Task 3: Shared upstream client and response cap

**Files:**
- Modify: `apps/gateway/app/services/proxy_client.py`, `apps/gateway/app/main.py` (lifespan opens and closes the client), `apps/gateway/app/core/config.py` (field `proxy_max_response_bytes: int`, env `PROXY_MAX_RESPONSE_BYTES`, default `10485760`)
- Create: `apps/gateway/tests/test_proxy_client.py`

**Interfaces:**
- Produces: `async def open_upstream_client() -> None`, `async def close_upstream_client() -> None` in `proxy_client.py`; `forward_request(...)` keeps its current signature.

- [ ] **Step 1: Write failing tests** using `httpx.MockTransport`. Inject it by monkeypatching a module-level factory `_build_client(transport=None)`, or by setting `proxy_client._client` directly.
  - `test_shared_client_is_reused`: two `forward_request` calls after `open_upstream_client()` → the transport handler sees both requests through the same client object (assert `_client` identity unchanged and not closed).
  - `test_content_length_over_cap_returns_502`: upstream `Content-Length: 11` with a cap of 10 → `HTTPException` 502, detail `"Upstream response too large"`.
  - `test_streamed_body_over_cap_returns_502`: chunked body of 11 bytes without `Content-Length`, cap 10 → 502.
  - `test_body_under_cap_is_identical`: body, status and safe headers equal what the upstream sent.
  - `test_midstream_error_returns_502`: the stream raises `httpx.ReadError` → 502 "Upstream service unavailable".
  - `test_without_lifespan_uses_temporary_client`: `_client is None` → the request still succeeds.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_proxy_client.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Use `client.send(client.build_request(...), stream=True)`, check `Content-Length`, read with `aiter_bytes()` into a `bytearray` while counting, and `aclose()` in `finally`. `httpx.RequestError` (including `ReadError`) → existing 502. The lifespan calls `open_upstream_client()` after `init_db()` and `close_upstream_client()` before `close_db()`.
- [ ] **Step 4: Run** the test file, then the full suite (`test_proxy.py` must still pass). Expected: PASS.
- [ ] **Step 5: Commit** `perf(gateway): reuse upstream client and cap upstream response size`.

### Task 4: Pinned model artifacts

**Files:**
- Create: `apps/gateway/app/ml/artifact_integrity.py`, `apps/gateway/tests/test_artifact_integrity.py`
- Modify: `apps/gateway/app/ml/inference.py`, `apps/gateway/app/ml/artifacts.py` (`review_model_artifact`), `apps/gateway/app/services/ml_shadow.py`, `apps/gateway/app/services/ml_promotion.py` (both reviewer call sites pass `expected_sha256`), `apps/gateway/app/services/retraining.py`, `apps/gateway/app/schemas/retraining.py` (`artifact_sha256: str`), `apps/gateway/app/core/config.py` (field `ml_model_artifact_sha256: str | None`, env `MIRAGE_MODEL_ARTIFACT_SHA256`, empty → `None`)

**Interfaces:**
- Produces: `class ArtifactIntegrityError(ValueError)`; `sha256_file(path: Path) -> str`; `verify_artifact_digest(path: Path, expected_sha256: str) -> None`; `RiskClassifier(artifact_path: Path, *, expected_sha256: str | None = None)`; `review_model_artifact(artifact_path, *, expected_sha256: str | None = None, ...)`. A mismatch in review becomes the blocker `"Artifact SHA-256 does not match MIRAGE_MODEL_ARTIFACT_SHA256"` with no load.

- [ ] **Step 1: Write failing tests:**
  - `test_verify_matches`, `test_verify_mismatch_raises`, `test_uppercase_digest_accepted`, `test_bad_digest_format_raises` (`"abc"`, 64 non-hex characters).
  - `test_classifier_does_not_load_on_mismatch`: monkeypatch `app.ml.inference.joblib.load` to a function that fails the test → constructing with a wrong digest raises `ArtifactIntegrityError` and the loader is never called.
  - `test_review_blocks_on_mismatch_without_loading`: the same patch on `app.ml.artifacts.joblib.load`.
  - `test_shadow_loader_returns_none_on_mismatch`: settings point at a real trained artifact (reuse the fixture pattern in `test_ml_shadow.py`) with a wrong digest; `_load_classifier.cache_clear()` → `None`.
  - In `test_retraining.py`, `test_retraining_reports_artifact_sha256`: the run's `artifact_sha256 == sha256_file(Path(run.artifact_path))`.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_artifact_integrity.py tests/test_retraining.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Hash in 1 MiB chunks; compare with `hmac.compare_digest`. In the shadow loader, a missing digest logs the warning `"MIRAGE_MODEL_ARTIFACT_SHA256 not set; loading unpinned artifact"`, and `ArtifactIntegrityError` is caught (logged; returns `None`). Update `next_steps` in retraining to mention `MIRAGE_MODEL_ARTIFACT_SHA256`.
- [ ] **Step 4: Run** the files above plus `tests/test_ml_*.py`, then the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(gateway): verify model artifact SHA-256 before loading`.

### Task 5: Per-route payload exemptions

**Files:**
- Create: `apps/gateway/app/services/payload_exemptions.py`, `apps/gateway/tests/test_payload_exemptions.py`
- Modify: `apps/gateway/app/core/config.py` (field `payload_exemptions: str`, env `PAYLOAD_EXEMPTIONS`, default `""`), `apps/gateway/app/schemas/request.py` (`exempted_indicators: list[Indicator] = Field(default_factory=list, max_length=20)`), `apps/gateway/app/services/risk_engine.py` (one zero-score reason per exempted label: `f"Exempted payload indicator: {label}"`), `apps/gateway/app/api/routes/proxy.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class ExemptionRule(method: str, path_glob: str, labels: frozenset[str])`; `parse_exemptions(raw: str) -> tuple[ExemptionRule, ...]` (raises `ValueError` naming the rule index, not its text); `is_canonical_path(path: str) -> bool`; `apply_exemptions(method: str, path: str, indicators: list[str], rules: tuple[ExemptionRule, ...] | None = None) -> tuple[list[str], list[str]]` (`rules=None` reads settings; in development an invalid setting logs and gives no rules).
- Known labels: `sql-like`, `xss`, `path-traversal`, `rce-indicator`, `header-injection`, `null-byte`, `encoded`, `large-payload`, `unusual-content-type`.

- [ ] **Step 1: Write failing tests:**
  - Parsing: `"POST /api/posts:xss;PUT /api/snippets/*:rce-indicator,sql-like"` gives 2 rules; `"* /x:xss"` is valid; `"POST /x:bogus"`, `"POST:xss"` and `"POST /x"` raise `ValueError`; `""` gives `()`.
  - Matching: method mismatch → nothing exempted; the lowercase rule method `post` matches `POST`; `/api/snippets/*` matches `/api/snippets/a/b`; only listed labels move to `exempted`, and the others stay in `kept`.
  - `test_non_canonical_paths_never_exempt`, parametrized over `/api/posts/../admin`, `/api/posts/%2e%2e/admin`, `/api/posts//x`, `/api/posts\\x`, `/api/posts;x`, `/api/posts/./x`.
  - Risk: `calculate_risk` with `exempted_indicators=["xss"]` and no other signal → score unchanged from baseline, and `"Exempted payload indicator: xss"` is in `reasons`.
  - Proxy integration in `tests/test_proxy.py`, reusing the existing `_route` helper with settings `payload_exemptions="POST /api/posts:xss"`: POST `<script>alert(1)</script>` to `/api/posts` → real app, and the event's reasons include the exemption line; the same body to `/api/comments` → decoy.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_payload_exemptions.py tests/test_proxy.py tests/test_risk_engine.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** A path is canonical when it has no `%`, `\`, `;`, `//`, and no `.` or `..` segment. In `proxy.py`, call `apply_exemptions(request.method, path, indicators)` right after detection; pass `kept` as `payload_indicators` and `exempted` as `exempted_indicators`.
- [ ] **Step 4: Run** the same command, then the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(gateway): add per-route payload detection exemptions`.

### Task 6: Fail-closed auth and startup validation

**Files:**
- Create: `apps/gateway/app/core/settings_validation.py`, `apps/gateway/tests/test_settings_validation.py`, `apps/gateway/tests/test_security.py`
- Modify: `apps/gateway/app/core/security.py`, `apps/gateway/app/main.py` (lifespan), `apps/gateway/tests/conftest.py`, `apps/gateway/pyproject.toml` (`asyncio_default_fixture_loop_scope = "function"`)

**Interfaces:**
- Consumes: `parse_trusted_proxies` (Task 1), `parse_exemptions` (Task 5).
- Produces: `production_config_errors(settings: Settings) -> list[str]`; `validate_startup(settings: Settings) -> None` (raises `RuntimeError("Invalid production configuration:\n- ...")` when `app_env == "production"` and there are errors).

- [ ] **Step 1: Write failing tests:**
  - `test_valid_production_config_has_no_errors`: 32+ character key and ticket secret, real decoy tokens, file SQLite or Postgres URL → `[]`.
  - One test per error, each asserting the variable name appears in the message and the bad value does not:
    - `MIRAGE_API_KEY` missing;
    - `MIRAGE_API_KEY` of 31 characters;
    - ticket secret missing or short;
    - each `*_NOT_CONFIGURED` token;
    - `sqlite+aiosqlite:///:memory:` and `...?mode=memory`;
    - artifact without a digest;
    - `TRUSTED_PROXIES="nope"`;
    - `PAYLOAD_EXEMPTIONS="POST /x:bogus"`.
  - `test_validate_startup_ignores_development`.
  - `test_lifespan_refuses_bad_production_config`: entering `app.router.lifespan_context(app)` with production settings and no key raises `RuntimeError`.
  - `test_security.py`: production with no key → `POST /api/v1/inspect` gives 503 with detail `"API key not configured"`; development with no key → not 401/503; key configured and wrong header → 401; right header → passes auth.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_settings_validation.py tests/test_security.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** The lifespan calls `validate_startup(config.settings)` before `init_db()`. In `conftest.py`, set `os.environ["APP_ENV"] = "development"` and register `atexit.register(shutil.rmtree, _TEST_DB.parent, ignore_errors=True)`. Add the pytest option.
- [ ] **Step 4: Run** the same command, then the full suite. Expected: PASS, with no pytest-asyncio loop-scope deprecation warning.
- [ ] **Step 5: Commit** `feat(gateway): fail closed without an API key and validate production config`.

### Task 7: No fingerprints

**Files:**
- Create: `apps/gateway/tests/test_fingerprinting.py`
- Modify: `apps/gateway/app/main.py` (`create_app(settings: Settings) -> FastAPI`; module-level `app = create_app(config.settings)`), `apps/gateway/app/api/routes/health.py`, `apps/gateway/app/api/routes/decoy.py`, `apps/gateway/tests/test_health.py` (update expectations to the development body)

**Interfaces:**
- Produces: `create_app(settings: Settings) -> FastAPI`. Docs URLs and the `/` route exist only when `settings.app_env == "development"`. `/health` reads `config.settings` at request time: development returns today's body; anything else returns `{"status": "ok"}`.

- [ ] **Step 1: Write failing tests.** Build `prod = create_app(replace(config.settings, app_env="production", api_key="k"*32))` and also swap `config.settings` to the same object (so request-time checks agree). Use an `AsyncClient` on `prod` without its lifespan.
  - `/docs`, `/redoc`, `/openapi.json` and `/` → 404.
  - `GET /api/v1/decoy/status` without the key → 401; with the key → 200.
  - `/health` → 200, body exactly `{"status": "ok"}`, and none of `mirage`, `deception`, `decoy` appear (case-insensitive).
  - `test_production_websocket_route_still_registered`: `"/api/v1/dashboard/ws"` is in `[r.path for r in prod.routes]`.
  - Development app: `/docs` → 200.
- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_fingerprinting.py tests/test_health.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `create_app` by moving the current module body into it; the `FastAPI(...)` kwargs set `docs_url`, `redoc_url` and `openapi_url` to `None` outside development. Add `dependencies=[Depends(require_api_key)]` to `/decoy/status`.
- [ ] **Step 4: Run** the same command, then the full suite and `ruff check .` from the repo root. Expected: PASS and clean.
- [ ] **Step 5: Commit** `fix(gateway): hide docs, root, health details and decoy status outside development`.

### Task 8: Login throttling (web) and lint gate

**Files:**
- Create: `apps/web/src/lib/login-throttle.ts`, `apps/web/src/lib/login-throttle.test.ts`
- Modify: `apps/web/src/app/api/auth/login/route.ts`, `apps/web/package.json` (add the new test to the `test` script), `apps/web/src/components/layout/Header.tsx:21` (fix the one lint warning with `useRouter().push("/login")` followed by `router.refresh()`), `.github/workflows/ci.yml` (`npm run lint -- --max-warnings 0`)

**Interfaces:**
- Produces: `createLoginThrottle(options?: { perClientLimit?: number; globalLimit?: number; windowMs?: number; maxClients?: number; now?: () => number })` returning `{ check(key: string): { allowed: boolean; retryAfterSeconds: number }; recordFailure(key: string): void; recordSuccess(key: string): void }`; `loginClientKey(headers: Headers, trustProxyHeaders: boolean): string`; a module-level `loginThrottle` instance used by the route.

- [ ] **Step 1: Write failing tests** (node:test, same style as `operator-auth.test.ts`, fake clock):
  - five failures → `check` gives `allowed: false` and `retryAfterSeconds` in `1..900`;
  - advancing past 15 min → allowed;
  - `recordSuccess` clears the client;
  - 50 failures spread over 50 keys → a fresh key is blocked;
  - `maxClients: 2` with keys a, b, c → a's failures are forgotten;
  - `loginClientKey` returns `"direct"` when not trusted, the first trimmed XFF hop when trusted, and `"direct"` when trusted but the header is missing.
- [ ] **Step 2: Run** `npm test` in `apps/web`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** Store failures as timestamp arrays in a `Map` (insertion order gives eviction order; re-insert on update). In the route, compute the key with `MIRAGE_TRUST_PROXY_HEADERS === "true"`, check before `request.json()`, and return 429 `{ detail: "Too many login attempts" }` with `Retry-After`. Record a failure on a wrong password and a success on authentication.
- [ ] **Step 4: Run** `npm test`, `npm run lint -- --max-warnings 0` and `npx tsc --noEmit`. Expected: pass, 0 warnings.
- [ ] **Step 5: Commit** `feat(web): throttle operator login attempts`.

### Task 9: Network segmentation, non-root images, CI pins

**Files:**
- Modify: `infra/docker-compose.yml`, `apps/gateway/Dockerfile`, `apps/decoy/Dockerfile`, `apps/real-app-demo/Dockerfile`, `apps/web/Dockerfile`, `.github/workflows/ci.yml`, `README.md` (deployment notes: new variables)

**Interfaces:** none (configuration).

- [ ] **Step 1: Write the failing check.** Add a CI step to the lint job:
  `docker compose -f infra/docker-compose.yml config --quiet`, with `env:` dummy values for every `:?` variable. Add a script `infra/check-compose.py` (run with `python`), which loads `docker compose ... config --format json` and asserts:
  - the decoy's networks equal `{"apps"}`;
  - the db's equal `{"data"}`;
  - the real app's equal `{"apps"}`;
  - the web's equal `{"edge"}`;
  - the gateway's equal `{"edge", "apps", "data"}`;
  - `apps` and `data` are `internal: true`;
  - every service has `no-new-privileges:true`.

  Run it locally if Docker is available; otherwise rely on CI. Record a ruling if it is skipped locally.
- [ ] **Step 2: Run** `python infra/check-compose.py`. Expected: FAIL (no networks yet), or "docker unavailable" (ruling).
- [ ] **Step 3: Implement.**
  - Compose: add the networks and `security_opt`, and pass through `TRUSTED_PROXIES`, `MIRAGE_MODEL_ARTIFACT_SHA256`, `PAYLOAD_EXEMPTIONS`, `PROXY_MAX_RESPONSE_BYTES` and `RATE_LIMIT_MAX_CLIENTS`. The web gets `MIRAGE_TRUST_PROXY_HEADERS`.
  - Python Dockerfiles: `RUN useradd --uid 10001 --create-home mirage` after the install step, then `USER mirage`.
  - Web runtime stage: `USER node`.
  - CI:
    - `python -m pip install pip==<pinned>`;
    - `pip install pip-audit==<pinned>`;
    - `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.

    Pick the pins from `pip index versions pip` and `pip index versions pip-audit` (the latest release at least two weeks old) and record them in the ledger.
- [ ] **Step 4: Run** `python infra/check-compose.py` (if Docker is available) and a YAML parse of `ci.yml` (`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`). Expected: pass.
- [ ] **Step 5: Commit** `chore(infra): segment compose networks, run containers as non-root, pin CI tooling`.
