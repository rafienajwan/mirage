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
  --output artifacts/risk_model.joblib
```

The training script stores:

- the trained model;
- the stable feature contract;
- precision, recall, F1, false-positive rate, training rows, and test rows;
- an artifact version.

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
metrics exist, and the selected metric thresholds are satisfied.

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
  --output artifacts/cicids2017-ddos-risk-model.joblib
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
  --output artifacts/cicids2017-full-risk-model.joblib
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
  --output artifacts/api-domain-fixture-risk-model.joblib
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
```

The status endpoint returns sanitized artifact readiness and does not expose the
full filesystem path. The summary endpoint reports recent model-only agreement,
disagreements, average probability, average score, and live-versus-shadow
decision counts for operator review.

## Safe Claims

It is safe to say that a reviewed artifact is running in shadow mode. It is not
safe to say that the model controls live routing until the decision engine is
explicitly changed and validated for that purpose.
