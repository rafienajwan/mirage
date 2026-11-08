# ML Pipeline Integrity — Design

Sub-project 4 of the repository hardening effort (2026-11-06 review).
Depends on sub-projects 2 (payload detection) and 3 (deployment hardening,
artifact pinning), both merged.

## Goal

A model can only reach live routing when it was trained on features the
gateway actually observes, measured on an honest holdout, judged against
analyst labels rather than against the heuristic it is meant to improve on,
and never weaker than the attack signatures.

## Problem

Measured on 2026-11-09 against `main` (`2edc11b`).

1. **Train/serve skew on flow features.** `FEATURE_NAMES` (contract v2) ends
   with six network-flow features (`flow_duration_ms`,
   `flow_packets_per_second`, `packet_length_mean`, `syn_flag_count`,
   `destination_port`, `average_packet_size`). The gateway works at the HTTP
   layer and never fills them, so they are always 0 at serving time. CICIDS
   training data fills them, so a model can learn rules it will never see
   satisfied in production.
2. **CICIDS rows carry no HTTP signal.** Without the flow features, a CICIDS
   row has only zeros in every HTTP feature. The source cannot train an
   HTTP-layer model.
3. **`ml_only` has no signature floor.** In `ml_only` mode the shadow
   decision alone routes the request. A request with one SQL injection
   signature (heuristic level HIGH) is allowed to the real app when the
   model says "allow". Hybrid mode already redirects HIGH/CRITICAL.
4. **Promotion rewards imitation.** The promotion gate requires the model to
   agree with the heuristic on at least 80% of shadow events. A model that
   copies the heuristic passes; a model that catches what the heuristic
   misses fails.
5. **Leaky holdout.** `stratified_split` splits rows per label at random.
   CSIC 2010 repeats identical requests, so copies land in both train and
   test and inflate the metrics that gate review.
6. **Lenient review thresholds.** `review_model_artifact` defaults accept
   precision, recall and F1 of 0.5 and a false-positive rate of 0.5, with as
   few as 15 training and 5 test rows. For a deception gateway a false
   positive sends a real user to the decoy.
7. **Hash-then-load window and double load.** `verify_artifact_digest`
   hashes the file, then `joblib.load` reopens it, so a file swapped in
   between is loaded unverified. The shadow loader also loads the file twice
   (review, then `RiskClassifier`).
8. **Artifacts accumulate.** Every retraining run writes a new artifact and
   nothing removes old ones.
9. **Stale prepared dataset.** The prepared CSIC dataset was built before
   the sub-project 2 detector, so its payload indicator features are all 0.
10. **Dead dependency.** `pandas` is declared in the `ml` extra and imported
    nowhere. Dependabot PR #62 proposes widening its range.

## Decisions

| Topic | Decision |
|---|---|
| Flow features | Removed from the feature contract, `InspectRequest` and every dataset loader. `FEATURE_CONTRACT_VERSION = 3`. All v2 artifacts become invalid by design. |
| CICIDS source | Removed (loader, `DatasetSource` value, script options, docs, tests). |
| `ml_only` floor | Heuristic HIGH or CRITICAL always redirects to the decoy, in every mode. |
| Promotion yardstick | Analyst labels. Heuristic agreement stays visible but no longer gates. |
| Split | Group rows by a hash of their feature vector; a group goes wholly to train or wholly to test. |
| Review defaults | precision ≥ 0.90, recall ≥ 0.60, F1 ≥ 0.70, false-positive rate ≤ 0.02, training rows ≥ 100, test rows ≥ 30. |
| Artifact retention | Keep the newest 5 retraining artifacts; never delete the configured `MIRAGE_MODEL_ARTIFACT`. |
| pandas | Removed from the `ml` extra; PR #62 is closed instead of merged. |

## Components

### Feature contract v3 (`app/services/feature_extraction.py`)

- `FEATURE_NAMES` drops the six flow features; `FEATURE_CONTRACT_VERSION`
  becomes `3`. `extract_features` stops reading them.
- `InspectRequest` drops `flow_duration_ms`, `flow_packets_per_second`,
  `packet_length_mean`, `syn_flag_count`, `destination_port` and
  `average_packet_size`. Requests that still send them are accepted and the
  fields are ignored (verify the model does not forbid extra fields, and
  keep it that way).
- Loaders and scripts that set those fields (`csic_http.py`,
  `api_log_review.py`, `datasets.py`, `build_api_domain_fixture_dataset.py`,
  `smoke_ml_shadow.py`) stop setting them.

### CICIDS removal (`app/ml/datasets.py` and callers)

- Delete the CICIDS loader, `_first_present` if it has no other caller, the
  `cicids` value of `DatasetSource`, its script options, its tests and its
  sections in `docs/dataset-preparation.md` and READMEs.

### Signature floor (`app/services/decision_engine.py`)

- The first rule in `make_decision`, for every mode: risk level HIGH or
  CRITICAL returns `REDIRECT_TO_DECOY`. The `ml_only` and `hybrid` branches
  then apply only below that level.

### Analyst-label promotion gate (`app/services/ml_promotion.py`)

