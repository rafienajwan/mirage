# CI Security Gate — Design

Sub-project 1 of 4 in the repository hardening effort (2026-11-06 review).
Order: (1) CI and test environment → (2) detection fix → (3) deployment and
auth hardening → (4) ML pipeline integrity. Shared per-analyst operator
accounts are tracked separately as a fifth item.

## Goal

Every push and pull request to `main` runs the full test suites of all four
services plus lint, dependency-vulnerability, and secret checks. Any failure
blocks the change. Later sub-projects land their regression tests into this
gate.

## Current state

- No `.github/` directory; nothing runs automatically.
- `apps/gateway/venv` was installed without the `ml` extra, so `pytest` fails
  at import (`ModuleNotFoundError: joblib`).
- Production image uses Python 3.13 (`apps/gateway/Dockerfile`); the local
  machine has 3.14; `requires-python = ">=3.11"`.
- Tests: gateway 28 files, decoy 1 file, real-app-demo none, web two
  `node --test` suites.
- No Python linter, type check, dependency audit, or secret scan.
- Git history contains no committed secrets: only `.env.example` variants
  were ever added; `.env`, databases, and model artifacts never were.

## Decisions

| Topic | Decision |
|---|---|
| Workflow layout | One file, `.github/workflows/ci.yml`, parallel jobs. No path filters (a skipped required check blocks merging). |
| Triggers | `push` to `main`, `pull_request` targeting `main`. |
| Python version | 3.13 only, matching the production image. |
| Node version | 20, matching the README prerequisite. |
| Lint findings | Fixed, not baselined. A justified exception is a line-level `# noqa: <code>  # <reason>`. |
| Workflow permissions | `contents: read` at the top level; no job escalates. |
| Third-party actions | Pinned to full commit SHA with the version in a trailing comment. |

## Jobs

All jobs run on `ubuntu-latest`. Each must pass.

### `gateway`

Working directory `apps/gateway`.

1. `pip install -e ".[dev,ml,postgres]"`
2. `pytest`
3. `pip install pip-audit && pip-audit` — audits the installed environment;
   any known vulnerability fails the job. The editable `mirage-gateway`
   package itself is skipped (`--skip-editable`).

### `decoy` and `real-app`

Each service's `pyproject.toml` gains a `dev` extra:
`pytest>=8,<9` and `httpx>=0.27,<1` (required by FastAPI's `TestClient`).

1. `pip install -e ".[dev]"`
2. `pytest`
3. `pip-audit --skip-editable`

`apps/real-app-demo` gains `tests/test_real_app.py` covering its three
routes: `GET /health`, `GET /api/products`, and `GET /api/users/me` each
return 200 with a JSON body whose top-level keys match the current
implementation.

### `web`

Working directory `apps/web`.

1. `npm ci`
2. `npm run lint`
3. `npx tsc --noEmit`
4. `npm test`
5. `npm run build`
6. `npm audit --omit=dev --audit-level=low` — any vulnerability in a
   production dependency fails.
7. `npm audit --audit-level=high` — high or critical in any dependency,
   including dev-only, fails.

### `lint`

A root `ruff.toml` applies to `apps/gateway`, `apps/decoy`, and
`apps/real-app-demo`:

- `target-version = "py311"` (the declared minimum).
- `select = ["E", "F", "B", "I", "S"]`.
- `per-file-ignores`: `S101` (assert) and `S105`/`S106` (hard-coded test
  credentials) in `**/tests/**`.
- Excludes `venv`, `migrations/versions`, `*.egg-info`, `pytest-tmp`.

Job steps: `pip install ruff==<version>` (exact version chosen at
implementation time and pinned in the workflow), then `ruff check .`.

### `secrets`

`gitleaks detect` over the full history (`fetch-depth: 0`). A root
`.gitleaks.toml` extends the default rules and allowlists only the
`*.env*.example` files' documented synthetic placeholder values, by exact
string, not by path.

The gitleaks binary is downloaded at a pinned version with its SHA-256
checksum verified, rather than using `gitleaks-action` (which requires a
license key for organization-owned repositories).

## Supporting changes

- `.github/dependabot.yml`: weekly updates for `pip` (each of the three
  Python services), `npm` (`apps/web`), and `github-actions`.
- `README.md`: a "Running checks locally" section listing the same commands
  CI runs.
- Local machine: reinstall `apps/gateway/venv` with
  `pip install -e ".[dev,ml,postgres]"`. Not committed.

## Failure handling during implementation

- A lint finding is fixed in place. If the fix would change runtime
  behavior, it is listed in the plan's notes and routed to sub-project 2, 3,
  or 4 instead of being changed here.
- A failing test that reveals a real defect is not patched in this
  sub-project; it is recorded and routed the same way. CI must still be green
  at merge, so such a test is marked `xfail(strict=True)` with the
  sub-project reference, ensuring it fails loudly once fixed.
- A vulnerable dependency is upgraded within its declared range; if no fixed
  version exists, it is recorded with a `pip-audit --ignore-vuln <ID>` /
  npm override and a dated reason in the workflow.

## Out of scope

- Making these checks required in GitHub branch protection: changes
  repository settings; requested separately after the first green run.
- Code formatting, type checking of Python (`mypy`), and container image
  scanning.
- Fixing the defects found in the 2026-11-06 review (sub-projects 2–4).

## Done when

1. Every command listed above passes locally.
2. The workflow runs green on GitHub for the `ci/security-gate` branch PR.
3. The gateway test suite runs on the local machine.
