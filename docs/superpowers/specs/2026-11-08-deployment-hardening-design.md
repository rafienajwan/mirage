# Deployment and Auth Hardening — Design

Sub-project 3 of the repository hardening effort (2026-11-06 review).
Depends on sub-projects 1 (CI gate) and 2 (payload detection), both merged.

## Problem

Measured on 2026-11-08 against `main` (`1125d03`).

1. **The gateway fingerprints itself to attackers.** The attacker-facing proxy
   (`/api/v1/proxy/*`) and the operator API share one public port (8000).
   Reachable without credentials:
   - `/docs`, `/redoc` and `/openapi.json`, whose description reads
     "AI-powered cyber deception defense gateway";
   - `/`, which returns the service name and a link to `/docs`;
   - `/api/v1/decoy/status`, which lists every fake endpoint.

   An attacker who finds any of these knows the decoy is a decoy.
2. **Auth fails open.** `require_api_key` admits every request when
   `MIRAGE_API_KEY` is unset, in every environment. Nothing stops a production
   start with placeholder decoy tokens (`*_NOT_CONFIGURED`), a short ticket
   secret, or an in-memory database.
3. **Client IPs are unreliable.** The proxy and the rate limiter key on
   `request.client.host`. Behind a reverse proxy, that is the proxy's address
   for every client, so one attacker can throttle everyone, or every attacker
   is merged into one actor. There is no setting for trusted proxies.
4. **Unbounded state.** The rate limiter keeps a deque per IP forever. An
   attacker rotating source addresses grows gateway memory without limit.
   (`traffic_tracker` is already capped by `max_sources`.)
5. **Upstream handling.** `forward_request` opens a new `httpx.AsyncClient`
   per request (no connection reuse) and buffers the whole upstream response
   in memory, with no size cap.
6. **Model files execute code.** `joblib.load` unpickles the configured
   `MIRAGE_MODEL_ARTIFACT`. Anyone who can replace that file gets code
   execution in the gateway. Nothing checks the file's integrity.
7. **Option-A false positives have no escape hatch.** Routes that legitimately
   accept code or rich text (sub-project 2, "Known false positives") are
   routed to the decoy, and there is no way to exempt them.
8. **Operator login is not throttled.** `POST /api/auth/login` (web) accepts
   unlimited password guesses.
9. **Flat network.** All compose services share the default network: the
   decoy, an attacker-controlled surface by design, can reach Postgres and
   the real app. Every container runs as root.
10. **CI minors.** pip and pip-audit are unpinned; `cancel-in-progress`
    cancels `main` runs too; web lint warnings do not fail the build; the
    pytest-asyncio loop scope is implicit; the test temp directory is never
    removed.

## Goal

A production deployment (`APP_ENV=production`, the compose stack) is safe by
default: it refuses to start misconfigured, reveals nothing about MIRAGE on
any unauthenticated path, attributes traffic to the real client, has bounded
memory and network reach, and only loads the model file it was told to trust.
Local development (`APP_ENV=development`, the default) keeps working with no
extra configuration.

## Decisions

| Topic | Decision |
|---|---|
| Environments | `development` (default) keeps today's conveniences. Any other value is treated as production-like for auth (fail closed); `production` also runs the startup validation. |
| Forwarded headers | Interpreted in one place, the app. Uvicorn runs with `--no-proxy-headers`. |
| Trusted proxies | Explicit list; empty by default (forwarded headers ignored). |
| Rate-limit state | Per-process memory with a cap. A shared store (Redis) is out of scope. |
| Login throttle state | Per-process memory in the web app (single dashboard instance). |
| Exemptions | Configured by environment variable; they remove labels, never skip inspection. |

## Components

### `app/core/settings_validation.py` (new)

`production_config_errors(settings: Settings) -> list[str]` returns one
message per problem. Called in the application lifespan before `init_db()`
when `settings.app_env == "production"`; a non-empty list raises
`RuntimeError` listing every message, so the process exits at startup.

