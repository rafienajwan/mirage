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
  --min-precision 0.5 \
  --min-recall 0.5 \
  --min-f1-score 0.5 \
  --max-false-positive-rate 0.5
```

The command exits with code `1` when holdout thresholds fail. This is separate
from the training script's internal validation and should be treated as the
operator-facing check for a prepared dataset split.

## Review The Artifact

Review the artifact payload before enabling it:

```bash
cd apps/gateway
python scripts/review_model_artifact.py \
  --artifact artifacts/risk_model.joblib \
  --min-precision 0.5 \
  --min-recall 0.5 \
  --min-f1-score 0.5 \
  --max-false-positive-rate 0.5
```

The command exits with code `1` when blockers are found. It checks that the
artifact can be loaded, the feature contract matches the gateway, required
metrics exist, dataset lineage is structurally valid when present, and the
selected metric thresholds are satisfied.

The default thresholds are intentionally modest for local prototypes. For a
real demonstration or deployment, raise them and review dataset provenance,
holdout behavior, label quality, and false-positive tradeoffs manually.

## Local CICIDS2017 DDoS Review

A local ignored CICIDS2017 DDoS split has been reviewed and used to train a
shadow-ready artifact. The raw CSV files, prepared split, and `.joblib` artifact
remain ignored local files and should not be committed.

Dataset review:

```bash
cd apps/gateway
python scripts/review_dataset.py \
  --manifest data/prepared/cicids2017-ddos-v1/manifest.json \
  --min-total-rows 20 \
  --min-train-rows 15 \
  --min-test-rows 5
```

Review result:

| Metric | Value |
| --- | ---: |
| Total rows | 225745 |
| Train rows | 169308 |
| Test rows | 56437 |
| Normal rows | 97718 |
| Suspicious rows | 128027 |
| Blockers | 0 |
| Warnings | 0 |

Training command:

```bash
python scripts/train_model.py \
  --input data/prepared/cicids2017-ddos-v1/train.jsonl \
  --output artifacts/cicids2017-ddos-risk-model.joblib \
  --manifest data/prepared/cicids2017-ddos-v1/manifest.json
```

Internal training-script validation:

| Metric | Value |
| --- | ---: |
| Precision | 0.9994169581875729 |
| Recall | 0.9997083940845657 |
| F1 score | 0.9995626548930587 |
| False-positive rate | 0.0007641087217552669 |
| Training rows | 126981 |
| Test rows | 42327 |

Holdout evaluation command:

```bash
python scripts/evaluate_model_artifact.py \
  --artifact artifacts/cicids2017-ddos-risk-model.joblib \
  --input data/prepared/cicids2017-ddos-v1/test.jsonl \
  --min-precision 0.9 \
  --min-recall 0.9 \
  --min-f1-score 0.9 \
  --max-false-positive-rate 0.05 \
  --min-rows 1000
```

Holdout evaluation:

| Metric | Value |
| --- | ---: |
| Evaluated rows | 56437 |
| Precision | 0.9993752342871424 |
| Recall | 0.9995313525166369 |
| F1 score | 0.9994532873053312 |
| False-positive rate | 0.0008186655751125665 |
| Blockers | 0 |

Artifact review command:

```bash
python scripts/review_model_artifact.py \
  --artifact artifacts/cicids2017-ddos-risk-model.joblib \
  --min-precision 0.9 \
  --min-recall 0.9 \
  --min-f1-score 0.9 \
  --max-false-positive-rate 0.05 \
  --min-training-rows 1000 \
  --min-test-rows 1000
```

The artifact review returned `shadow_ready: true` with no blockers or warnings.
This supports shadow-mode observation only. It does not justify switching live
routing from heuristics to model control.

## Local CICIDS2017 Full Directory Review

The local ignored full CICIDS2017 CSV directory has also been prepared with the
`cicids-csv-dir` adapter and used to train a broader shadow-ready artifact. The
raw CSV files, prepared split, and `.joblib` artifact remain ignored local files
and should not be committed.

Dataset preparation:

```bash
cd apps/gateway
python scripts/prepare_dataset.py \
  --source cicids-csv-dir \
  --input data \
  --output-dir data/prepared/cicids2017-full-v1 \
  --dataset-name cicids2017-full \
  --dataset-version v1
