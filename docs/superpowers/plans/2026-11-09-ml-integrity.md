# ML Pipeline Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Only models trained on gateway-observable features, measured on an honest holdout and judged against analyst labels can reach live routing, and never below the signature floor.

**Architecture:** Contract v3 drops flow features and the CICIDS source; the decision engine gets a mode-independent HIGH/CRITICAL floor; promotion compares model and heuristic on analyst-labelled shadow events; the split groups identical feature vectors; artifacts load once from verified bytes; retraining prunes old artifacts.

**Tech Stack:** Python 3.13, FastAPI, pydantic v2, scikit-learn, joblib, pytest (asyncio auto).

**Spec:** `docs/superpowers/specs/2026-11-09-ml-integrity-design.md`

## Global Constraints

- `FEATURE_CONTRACT_VERSION = 3`; the six removed features are `flow_duration_ms`, `flow_packets_per_second`, `packet_length_mean`, `syn_flag_count`, `destination_port`, `average_packet_size`.
- Review defaults: precision ≥ 0.90, recall ≥ 0.60, F1 ≥ 0.70, false-positive rate ≤ 0.02, training rows ≥ 100, test rows ≥ 30.
- `ML_PROMOTION_MIN_LABELED_EVENTS` default 100; `ML_PROMOTION_MIN_AGREEMENT_RATE` removed everywhere.
- Retention keeps the newest 5 `risk_model_*.joblib`; never the configured `MIRAGE_MODEL_ARTIFACT`.
- Gateway commands from `apps/gateway`: `venv/Scripts/python.exe -m pytest -q`; lint from the repo root: `apps/gateway/venv/Scripts/python.exe -m ruff check .` (ruff 0.17.4, never a global ruff).
- Settings are read at call time (`from app.core import config`); modules whose tests patch a module-level `settings` keep that pattern.
- Commits: conventional, **no** `Co-Authored-By` or session trailers. No push.

## Review Focus

1. Events stored before this change have an `ml_shadow` without `heuristic_decision`: they must read back without error and fall back to the event's final decision. Test in Task 3.
2. `MIRAGE_MODEL_ARTIFACT` given as a relative path while retention lists absolute paths: the configured file must still be protected (compare resolved paths). Test in Task 7.
3. A class whose rows are all identical forms a single group: the split must fail with a clear "fewer than 2 groups" error, not produce an empty test class. Test in Task 4.
4. A test split with no negatives makes the false-positive rate undefined: review must block with a clear message, not pass. Test in Task 5.
5. A v2 artifact configured after upgrade: shadow scoring turns off with the contract blocker, and requests keep flowing. Test in Task 1.

---

### Task 1: Feature contract v3 and CICIDS removal

**Files:** `app/services/feature_extraction.py`, `app/schemas/request.py`, `app/ml/{datasets.py,csic_http.py,api_log_review.py}`, `scripts/{prepare_dataset.py,build_api_domain_fixture_dataset.py,smoke_ml_shadow.py}` and any script with a `cicids` option, tests touching flow features or CICIDS, `docs/dataset-preparation.md`, READMEs, `apps/gateway/pyproject.toml` (drop pandas).

**Interfaces:** Produces `FEATURE_NAMES` (15 names, v2 order minus the six) and `FEATURE_CONTRACT_VERSION = 3`.

- [ ] Step 1: Tests (RED): `test_feature_contract_v3_has_no_flow_features` (version 3, none of the six names, `set(extract_features(req)) == set(FEATURE_NAMES)`); `test_inspect_request_ignores_legacy_flow_fields` (`InspectRequest.model_validate({...,"flow_duration_ms": 5})` succeeds and has no such attribute); `test_v2_artifact_disables_shadow_scoring` (artifact with `feature_contract_version=2` → `_load_classifier()` is `None`, a proxied request still returns 200); `test_prepare_dataset_rejects_cicids_source` (CLI exits non-zero for `--source cicids`).
- [ ] Step 2: Run them; expect failures on version, field presence and the CLI.
- [ ] Step 3: Remove the six features from the contract, schema, loaders and scripts; delete the CICIDS loader, `_first_present` if unused, the `cicids` `DatasetSource` value, its tests and docs sections; remove `pandas` from the `ml` extra. Update test fixtures that build feature dicts to the v3 names.
- [ ] Step 4: Full suite green; `grep -rn "flow_duration\|syn_flag\|destination_port\|cicids\|CICIDS\|pandas" apps docs README.md` shows only historical specs/plans.
- [ ] Step 5: Commit `feat(ml)!: drop flow features and the CICIDS source (feature contract v3)`.