Errors:

- `MIRAGE_API_KEY` missing or shorter than 32 characters.
- `MIRAGE_DASHBOARD_TICKET_SECRET` missing or shorter than 32 characters.
- Any of `DECOY_LOGIN_TOKEN`, `DECOY_OAUTH_TOKEN`, `DECOY_SERVICE_TOKEN`
  still equal to its `*_NOT_CONFIGURED` default.
- `DATABASE_URL` is SQLite in memory (`:memory:` or `mode=memory`).
- `MIRAGE_MODEL_ARTIFACT` set without `MIRAGE_MODEL_ARTIFACT_SHA256`.
- `TRUSTED_PROXIES` contains an entry that is not an IP or CIDR.
- `PAYLOAD_EXEMPTIONS` does not parse.

Messages name the variable, never its value.

### `app/core/security.py`

`require_api_key`: when no key is configured, admit the request only if
`app_env == "development"`; otherwise respond **503** "API key not
configured". The configured-key path is unchanged (constant-time compare,
401 on mismatch).

### `app/main.py` and `app/api/routes/decoy.py`: no fingerprints

- `FastAPI(docs_url=..., redoc_url=..., openapi_url=...)` are `None` unless
  `app_env == "development"`.
- `/` is registered only in development; elsewhere it is a 404 like any
  unknown path.
- `GET /api/v1/decoy/status` requires the API key. The web dashboard
  already calls it server-side with the key.
- `/health` stays public (compose health checks). Today it returns the
  service name, version and environment; outside development it returns
  only `{"status": "ok"}`.

### `app/core/client_ip.py` (new)

- Setting `trusted_proxies: tuple[IPv4Network | IPv6Network, ...]`, parsed
  from `TRUSTED_PROXIES` (comma-separated IPs or CIDRs; empty by default).
- `client_ip(request: Request) -> str`. If the socket peer is not a trusted
  proxy, return the peer. Otherwise walk `X-Forwarded-For` from right to
  left, skipping trusted addresses, and return the first untrusted, valid
  IP. If every hop is trusted, return the leftmost valid entry. If the
  header is absent, return the peer; malformed entries stop the walk and
  yield the last trusted hop.
- Used by the proxy route (`source_ip`), the rate limiter and every other
  `request.client.host` use in `app/`.
- The gateway Dockerfile command adds `--no-proxy-headers`.

### `app/core/rate_limit.py`

- Keyed by `client_ip(request)`.
- Buckets emptied by expiry are deleted.
- At most `RATE_LIMIT_MAX_CLIENTS` keys (default **10,000**). When a new key
  arrives at the cap, purge expired buckets first; if still full, evict the
  least recently used key. Implemented with an `OrderedDict` moved to the end
  on access.
- Behavior for a client under the limit is unchanged (headers,
  429 + `Retry-After: 60`).

### `app/services/proxy_client.py`

- One module-level `httpx.AsyncClient` created in the lifespan
  (`timeout=PROXY_TIMEOUT_SECONDS`, `follow_redirects=False`) and closed on
  shutdown. `forward_request` uses it, or a temporary client if the lifespan
  has not run (tests that skip the lifespan).
- The upstream response is streamed. A `Content-Length` above
  `PROXY_MAX_RESPONSE_BYTES` (default **10,485,760**), or streamed bytes
  exceeding it, closes the stream and returns **502**
  "Upstream response too large". Below the cap, the response is returned
  exactly as today.

### `app/ml/artifact_integrity.py` (new)

- `verify_artifact_digest(path: Path, expected_sha256: str) -> None` streams
  the file through SHA-256 and raises `ArtifactIntegrityError` on mismatch.
  The expected value must be 64 lowercase hex characters (uppercase input is
  lowercased); anything else raises.
- `RiskClassifier.__init__` and `review_model_artifact` accept
  `expected_sha256: str | None`. When given, the digest is verified
  **before** `joblib.load`.