- `MLShadowScore` gains `heuristic_decision: Literal["allow", "monitor",
  "redirect_to_decoy"] | None = None` (stored with the event's shadow score;
  old rows read back as `None`). `inspection.py` fills it.
- New pure function `labeled_shadow_comparison(events) -> LabeledComparison`
  over events with both an analyst label and a shadow score. Ground truth:
  suspicious when the analyst label maps to 1 in `LABEL_TO_BINARY`. A
  decision is positive when it is `redirect_to_decoy`. It returns, for the
  model and for the heuristic, precision, recall and false-positive rate,
  plus the event count. The heuristic decision is
  `ml_shadow.heuristic_decision`, falling back to the event's final decision
  when absent.
- New gate `labeled_model_vs_heuristic`: passes when the labeled event count
  ≥ `ML_PROMOTION_MIN_LABELED_EVENTS` (new setting, default 100), model
  precision ≥ heuristic precision, and model recall ≥ heuristic recall. Its
  message states the four numbers.
- The `shadow_agreement_rate` gate becomes informational: still computed
  and shown, never blocking. `ML_PROMOTION_MIN_AGREEMENT_RATE` is removed
  (settings, compose, docs).

### Grouped split (`app/ml/datasets.py`)

- `stratified_split` assigns rows by group: the group key is the SHA-256 of
  the row's feature values in `FEATURE_NAMES` order. Groups are shuffled with
  the seeded RNG and assigned per label until the test share is met. A group
  that contains both labels is assigned by its majority label and counted in
  a new manifest field `conflicting_feature_groups`.
- The existing "at least 2 rows per class" rule now applies to groups
  (at least 2 groups per class).

### Review thresholds (`app/ml/artifacts.py`, `app/ml/dataset_review.py`)

- `review_model_artifact` defaults change to the values in Decisions. The
  script that exposes them shows the new defaults in `--help`.
- `retraining.py` passes the same defaults, so the dashboard's "shadow
  ready" uses the stricter bar.

### Single verified load (`app/ml/artifact_integrity.py`, `artifacts.py`, `inference.py`, `ml_shadow.py`)

- New `load_verified_artifact(path, expected_sha256) -> Any`: read the file
  bytes once, hash those bytes, compare, then `joblib.load(io.BytesIO(data))`.
  With no expected digest (development only) it loads the bytes it read.
  Every serving-path load uses it.
- `RiskClassifier.from_artifact(artifact: dict)` builds a classifier from an
  already loaded artifact. The shadow loader reviews once and builds the
  classifier from the same loaded object.

### Artifact retention (`app/services/retraining.py`)

- After a successful run, list `risk_model_*.joblib` in the retraining
  directory, sort by modification time, and delete all but the newest 5,
  skipping the path that resolves to `MIRAGE_MODEL_ARTIFACT`. Deletion
  errors are logged, never raised.

### Retrain with the current detector (operational, docs)

- Regenerate the prepared CSIC dataset from `data/csic-2010` under contract
  v3, train, review with the new thresholds, and record the dataset counts,
  metrics and review outcome in `docs/dataset-preparation.md`. Datasets and
  artifacts stay out of git (`data/` and `artifacts/` are ignored). If the
  artifact fails the stricter review, record that honestly: the gate is
  doing its job.

### pandas

- Remove `pandas` from the `ml` extra. Close Dependabot PR #62 with a
  comment that the dependency was removed.

## Error handling

- Loading an artifact whose contract version is not 3 yields the existing
  contract blocker (review) or `ValueError` (classifier); shadow scoring is
  then off.
- A mirage-jsonl row with v2 features is rejected by the strict contract
  check added in the audit (missing and unknown features are named).
- Retention never deletes the configured artifact and never fails a
  retraining run.

## Testing

Each change gets a test that fails before it.

- Contract: `FEATURE_NAMES` has no flow feature; version is 3;
  `extract_features` output keys equal `FEATURE_NAMES`.
- `InspectRequest` with flow fields in the payload is accepted and ignores
  them.
- Decision engine: in `ml_only` and `hybrid`, a HIGH heuristic risk with a
  shadow "allow" redirects; below HIGH, `ml_only` follows the shadow.
- Promotion: `labeled_shadow_comparison` on a hand-built set with known
  precision and recall; the gate passes when the model matches or beats the
  heuristic, fails when it is worse or when labeled events are too few;
  agreement below 0.8 no longer blocks.
- Split: identical rows never appear in both train and test; seeded and
  reproducible; conflicting groups counted.
- Review: an artifact with FPR 0.05 is blocked by default; one meeting all
  thresholds passes.
- Single load: patch `joblib.load` to count calls → one load per shadow
  loader run; the bytes loaded are the bytes hashed.
- Retention: seven artifacts → the five newest kept, and the configured
  artifact kept even when old.
- CICIDS: tests removed with the loader; a `cicids` source is rejected by
  the CLI.

## Success criteria

1. All tests pass; CI green.
2. No reference to flow features or CICIDS remains outside historical
   specs and plans.
3. A CSIC v3 artifact is trained and reviewed, and its metrics and review
   outcome are recorded in the docs.
4. pandas is gone and PR #62 is closed.

## Out of scope

- Per-analyst operator accounts (sub-project 5).
- Event and alert retention in the database.
- New model families or hyperparameter search.