### Task 2: Signature floor in every routing mode

**Files:** `app/services/decision_engine.py`, `tests/test_decision_engine.py`, `tests/test_hybrid_routing.py`.

- [ ] Step 1: Tests (RED): `test_ml_only_redirects_high_risk_even_when_model_allows` and the same for CRITICAL; `test_ml_only_follows_model_below_high` (MEDIUM risk + shadow "allow" → ALLOW); hybrid HIGH + shadow allow → redirect (regression).
- [ ] Step 2: Run; the ml_only HIGH case fails.
- [ ] Step 3: Make the HIGH/CRITICAL → `REDIRECT_TO_DECOY` rule the first check in `make_decision`, before mode branches; remove the now-duplicate check in the hybrid branch.
- [ ] Step 4: Tests green.
- [ ] Step 5: Commit `fix(gateway): keep the signature floor in ml_only routing`.

### Task 3: Promotion judged against analyst labels

**Files:** `app/schemas/ml.py`, `app/services/inspection.py`, `app/services/ml_shadow.py`, `app/services/ml_promotion.py`, `app/core/config.py`, `app/core/settings_validation.py` (if it references the agreement setting), `infra/docker-compose.yml`, `.env.example` files, docs, `apps/web` only if it renders the removed setting (grep), tests.

**Interfaces:**
- `MLShadowScore.heuristic_decision: Literal["allow","monitor","redirect_to_decoy"] | None = None`.
- `@dataclass(frozen=True) class ClassifierRates(precision: float, recall: float, false_positive_rate: float)`; `@dataclass(frozen=True) class LabeledComparison(events: int, model: ClassifierRates, heuristic: ClassifierRates)`; `labeled_shadow_comparison(events: Iterable[EventRecord]) -> LabeledComparison` in `app/services/ml_promotion.py`. Rates with a zero denominator are `0.0`.
- Setting `ml_promotion_min_labeled_events: int` (`ML_PROMOTION_MIN_LABELED_EVENTS`, default 100).

- [ ] Step 1: Tests (RED):
  - `test_shadow_score_records_heuristic_decision` (inspection fills it).
  - `test_labeled_comparison_rates`: 4 events, labels/decisions chosen so model precision 1.0 recall 0.5 and heuristic precision 0.5 recall 0.5; assert exact values and `events == 4`.
  - `test_labeled_comparison_falls_back_to_final_decision` (shadow without `heuristic_decision`).
  - `test_old_shadow_rows_read_back` (stored JSON without the field → model validates).
  - Gate: passes when model ≥ heuristic on both; fails when model precision lower; fails below `ML_PROMOTION_MIN_LABELED_EVENTS`; agreement 0.5 no longer blocks (the `shadow_agreement_rate` gate is still reported but excluded from the blocking set).
- [ ] Step 2: Run; expect failures.
- [ ] Step 3: Implement; fetch labelled events with `store.get_labeled_events(limit=10000)` in the promotion endpoint path (as retraining does); make the agreement gate informational; delete `ml_promotion_min_agreement_rate` and its env var everywhere.
- [ ] Step 4: Tests green; grep shows no `MIN_AGREEMENT_RATE`.
- [ ] Step 5: Commit `feat(ml): gate promotion on analyst labels instead of heuristic agreement`.

### Task 4: Grouped split

**Files:** `app/ml/datasets.py` (`stratified_split`, manifest), `app/ml/dataset_review.py` if it reads manifest fields, tests.

**Interfaces:** the split reports `conflicting_feature_groups: int`, stored in the manifest. Keep `stratified_split`'s current return shape if possible and add the count through a small result dataclass; name the choice in the commit message.