- `ml_shadow._load_classifier` passes `MIRAGE_MODEL_ARTIFACT_SHA256`.
  Without a digest (development only, because production validation rejects
  it), it logs a warning and loads as today. On a mismatch it logs, and the
  classifier stays `None` (shadow scoring off). It never loads the file.
- `ml_promotion` passes the digest to the reviewer the same way.
- The retraining result (`RetrainingRun`) gains `artifact_sha256`, so an
  operator can pin a newly trained model.
- Offline scripts (`training`, `evaluation`) are unchanged: they run on the
  operator's own files.

### `app/services/payload_exemptions.py` (new)

- Setting `PAYLOAD_EXEMPTIONS`: `;`-separated rules of the form
  `METHOD PATH_GLOB:label[,label...]`, e.g.
  `POST /api/posts:xss;PUT /api/snippets/*:rce-indicator,sql-like`.
  `METHOD` may be `*`. Labels must be known indicator labels. Parse errors
  fail production validation; in development they log and the rule is
  ignored.
- `apply_exemptions(method: str, path: str, indicators: list[str]) -> tuple[list[str], list[str]]`
  returns `(kept, exempted)`.
- A rule applies only when the path is **canonical**: no `%`, no `\`, no
  `//`, no `.` or `..` segment, no `;`. A non-canonical path is never
  exempted, so an exempt prefix cannot be used to reach another route
  (`/api/posts/..%2fadmin`).
- Glob matching uses `fnmatch.fnmatchcase`, where `*` also matches `/`.
  Documented: `/api/posts/*` matches any depth.
- In `proxy.py`, exemptions are applied after detection, and
  `payload_indicators` carries only `kept`. Exempted labels never reach
  `payload_indicators`, because `anomaly_engine` (2 or more labels) and the
  fingerprint would still count them. Instead `InspectRequest` gains
  `exempted_indicators: list[str] = []`, and the risk engine adds one
  zero-score reason per label (`Exempted payload indicator: xss`). Analysts
  see it on the event's reasons.

### Web: `apps/web/src/lib/login-throttle.ts` (new)

- `createLoginThrottle({ perClientLimit = 5, globalLimit = 50, windowMs = 15 * 60_000, now = Date.now })`
  returns `{ check(clientKey): { allowed: boolean; retryAfterSeconds: number }, recordFailure(clientKey), recordSuccess(clientKey) }`.
- Sliding window of failure timestamps per client, plus one global list.
  Blocked when a client has ≥ 5 failures, or there are ≥ 50 failures in
  total, within the window. `retryAfterSeconds` is the time until the oldest
  counted failure leaves the window (at least 1). A success clears that
  client's failures. At most 10,000 client keys; the oldest are evicted.
- The login route checks the throttle **before** reading the password and
  returns **429** with `Retry-After` when blocked. It records failures on
  401 and successes on authentication.
- The client key is the first `X-Forwarded-For` hop only when
  `MIRAGE_TRUST_PROXY_HEADERS=true`; otherwise it is the string `"direct"`,
  so the per-client limit then acts as a global limit too. Next.js exposes
  no socket address, so honoring forwarded headers is opt-in.

### `infra/docker-compose.yml` and Dockerfiles

- Networks:

  | Network | Members | `internal` |
  |---|---|---|
  | `edge` | web, gateway | no |
  | `apps` | gateway, real-app, decoy | yes |
  | `data` | gateway, db | yes |

  The decoy reaches only the gateway. The db and real-app are unreachable
  from the decoy and the web.
- Every service: `security_opt: ["no-new-privileges:true"]`.
- gateway, decoy and real-app Dockerfiles create and switch to a non-root
  user (`mirage`, uid 10001). The web runtime stage switches to the image's
  `node` user. Read-only mounts stay as they are.
- `TRUSTED_PROXIES`, `MIRAGE_MODEL_ARTIFACT_SHA256`, `PAYLOAD_EXEMPTIONS`
  and `PROXY_MAX_RESPONSE_BYTES` are passed through to the gateway
  (empty or default).
