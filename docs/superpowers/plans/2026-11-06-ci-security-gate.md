# CI Security Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every push and PR to `main` runs tests for all four services plus lint, dependency-audit, and secret-scan gates, and any failure blocks the change.

**Architecture:** One GitHub Actions workflow (`.github/workflows/ci.yml`) with six parallel jobs (`gateway`, `decoy`, `real-app`, `web`, `lint`, `secrets`). Lint config lives in a root `ruff.toml`; secret-scan config in a root `.gitleaks.toml`. Each task adds one job plus whatever the job needs to pass.

**Tech Stack:** GitHub Actions, Python 3.13, pytest, pip-audit, ruff 0.17.4, Node 20, npm, gitleaks 8.30.1.

**Spec:** `docs/superpowers/specs/2026-11-06-ci-security-gate-design.md`

## Global Constraints

- Branch: `ci/security-gate` (already created from `origin/main`; spec committed as `ea16922`).
- Triggers: `push` to `main`, `pull_request` targeting `main`. No path filters.
- Top-level `permissions: contents: read`; no job adds permissions.
- Runner: `ubuntu-latest`. Python `3.13`. Node `20`.
- Actions pinned by full SHA with version comment:
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
  - `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0`
  - `actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0`
- gitleaks `8.30.1`, linux x64 tarball SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`.
- ruff pinned `0.17.4`.
- Lint findings are fixed, not baselined. Allowed exception form: line-level `# noqa: <CODE>  # <reason>`.
- A test exposing a real defect is not fixed here: mark `@pytest.mark.xfail(strict=True, reason="defect: <what>; fixed in sub-project <N>")` and list it in the PR body.
- A vulnerability with no fixed release: `pip-audit --ignore-vuln <ID>` (or npm `overrides`) with a `# <date> <reason>` comment in the workflow. Otherwise upgrade within the declared range.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Python 3.13 vs local 3.14.** Tests pass locally on 3.14 but CI uses 3.13 — the PR run in Task 7 is the real check; any 3.13-only failure is fixed, not skipped.
2. **`next build` without environment variables.** CI has no `.env`; route handlers read `process.env` at request time and must not be evaluated during build. Task 4 runs the build with an empty environment locally to prove this.
3. **Gitleaks false positives on fake test credentials** (e.g. dummy API keys in `apps/gateway/tests`, `apps/web/src/lib/*.test.ts`). Allowlist by exact string in `.gitleaks.toml`; never allowlist a path. Task 5 runs the scan over full history locally first.
4. **Untracked local files.** `apps/gateway/artifacts`, `apps/gateway/data`, `mirage.db` exist only locally. Tests already use `sqlite+aiosqlite:///:memory:` (`tests/conftest.py:9`) and `tmp_path`; Task 1 proves it by running the suite from a fresh clone.
5. **Test files leaking into the repo.** `test_ml_shadow.py` / `test_ml_training.py` write `.test-*.joblib` into the CWD. Task 1 checks `git status` is clean after a run.

Note for sub-project 3 (do not change here): `tests/conftest.py:10` sets `MIRAGE_API_KEY=""`, so gateway tests rely on fail-open auth.

---

### Task 1: Gateway job and working local environment

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify (if tests fail on a real defect): affected `apps/gateway/tests/test_*.py` (xfail marker only)

**Interfaces:**
- Produces: `ci.yml` with `name: CI`, the triggers and top-level `permissions` from Global Constraints, and a `jobs:` map that later tasks append to.

- [ ] **Step 1: Reinstall the local gateway venv**

Run (from `apps/gateway`): `venv/Scripts/python.exe -m pip install -e ".[dev,ml,postgres]"`
Expected: completes; `venv/Scripts/python.exe -c "import joblib, sklearn"` exits 0.

- [ ] **Step 2: Run the suite locally**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: all pass. For each failure: if it is a defect in product code, apply the xfail rule from Global Constraints; if it is an environment/test bug, fix the test.

- [ ] **Step 3: Prove the suite needs no untracked files and leaves none behind**

Run: `git clone --quiet . "$SCRATCH/mirage-clean" && cd "$SCRATCH/mirage-clean/apps/gateway" && <gateway venv python> -m pytest -q && git status --porcelain`
Expected: same pass count as Step 2; `git status --porcelain` prints nothing (add any generated file pattern to `.gitignore` if it does).