- [ ] Step 1: Tests (RED): `test_identical_rows_stay_on_one_side` (10 copies of one vector + varied rows → copies all in train or all in test); `test_grouped_split_is_reproducible`; `test_conflicting_groups_counted_and_assigned_by_majority`; `test_single_group_class_is_rejected` (all suspicious rows identical → error mentioning "groups").
- [ ] Step 2: Run; expect failures.
- [ ] Step 3: Group by SHA-256 of `json.dumps([row.features[name] for name in FEATURE_NAMES])`; shuffle groups per majority label with the seeded RNG; fill the test share per label with whole groups.
- [ ] Step 4: Tests green (update fixtures that relied on row-level counts).
- [ ] Step 5: Commit `fix(ml): keep identical feature vectors on one side of the split`.

### Task 5: Stricter review thresholds

**Files:** `app/ml/artifacts.py`, `app/services/retraining.py`, the review script(s) in `scripts/`, tests, docs.

- [ ] Step 1: Tests (RED): `test_review_blocks_fpr_above_two_percent`; `test_review_blocks_small_training_set` (99 rows); `test_review_passes_artifact_meeting_all_thresholds`; `test_review_blocks_undefined_false_positive_rate` (metrics without a false-positive rate → blocker "False-positive rate is unavailable").
- [ ] Step 2: Run; expect failures.
- [ ] Step 3: Change the defaults to the Global Constraints values; treat a missing FPR as a blocker; script `--help` shows the defaults; retraining uses the same defaults. Existing tests that are not about thresholds pass explicit lower thresholds or better fixtures.
- [ ] Step 4: Tests green.
- [ ] Step 5: Commit `fix(ml): raise artifact review thresholds for decoy routing`.

### Task 6: Load once from verified bytes

**Files:** `app/ml/artifact_integrity.py`, `app/ml/artifacts.py`, `app/ml/inference.py`, `app/services/ml_shadow.py`, tests.

**Interfaces:** `load_verified_artifact(path: Path, expected_sha256: str | None) -> Any`; `RiskClassifier.from_artifact(artifact: dict) -> RiskClassifier`; the review exposes the loaded artifact for reuse (one named function, chosen by the implementer and named in the commit).

- [ ] Step 1: Tests (RED): `test_loads_the_bytes_that_were_hashed` (the file is read once; contents swapped after the read do not change what loads); `test_shadow_loader_loads_artifact_once` (`joblib.load` called once).
- [ ] Step 2: Run; expect two loads.
- [ ] Step 3: Implement with `io.BytesIO`; route every serving-path load through it.
- [ ] Step 4: Tests green.
- [ ] Step 5: Commit `fix(ml): load artifacts once from the verified bytes`.

### Task 7: Retraining artifact retention

**Files:** `app/services/retraining.py`, `tests/test_retraining.py`.

**Interfaces:** `prune_retraining_artifacts(directory: Path, *, keep: int = 5, protected: Path | None) -> list[Path]` (returns deleted paths).

- [ ] Step 1: Tests (RED): seven files with increasing mtimes → five newest kept; the oldest protected via a relative `MIRAGE_MODEL_ARTIFACT` path → kept (six remain); unrelated files untouched; a deletion error is logged, not raised.
- [ ] Step 2: Run; expect NameError.
- [ ] Step 3: Implement (compare `Path.resolve()`); call after a successful retraining run.
- [ ] Step 4: Tests green.
- [ ] Step 5: Commit `feat(ml): keep only the newest retraining artifacts`.

### Task 8: Retrain CSIC under v3 and record it

**Files:** `docs/dataset-preparation.md` (and `docs/model-artifacts.md` if it shows old thresholds or v2 runs).

- [ ] Step 1: Prepare the CSIC dataset from `apps/gateway/data/csic-2010` with the documented `scripts/prepare_dataset.py` command into `data/prepared/csic-http-2010-v3/`; review it; train with `scripts/train_model.py --manifest ...` into `artifacts/csic-http-2010-risk-model-v3.joblib`; review the artifact with default thresholds. If the source data is absent, record that and skip.
- [ ] Step 2: Record row counts, `conflicting_feature_groups`, metrics, review outcome (pass, or blockers verbatim) and the artifact SHA-256 in `docs/dataset-preparation.md`, replacing v2 claims.
- [ ] Step 3: Full suite and ruff green.
- [ ] Step 4: Commit `docs(ml): record the contract v3 CSIC training run`.
- [ ] Step 5: Controller only, after merge: close PR #62 with a comment that pandas was unused and removed.