```

Dataset review:

```bash
python scripts/review_dataset.py \
  --manifest data/prepared/cicids2017-full-v1/manifest.json \
  --min-total-rows 1000 \
  --min-train-rows 1000 \
  --min-test-rows 1000 \
  --min-rows-per-class 1000
```

Review result:

| Metric | Value |
| --- | ---: |
| Total rows | 2830743 |
| Train rows | 2123057 |
| Test rows | 707686 |
| Normal rows | 2273097 |
| Suspicious rows | 557646 |
| Blockers | 0 |
| Warnings | 0 |

Training command:

```bash
python scripts/train_model.py \
  --input data/prepared/cicids2017-full-v1/train.jsonl \
  --output artifacts/cicids2017-full-risk-model.joblib \
  --manifest data/prepared/cicids2017-full-v1/manifest.json
```

Internal training-script validation:

| Metric | Value |
| --- | ---: |
| Precision | 0.9653379712324903 |
| Recall | 0.9820579768360447 |
| F1 score | 0.9736261964926587 |
| False-positive rate | 0.008650746352702684 |
| Training rows | 1592292 |
| Test rows | 530765 |

Holdout evaluation command:

```bash
python scripts/evaluate_model_artifact.py \
  --artifact artifacts/cicids2017-full-risk-model.joblib \
  --input data/prepared/cicids2017-full-v1/test.jsonl \
  --min-precision 0.9 \
  --min-recall 0.9 \
  --min-f1-score 0.9 \
  --max-false-positive-rate 0.05 \
  --min-rows 1000
```

Holdout evaluation:

| Metric | Value |
| --- | ---: |
| Evaluated rows | 707686 |
| Precision | 0.9661597923602099 |
| Recall | 0.9825983416061745 |
| F1 score | 0.9743097341356207 |
| False-positive rate | 0.008443110189802806 |
| Blockers | 0 |

Artifact review returned `shadow_ready: true` with no blockers or warnings at
the same 0.9 precision, recall, and F1 thresholds. Smoke testing confirmed the
artifact loads through the runtime shadow-scoring path. Like the DDoS-specific
artifact, this supports shadow-mode observation only; it still does not justify
model-controlled routing.

## Local HTTP CSIC 2010 Review

The ignored HTTP CSIC 2010 split was regenerated for feature contract version 2
with train/test SHA-256 values, trained with manifest-bound lineage, and
evaluated against its external holdout. Dataset review passed with 34,604 rows:
25,953 training rows and 8,651 holdout rows. The enriched candidate improves
substantially over the version 1 baseline, but it still does not pass the
conservative promotion-quality gates.

Training command:

```bash
python scripts/train_model.py \
  --input data/prepared/csic-http-2010-v2/train.jsonl \
  --output artifacts/csic-http-2010-risk-model-v2.joblib \
  --manifest data/prepared/csic-http-2010-v2/manifest.json
```

| Candidate and check | Precision | Recall | F1 | False-positive rate |
| --- | ---: | ---: | ---: | ---: |
| Version 1 holdout baseline, 8,651 rows | 0.639824 | 0.328489 | 0.434106 | 0.158369 |
| Version 2 internal validation, 6,489 rows | 0.836122 | 0.734469 | 0.782006 | 0.123319 |
| Version 2 prepared holdout, 8,651 rows | 0.818670 | 0.725132 | 0.769067 | 0.137554 |

The version 2 artifact still fails the required `0.9` precision, recall, and F1
gates and the maximum `0.05` false-positive-rate gate. Its default local
artifact review reports `shadow_ready` because all four metrics satisfy the
default review thresholds (`0.5` minimums and `0.5` maximum FPR). That status
only permits observation: a smoke
run still produced one false positive on the normal request, agreement was
`0.5`, and heuristic routing remained unchanged.

Feature contract version 2 increases the training split from 163 to 17,294
unique feature vectors. Label-conflicting vectors now cover 4,574 rows instead
of 24,737. Payload entropy, non-alphanumeric ratio, payload length,
percent-encoded count, and parameter count are the five most important model
inputs in this candidate. This confirms that generic payload shape reduces the
earlier structural information loss, but the remaining false-positive rate and
legacy CSIC domain gap still require reviewed production-like custom API logs.
Thresholds were not lowered and this artifact must not control live routing.

## Smoke-Test Shadow Scoring

Use the smoke script to verify a local artifact can be loaded by the gateway
scoring path, attached to inspected events, and summarized without writing to
the configured database:

```bash
cd apps/gateway
python scripts/smoke_ml_shadow.py \
  --artifact artifacts/cicids2017-ddos-risk-model.joblib \
  --memory-store \
  --monitor-threshold 0.35 \
  --redirect-threshold 0.65
