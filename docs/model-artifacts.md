# Model Artifact Review and Shadow Mode

MIRAGE supports trained Random Forest artifacts, but runtime routing remains
heuristic until an artifact has been reviewed and promoted deliberately. The
safe next step is shadow mode: the model scores requests and stores model-only
decisions beside events without changing live routing.

## Train From A Prepared Split

Prepare a dataset first as described in `docs/dataset-preparation.md`, then run:

```bash
cd apps/gateway
python scripts/train_model.py \
  --input data/prepared/runtime-v1/train.jsonl \
  --output artifacts/risk_model.joblib
```

The training script stores:

- the trained model;
- the stable feature contract;
- precision, recall, F1, false-positive rate, training rows, and test rows;
- an artifact version.

## Review The Artifact

Review the artifact before enabling it:

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
```

This endpoint returns a sanitized status object for operator visibility. It does
not expose the full filesystem path of the configured artifact.

## Safe Claims

It is safe to say that a reviewed artifact is running in shadow mode. It is not
safe to say that the model controls live routing until the decision engine is
explicitly changed and validated for that purpose.