- [ ] **Step 4: Write `ci.yml` with the `gateway` job**

Job `gateway`, `defaults.run.working-directory: apps/gateway`:
checkout → setup-python (`python-version: "3.13"`, `cache: pip`, `cache-dependency-path: apps/gateway/pyproject.toml`) →
`pip install -e ".[dev,ml,postgres]"` → `pytest -q` → `pip install pip-audit` → `pip-audit --skip-editable`.

- [ ] **Step 5: Run pip-audit locally against the gateway venv**

Run: `venv/Scripts/python.exe -m pip install pip-audit && venv/Scripts/python.exe -m pip_audit --skip-editable`
Expected: "No known vulnerabilities found". Otherwise apply the vulnerability rule from Global Constraints and re-run.

- [ ] **Step 6: Validate workflow syntax**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` (use the scratch tools venv; `pip install pyyaml` there).
Expected: exits 0.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/ci.yml apps/gateway
git commit -m "ci: add gateway test and dependency audit job"
```

---

### Task 2: Decoy and real-app jobs

**Files:**
- Modify: `apps/decoy/pyproject.toml`, `apps/real-app-demo/pyproject.toml` (add `[project.optional-dependencies] dev = ["pytest>=8.0.0,<9.0.0", "httpx>=0.27.0,<1.0.0"]`)
- Create: `apps/real-app-demo/tests/__init__.py` (only if `apps/decoy/tests` has one — mirror it), `apps/real-app-demo/tests/test_real_app.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `ci.yml` from Task 1.

- [ ] **Step 1: Write `apps/real-app-demo/tests/test_real_app.py`**

Use `fastapi.testclient.TestClient(app)` from `app.main`. These are characterization tests of existing behavior, so they pass on first run; Step 2 proves they can fail.

```python
def test_health():            # GET /health -> 200, == {"status": "healthy"}
def test_products():          # GET /api/products -> 200, [p["name"] for p in body["products"]] == ["Sentinel Basic", "Sentinel Pro"]
def test_current_user():      # GET /api/users/me -> 200, == {"id": 42, "name": "Demo Operator", "role": "analyst"}
def test_catch_all_echoes_method_and_path():  # POST /api/orders/7 -> 200, == {"service": "protected-demo-app", "method": "POST", "path": "/api/orders/7", "status": "ok"}
def test_docs_disabled():     # GET /docs -> body is the catch-all echo (not Swagger HTML): body["path"] == "/docs"
```

- [ ] **Step 2: Prove the tests detect a change**

Temporarily change `"healthy"` to `"ok"` in `apps/real-app-demo/app/main.py`, run `pytest -q` in `apps/real-app-demo`, expect `test_health` FAIL; revert.

- [ ] **Step 3: Install and run both services' tests in a scratch venv (Python 3.13 if available via `py -3.13`, else 3.14)**

Run per service: `pip install -e ".[dev]" && pytest -q && pip install pip-audit && pip-audit --skip-editable`
Expected: tests pass; no known vulnerabilities.

- [ ] **Step 4: Add `decoy` and `real-app` jobs to `ci.yml`**

Same shape as `gateway` with `working-directory` `apps/decoy` / `apps/real-app-demo` and install `-e ".[dev]"`.

- [ ] **Step 5: Commit**

```bash
git add apps/decoy/pyproject.toml apps/real-app-demo .github/workflows/ci.yml
git commit -m "ci: test and audit decoy and real-app services"
```

---

### Task 3: Ruff lint gate

**Files:**
- Create: `ruff.toml` (repo root)
- Modify: Python files flagged by ruff (list below)
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `ruff.toml` used by the `lint` job and the README section (Task 6).

Baseline measured 2026-11-06 with the config below: 46 `I001`, 5 `E501` (at length 100), 5 `E402`, 2 `B008`, 1 `S104`, 1 `S311`.

- [ ] **Step 1: Write `ruff.toml`**

```toml
target-version = "py311"
line-length = 100
extend-exclude = ["apps/web", "**/venv", "**/migrations/versions", "**/*.egg-info", "**/pytest-tmp", ".tmp", "pytest-tmp"]