```

The command exits with code `1` when the artifact is not `shadow_ready` or when
the smoke requests do not produce shadow-scored events.

Current local smoke result for the reviewed CICIDS2017 DDoS artifact:

| Signal | Value |
| --- | ---: |
| Artifact mode | `shadow_ready` |
| Shadow events | 2 |
| Agreements | 1 |
| Disagreements | 1 |
| Agreement rate | 0.5 |
| Average probability | 0.27 |

The disagreement is expected for this smoke run: the heuristic redirects the
high-risk `/.env` probe, while the CICIDS-trained model scores it as monitor.
That difference is useful operator evidence that the current artifact should
remain in shadow mode until runtime API-domain data is collected and reviewed.

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

### Local Full-Artifact Observation

A local ignored observation run was executed against a temporary gateway on
`127.0.0.1:8010` with the full CICIDS2017 artifact configured in shadow mode.
The gateway used a local SQLite observation database and simulated normal plus
suspicious dashboard traffic. The observation outputs remain under ignored
`data/observations/` files and should not be committed.

Observation command:

```bash
python scripts/observe_ml_shadow.py \
  --base-url http://127.0.0.1:8010 \
  --samples 10 \
  --interval-seconds 1 \
  --limit 200 \
  --output data/observations/ml-shadow-full-observation.jsonl \
  --summary-output data/observations/ml-shadow-full-observation-summary.json
```

Observation summary:

| Signal | Value |
| --- | ---: |
| Artifact mode samples | `shadow_ready`: 10 |
| Shadow-ready samples | 10 |
| Shadow event delta | 18 |
| Latest shadow events | 19 |
| Latest agreement rate | 0.526316 |
| Latest disagreement rate | 0.473684 |
| Latest disagreements | 9 |
| Max disagreement rate | 0.473684 |

The final snapshot showed 10 live `allow` decisions and 9 live
`redirect_to_decoy` decisions, while the model shadow decisions were 19
`allow`. This is useful negative evidence: the artifact loads and scores in
shadow mode, but CICIDS flow features alone do not match MIRAGE's simulated API
attack semantics closely enough to control routing. Keep the model shadow-only
until reviewed custom API-domain logs are collected and trained.

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
shadow-mode activation. It does not update `MIRAGE_MODEL_ARTIFACT`.

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
- `blocked` when configuration, artifact, or dataset review fails;
- `needs_observation` when runtime shadow evidence is insufficient;
- `eligible` when every configured gate passes.

Only sanitized file names are returned. The report never changes the active
artifact or heuristic routing policy. Agreement is a compatibility signal
against current heuristics, not proof of real-world model accuracy.

## Experimental Live Routing

The gateway contains experimental `hybrid` and `ml_only` decision paths, but
they are guarded by two independent settings. Selecting a mode through
`ML_ROUTING_MODE` is insufficient on its own; `ML_LIVE_ROUTING_APPROVED=true`
must also be set deliberately. The default remains `heuristic`.

Only consider that approval after the promotion report is `eligible`, the
artifact has representative API-domain holdout results, and the shadow
observation has an acceptable false-positive impact. Keep `ml_only` limited to
controlled experiments because it can override explainable heuristic signals.

## Safe Claims

It is safe to say that a reviewed artifact is running in shadow mode and that
guarded experimental live-routing code exists. It is not safe to claim
production ML routing until representative custom API logs, cloud deployment,
and end-to-end operational behavior have been independently validated.
