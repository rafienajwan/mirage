# Model Artifact Review and Shadow Mode

MIRAGE supports trained Random Forest artifacts, but runtime routing remains
heuristic until an artifact has been reviewed and promoted deliberately. The
safe next step is shadow mode: the model scores requests and stores model-only
decisions beside events without changing live routing.

## Train From A Prepared Split

Prepare and review a dataset first as described in
`docs/dataset-preparation.md`, then run:

```bash
cd apps/gateway
python scripts/review_dataset.py \
  --manifest data/prepared/runtime-v1/manifest.json
```

If the dataset review passes, train from the reviewed split:

```bash
python scripts/train_model.py \
  --input data/prepared/runtime-v1/train.jsonl \
  --output artifacts/risk_model.joblib \
  --manifest data/prepared/runtime-v1/manifest.json
```

The training script stores:

- the trained model;
- the stable feature contract;
- precision, recall, F1, false-positive rate, training rows, and test rows;
- an artifact version;
- sanitized dataset lineage containing dataset identity and SHA-256 values for
  the manifest and prepared train/test splits.

Omitting `--manifest` still creates a legacy local artifact for compatibility,
but the promotion-readiness gate rejects it because it cannot prove which
prepared dataset produced the model.

Likewise, regenerate older prepared manifests that do not contain train/test
file hashes before retraining a promotion-eligible artifact.

## Evaluate The Holdout Split

Evaluate the artifact against the prepared `test.jsonl` split before enabling
shadow mode:

```bash
python scripts/evaluate_model_artifact.py \
  --artifact artifacts/risk_model.joblib \
  --input data/prepared/runtime-v1/test.jsonl \
  --min-precision 0.9 \
  --min-recall 0.6 \
  --min-f1-score 0.7 \
  --max-false-positive-rate 0.02
```

The command exits with code `1` when holdout thresholds fail. This is separate
from the training script's internal validation and should be treated as the
operator-facing check for a prepared dataset split.

## Review The Artifact

Review the artifact payload before enabling it:

```bash
cd apps/gateway
python scripts/review_model_artifact.py \
  --artifact artifacts/risk_model.joblib
```

The command exits with code `1` when blockers are found. It checks that the
artifact can be loaded, the feature contract matches the gateway, required
metrics exist, dataset lineage is structurally valid when present, and the
selected metric thresholds are satisfied.

The default thresholds are strict because a false positive sends a real user
to the decoy: precision at least `0.90`, recall at least `0.60`, F1 at least
`0.70`, false-positive rate at most `0.02`, at least `100` training rows and
`30` test rows (`--help` shows them). A test split without negatives has no
false-positive rate and is blocked. Gateway shadow loading and dashboard
retraining use the same defaults. Still review dataset provenance, holdout
behavior, label quality, and false-positive tradeoffs manually.

## Local HTTP CSIC 2010 Review

The ignored HTTP CSIC 2010 split was regenerated under feature contract
version 3 with the grouped split and trained with manifest-bound lineage, so
its metrics come from the prepared holdout:

```bash
python scripts/train_model.py \
  --input data/prepared/csic-http-2010-v3/train.jsonl \
  --output artifacts/csic-http-2010-risk-model-v3.joblib \
  --manifest data/prepared/csic-http-2010-v3/manifest.json

python scripts/review_model_artifact.py \
  --artifact artifacts/csic-http-2010-risk-model-v3.joblib
```

On 8,686 holdout rows it reaches precision 0.750, recall 0.728, F1 0.739 and a
false-positive rate of 0.210. The default review blocks it (`Precision 0.750 is
below 0.900`, `False-positive rate 0.210 is above 0.020`), so it must not be
used for shadow or live routing. Dataset counts, `conflicting_feature_groups`
and the artifact SHA-256 are recorded in `docs/dataset-preparation.md`. The CSIC
domain gap still requires reviewed production-like custom API logs.

## Smoke-Test Shadow Scoring

Use the smoke script to verify a local artifact can be loaded by the gateway
scoring path, attached to inspected events, and summarized without writing to
the configured database:

```bash
cd apps/gateway
python scripts/smoke_ml_shadow.py \
  --artifact artifacts/csic-http-2010-risk-model-v3.joblib \
  --memory-store \
  --monitor-threshold 0.35 \
  --redirect-threshold 0.65
```

The command exits with code `1` when the artifact is not `shadow_ready` or when
the smoke requests do not produce shadow-scored events.

## Observe Shadow Trends

After the gateway is running with `MIRAGE_MODEL_ARTIFACT` configured, collect
periodic status and summary snapshots while local traffic is being replayed or
tested:

```bash
cd apps/gateway
python scripts/observe_ml_shadow.py \
  --base-url http://localhost:8000 \
  --samples 20 \
  --interval-seconds 30 \
  --limit 500 \
  --output .tmp/ml-shadow-observation.jsonl \
  --summary-output .tmp/ml-shadow-observation-summary.json
```

The script reads `MIRAGE_API_KEY` automatically when the dashboard API is
protected. Pass `--api-key` only when an explicit override is needed. The key is
sent in the `X-Mirage-API-Key` header and is never written to observation files.