[lint]
select = ["E", "F", "B", "I", "S"]

[lint.per-file-ignores]
"**/tests/**" = ["S101", "S105", "S106"]

[lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Query", "fastapi.Depends", "fastapi.Security"]
```

`extend-immutable-calls` is how ruff documents FastAPI's default-argument idiom; it resolves both `B008` findings in `apps/gateway/app/api/routes/dashboard.py` without suppression.

- [ ] **Step 2: Run ruff and confirm the baseline**

Run: `ruff check . --statistics`
Expected: `I001` 46, `E402` 5, `E501` 5, `S104` 1, `S311` 1 (B008 gone).

- [ ] **Step 3: Auto-fix import order**

Run: `ruff check . --select I --fix`, then the full gateway/decoy test suites.
Expected: `I001` 0; tests still pass.

- [ ] **Step 4: Fix the remaining 12 by hand**

- `E501` ×5 (`apps/gateway/app/services/logger.py`, `apps/gateway/tests/test_api_domain_training_collector.py`, `apps/gateway/tests/test_dataset_preparation.py` ×3): wrap the line.
- `E402` ×5 in `apps/gateway/scripts/generate_custom_api_dataset.py` (imports after the `sys.path.insert` bootstrap at lines 13-14): `# noqa: E402  # imported after sys.path bootstrap so the script runs standalone`.
- `S104` `apps/gateway/app/core/config.py:49` (`HOST` default `0.0.0.0`): `# noqa: S104  # container bind address; HOST env overrides`.
- `S311` `apps/gateway/app/ml/datasets.py:721` (`random.Random(random_seed)`): `# noqa: S311  # seeded, reproducible split; not security-sensitive`.

- [ ] **Step 5: Verify clean**

Run: `ruff check .` then the gateway, decoy, and real-app test suites.
Expected: `All checks passed!`; all suites pass.

- [ ] **Step 6: Add `lint` job to `ci.yml`**

checkout → setup-python 3.13 → `pip install ruff==0.17.4` → `ruff check .` (repo root).

- [ ] **Step 7: Commit**

```bash
git add ruff.toml apps .github/workflows/ci.yml
git commit -m "ci: add ruff lint gate with security rules"
```

---

### Task 4: Web job

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify (only if a check fails): files under `apps/web/src`, `apps/web/package.json` / `package-lock.json`

Baseline measured 2026-11-06: lint, `tsc --noEmit`, and `npm test` pass. `npm audit` fails with 22 findings (1 critical, 5 high, 16 moderate), including **critical unauthenticated RCE advisories in `next@16.2.11`** (e.g. GHSA-2464-fhr4-w9xw, GHSA-673q-mjm6-r5xr; fixed in 16.4.5). Several findings are caused by the stale `overrides` block in `package.json`, which pins now-vulnerable versions. Do not run `npm audit fix --force`: it proposes downgrading `eslint-config-next` to 15.x.

- [ ] **Step 1: Upgrade the vulnerable dependencies**

In `apps/web/package.json`:
- `next` → `16.4.5`; `eslint-config-next` → `16.4.5` (keep them equal).
- `overrides`: `minimatch` → `>=11.0.1` latest 11.x; `sharp` → `>=0.35.5` latest; `js-yaml` → latest `5.x` above `5.4.0`; add `brace-expansion` ≥ `5.0.12`, `source-map-js` ≥ `1.2.2`, `browserslist` > `4.28.6`, `baseline-browser-mapping` ≥ `2.11.0`, `zod` ≥ `4.6.6` **only if** `npm update` alone does not lift them. Resolve exact versions with `npm view <pkg> version` at implementation time.
- Remove any override no longer needed after the upgrade (an override that equals what npm would resolve anyway is dead config).

Run `npm install`, then `npm audit`.
Expected: `found 0 vulnerabilities`.

- [ ] **Step 1b: Re-run every web check after the upgrade**

`npm run lint`, `npx tsc --noEmit`, `npm test`, `npm audit --omit=dev --audit-level=low`, `npm audit --audit-level=high`.
Expected: all exit 0. Fix any lint/type breakage from the Next upgrade in code.

- [ ] **Step 2: Prove the build needs no secrets**

Run: `env -i PATH="$PATH" HOME="$HOME" npm run build`
Expected: build succeeds. If a page reads env at build time, make that route dynamic (`export const dynamic = "force-dynamic"`) rather than adding env to CI.

- [ ] **Step 3: Add `web` job to `ci.yml`**

`working-directory: apps/web`; checkout → setup-node (`node-version: "20"`, `cache: npm`, `cache-dependency-path: apps/web/package-lock.json`) → `npm ci` → `npm run lint` → `npx tsc --noEmit` → `npm test` → `npm run build` → `npm audit --omit=dev --audit-level=low` → `npm audit --audit-level=high`.

- [ ] **Step 4: Commit**

Two commits, so the security fix can be cherry-picked on its own:

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "fix(web): upgrade next to 16.4.5 and refresh dependency overrides"
git add apps/web .github/workflows/ci.yml
git commit -m "ci: add web lint, typecheck, test, build and audit job"
```

---

### Task 5: Secret scan

**Files:**
- Create: `.gitleaks.toml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Run gitleaks over full history locally**

Download the Windows binary for 8.30.1 to the scratchpad; run from repo root:
`gitleaks git --config .gitleaks.toml --redact --verbose .` (first with no config file present).
Expected: a list of findings, or none.

- [ ] **Step 2: Classify every finding**

For each: a real secret → stop and report to the user (rotate first; do not allowlist). A synthetic placeholder or test dummy → add its exact value to `.gitleaks.toml`:

```toml
[extend]
useDefault = true

[allowlist]
description = "Synthetic placeholders and test dummies; exact values only"
regexTarget = "match"
regexes = [ '''<exact escaped value>''' ]  # one per value, with a comment naming where it lives
```

- [ ] **Step 3: Re-run**

Run: `gitleaks git --config .gitleaks.toml --redact .`
Expected: `no leaks found`.

- [ ] **Step 4: Prove the scan still catches a real-looking secret**

Create an uncommitted scratch file with a fabricated AWS-format key (`AKIA` + 16 uppercase chars), run `gitleaks dir --config .gitleaks.toml <file>`, expect 1 finding; delete the file.

- [ ] **Step 5: Add `secrets` job to `ci.yml`**

checkout with `fetch-depth: 0` → download `https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz` → `echo "<sha256>  gitleaks_8.30.1_linux_x64.tar.gz" | sha256sum -c -` → extract → `./gitleaks git --config .gitleaks.toml --redact .`

- [ ] **Step 6: Commit**

```bash
git add .gitleaks.toml .github/workflows/ci.yml
git commit -m "ci: scan full git history for secrets"
```

---

### Task 6: Dependabot and local-check docs

**Files:**
- Create: `.github/dependabot.yml`
- Modify: `README.md` (new section "Running checks locally", after "Quick Start")

- [ ] **Step 1: Write `.github/dependabot.yml`**

`version: 2`; weekly `pip` updates for `/apps/gateway`, `/apps/decoy`, `/apps/real-app-demo`; weekly `npm` for `/apps/web`; weekly `github-actions` for `/`.

- [ ] **Step 2: Add the README section**

List the exact commands each CI job runs, grouped by job, with working directories. Include the gateway install line `pip install -e ".[dev,ml,postgres]"`.

- [ ] **Step 3: Validate YAML** (same command as Task 1 Step 6, on `dependabot.yml`). Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add .github/dependabot.yml README.md
git commit -m "ci: add dependabot and document local checks"
```

---

### Task 7: Push, open PR, verify green

- [ ] **Step 1: Push** — `git push -u origin ci/security-gate`
- [ ] **Step 2: Open PR to `main`** — `gh pr create` titled `ci: add security gate (tests, lint, audit, secret scan)`; body lists the six jobs, any xfailed tests with their routed sub-project, any ignored vulnerabilities with reasons, and ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- [ ] **Step 3: Watch the run** — `gh pr checks --watch`
Expected: all six jobs pass. Fix any failure on the branch (Review Focus 1–3 are the likely causes) and push again.
- [ ] **Step 4: Report** — tell the user the PR link and ask whether to mark the six checks as required in branch protection for `main` (spec: out of scope without their approval).
