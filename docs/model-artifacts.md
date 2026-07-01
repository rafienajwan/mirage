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