The JSONL output is append-only and intended for local review. Keep it ignored
unless it has been sanitized and intentionally promoted to documentation. The
summary output reports sample count, artifact modes observed, shadow-ready
sample count, latest agreement/disagreement rates, disagreement count, and the
change in shadow-scored events across the observation window.

Use this as operational evidence only. A high agreement rate on local traffic is
not enough to let the model control routing; it should still be reviewed against
representative API-domain data and false-positive expectations.

## Local API-Domain Fixture Review

A deterministic local API-domain fixture can exercise the custom API-log adapter
and artifact review path without a running gateway. The generated raw JSONL,
prepared split, and `.joblib` artifact remain ignored local files and should not
be committed.

Fixture generation and preparation:

```bash
cd apps/gateway
python scripts/build_api_domain_fixture_dataset.py \
  --normal-count 20 \
  --suspicious-count 20 \
  --output data/raw/runtime/api-domain-fixture-events.jsonl
python scripts/prepare_dataset.py \
  --source api-log-jsonl \
  --input data/raw/runtime/api-domain-fixture-events.jsonl \
  --output-dir data/prepared/api-domain-fixture-v1 \
  --dataset-name api-domain-fixture \
  --dataset-version v1
```

Dataset review:

```bash
python scripts/review_dataset.py \
  --manifest data/prepared/api-domain-fixture-v1/manifest.json \
  --min-total-rows 40 \
  --min-train-rows 30 \
  --min-test-rows 10 \
  --min-rows-per-class 10
```

Review result:

| Metric | Value |
| --- | ---: |
| Total rows | 40 |
| Train rows | 30 |
| Test rows | 10 |
| Normal rows | 20 |
| Suspicious rows | 20 |
| Blockers | 0 |
| Warnings | 1 |

Training command:

```bash
python scripts/train_model.py \
  --input data/prepared/api-domain-fixture-v1/train.jsonl \
  --output artifacts/api-domain-fixture-risk-model.joblib \
  --manifest data/prepared/api-domain-fixture-v1/manifest.json
```

Internal training-script validation:

| Metric | Value |
| --- | ---: |
| Precision | 1.0 |
| Recall | 1.0 |
| F1 score | 1.0 |
| False-positive rate | 0.0 |
| Training rows | 22 |
| Test rows | 8 |

Holdout evaluation command:

```bash
python scripts/evaluate_model_artifact.py \
  --artifact artifacts/api-domain-fixture-risk-model.joblib \
  --input data/prepared/api-domain-fixture-v1/test.jsonl \
  --min-precision 0.8 \
  --min-recall 0.8 \
  --min-f1-score 0.8 \
  --max-false-positive-rate 0.25 \
  --min-rows 10
```

Holdout evaluation:

| Metric | Value |
| --- | ---: |
| Evaluated rows | 10 |
| Precision | 1.0 |
| Recall | 1.0 |
| F1 score | 1.0 |
| False-positive rate | 0.0 |
| Blockers | 0 |

Artifact review returned `shadow_ready: true` with the expected small-dataset
warning. Smoke testing confirmed the artifact loads through the runtime
shadow-scoring path and agreed with the heuristic on one normal and one
suspicious smoke request.

This is a pipeline validation artifact only. Because the fixture is
deterministic and small, it should not be used to claim production ML quality or
model-controlled routing.

## Analyst-Reviewed Runtime Pilot

The first independently labeled runtime batch was finalized locally with 40
events: 20 normal and 20 suspicious. Every row contains the version 2 feature
contract, and the finalized JSONL SHA-256 matches its hash-bound summary. Raw,
prepared, observation, and artifact files remain under ignored local paths.

Preparation produced a deterministic 30-row training split and a separate
10-row holdout, each balanced by class. Dataset review passed with no blockers
and the expected small-dataset warning.

```bash
cd apps/gateway
python scripts/prepare_dataset.py \
  --source mirage-jsonl \
  --input data/raw/runtime/manual-reviewed-events.jsonl \
  --output-dir data/prepared/runtime-manual-v1 \
  --dataset-name runtime-manual-review \
  --dataset-version v1 \
  --train-ratio 0.75 \
  --seed 42
python scripts/review_dataset.py \
  --manifest data/prepared/runtime-manual-v1/manifest.json \
  --min-total-rows 40 \
  --min-train-rows 30 \
  --min-test-rows 10 \
  --min-rows-per-class 10
```

The candidate artifact was trained with manifest-bound split lineage. Its
internal 22/8 validation and external 10-row holdout both reported precision,
recall, and F1 of `1.0` with a false-positive rate of `0.0`. Those metrics are
not production-quality evidence: the holdout contains only five rows per class
and comes from the same small collection procedure.

Artifact review returned `shadow_ready: true` with the small-dataset warning.
Runtime checks were less optimistic:

| Signal | Smoke run | Varied local observation |
| --- | ---: | ---: |
| Shadow events | 2 | 42 |
| Agreements | 1 | 27 |
| Disagreements | 1 | 15 |
| Agreement rate | 0.5 | 0.642857 |
| Live allow decisions | 1 | 15 |
| Live monitor decisions | 0 | 10 |
| Live redirects | 1 | 17 |
| Shadow allow decisions | 1 | 0 |
| Shadow monitor decisions | 1 | 25 |
| Shadow redirects | 0 | 17 |

The smoke attack received suspicious probability `0.61`, below the `0.65`
redirect threshold, so the model monitored a request that the heuristic
redirected. In the varied observation, all 15 normal requests were raised from
live `allow` to shadow `monitor` at or above the `0.35` monitor threshold. This
negative evidence outweighs the perfect tiny holdout metrics. Keep this
artifact local and shadow-only; do not enable `hybrid` or `ml_only` routing.

The next dataset must add independently reviewed normal and borderline traffic,
reach the configured 1,000-row promotion minimum, and accumulate at least 500
shadow events before another promotion review.

## Retrain From Analyst Labels

After enough dashboard events have analyst labels and feature vectors, the
gateway can train a local candidate artifact:

```bash
curl -X POST \
  -H "X-Mirage-API-Key: YOUR_LOCAL_MIRAGE_API_KEY" \
  http://localhost:8000/api/v1/dashboard/training-data/retrain
```

The endpoint stores the artifact in `MIRAGE_RETRAINING_ARTIFACT_DIR`, returns
the training metrics, and includes the same artifact review result used before
shadow-mode activation. It does not update `MIRAGE_MODEL_ARTIFACT`. Its
internal holdout keeps identical feature vectors on one side; when a class has
fewer than two distinct feature vectors the endpoint returns `409`.

After each successful run only the five newest `risk_model_*.joblib` files in
that directory are kept. The file configured as `MIRAGE_MODEL_ARTIFACT` is never
deleted, even when it is older. Files that cannot be deleted are logged and
left in place.

## Enable Shadow Mode

Only after review, point the gateway to the artifact:

```env
MIRAGE_MODEL_ARTIFACT=artifacts/risk_model.joblib
ML_SHADOW_MONITOR_THRESHOLD=0.35
ML_SHADOW_REDIRECT_THRESHOLD=0.65
```

Restart the gateway. New events should include `ml_shadow` data with the model
probability, model-only decision, and whether it agrees with the heuristic live
decision.

The dashboard also reads:

```text
GET /api/v1/dashboard/ml-shadow/status
GET /api/v1/dashboard/ml-shadow/summary
GET /api/v1/dashboard/ml-promotion/readiness
```

The status endpoint returns sanitized artifact readiness and does not expose the
full filesystem path. The summary endpoint reports recent model-only agreement,
disagreements, average probability, average score, and live-versus-shadow
decision counts for operator review.

The promotion endpoint requires `X-Mirage-API-Key` and also needs a prepared
manifest configured through `MIRAGE_MODEL_DATASET_MANIFEST`. It reports:

- `unavailable` when required paths are not configured;
- `blocked` when configuration, artifact, or dataset review fails, or when, on
  at least `ML_PROMOTION_MIN_LABELED_EVENTS` (default 100) analyst-labeled
  shadow events covering both classes, the model caught no suspicious event or
  its precision or recall is below the heuristic's;
- `needs_observation` when runtime shadow evidence is insufficient: too few
  shadow events, too few labeled events, or labels missing a class;
- `eligible` when every configured gate passes.

The labeled comparison only passes when the labels include at least one
suspicious and one normal event and the model caught at least one suspicious
event. A rate with nothing to divide by (for example precision for a model that
never redirects) is undefined and never counts as matching the heuristic.
It uses the newest 10,000 analyst-labeled events and counts only those
shadow-scored by the configured artifact (matched by file name), so labels on
events scored by an earlier artifact do not vouch for the current one.

Only sanitized file names are returned. The report never changes the active
artifact or heuristic routing policy. Agreement with the heuristic is shown for
information only and never blocks promotion: a model that copies the heuristic
adds nothing, and one that catches what the heuristic misses must disagree.
Analyst labels are the yardstick.

## Experimental Live Routing

The gateway contains experimental `hybrid` and `ml_only` decision paths, but
they are guarded by two independent settings. Selecting a mode through
`ML_ROUTING_MODE` is insufficient on its own; `ML_LIVE_ROUTING_APPROVED=true`
must also be set deliberately. The default remains `heuristic`.

Only consider that approval after the promotion report is `eligible`, the
artifact has representative API-domain holdout results, and the shadow
observation has an acceptable false-positive impact. Keep `ml_only` limited to
controlled experiments because it can override explainable heuristic signals
below HIGH. In every mode, a HIGH or CRITICAL heuristic risk (an attack
signature) still redirects to the decoy, whatever the model decides.

## Safe Claims

It is safe to say that a reviewed artifact is running in shadow mode and that
guarded experimental live-routing code exists. It is not safe to claim
production ML routing until representative custom API logs, cloud deployment,
and end-to-end operational behavior have been independently validated.