- Validated with `docker compose -f infra/docker-compose.yml config` in CI
  (a new step in the existing lint job), using dummy values for the
  required variables.

### CI (`.github/workflows/ci.yml`) and test setup

- Pin `pip` and `pip-audit` to exact versions.
- `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.
- Web lint: `npm run lint -- --max-warnings 0`. Existing warnings are fixed
  in this sub-project.
- `asyncio_default_fixture_loop_scope = "function"` in the gateway pytest
  configuration.
- Gateway `conftest.py`: set `APP_ENV=development` explicitly, and remove
  the temp database directory at session end.

## Error handling

- Startup validation raises one `RuntimeError` listing every problem;
  values are never echoed.
- Integrity failure, an unreadable model file, or an invalid digest:
  shadow scoring is off and a warning is logged. Request handling is
  unaffected.
- Upstream too large: 502, with the same body shape as the existing 502.
- Exemption rule errors: production fails at startup; development logs and
  ignores the rule.

## Testing

Each item gets a test that fails before its fix.

- `test_settings_validation.py`: every error case; a valid production
  configuration yields `[]`; a lifespan start in production with a missing
  key raises.
- `test_security.py`: no key + production → 503; no key + development → 200;
  wrong key → 401.
- `test_fingerprinting.py`: in production mode, `/docs`, `/redoc`,
  `/openapi.json` and `/` return 404; `/api/v1/decoy/status` without the
  key returns 401; `/health` does not contain "MIRAGE", "deception" or
  "decoy". The app is built through a factory or reloaded, so tests can
  construct it per environment: `create_app(settings)` in `app/main.py`,
  with the module-level `app = create_app(settings)` kept for uvicorn and
  existing tests. Route-level checks read `settings` at request time, so
  tests patch `settings` (a frozen dataclass, replaced via
  `dataclasses.replace` and monkeypatching the module attribute).
- `test_client_ip.py`: untrusted peer with a forged XFF → peer;
  trusted peer → rightmost untrusted hop; a chain of trusted hops; CIDR
  match; IPv6; malformed entries; no header.
- `test_rate_limit.py`: limit enforced; independent per client; expired
  buckets removed; the cap evicts the least recently used; uses
  `client_ip`.
- `test_proxy_client.py`: shared client reused across requests; response
  over the cap via `Content-Length` → 502; streamed body over the cap
  without `Content-Length` → 502; under the cap is byte-identical.
- `test_artifact_integrity.py`: match passes; mismatch raises before
  `joblib.load` is called (patched loader not invoked); bad digest format;
  shadow loader returns `None` on mismatch; the retraining run reports the
  digest.
- `test_payload_exemptions.py`: parsing (valid, bad label, bad syntax);
  matching method and glob; non-canonical paths never exempted
  (`..`, `%2f`, `//`, `\`, `;`); proxy integration: an exempt XSS post
  reaches the real app and the event's reasons include
  `Exempted payload indicator: xss`, while the same
  body on another route reaches the decoy.
- Web `login-throttle.test.ts`: 5 failures block, 6th returns blocked with a
  positive Retry-After; window expiry unblocks; success resets; the
  global limit blocks other clients; key eviction.
- CI: the compose config step passes.

## Success criteria

1. All tests above pass; CI green.
2. `docker compose config` validates the segmented topology.
3. With `APP_ENV=production` and no `MIRAGE_API_KEY`, the gateway exits at
   startup with a message naming the variable.

## Out of scope

- Per-analyst operator accounts (sub-project 5).
- Retraining, feature contract and ML evaluation changes (sub-project 4).
- A shared rate-limit store (Redis) or multi-instance deployments.
- TLS termination (the deployment's reverse proxy owns it; see `TRUSTED_PROXIES`).
- Deferred detection minors from sub-project 2 (header inspection, `%u`
  decoding).
