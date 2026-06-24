# Dataset Preparation Workflow

Project MIRAGE can train a local Random Forest risk model from validated JSON
Lines records. The proposal target includes CICIDS2017-style traffic data and
custom API logs, so raw data should be prepared before training rather than fed
directly into the trainer.

## Supported Sources

| Source | Adapter | Status |
| --- | --- | --- |
| Analyst-labeled MIRAGE export | `mirage-jsonl` | Ready |
| CICIDS2017-style CSV | `cicids-csv` | Basic adapter for compatible columns |

Raw and prepared datasets should stay under local ignored `data/` directories.
Commit the preparation code, schema, and documentation, but do not commit raw
datasets, generated splits, manifests, or model artifacts unless a dataset has
been explicitly approved for publication.

## Expected Training Row

Prepared JSONL records use the model's stable feature schema:

```json
{"label": 0, "features": {"request_count_log": 0.0, "path_length": 0.0}}
```

Labels are binary:

- `0`: normal or false positive;
- `1`: suspicious or false negative.

Missing known features are filled with `0.0`. Unknown features are ignored so
training and inference keep the same feature order.

## Prepare MIRAGE Runtime Export

Export analyst-labeled events from a running gateway:

```bash
curl -H "X-Mirage-API-Key: YOUR_LOCAL_MIRAGE_API_KEY" \
  http://localhost:8000/api/v1/dashboard/training-data/export \
  -o data/raw/runtime/training_events.jsonl
```

Prepare a deterministic train/test split:

```bash
cd apps/gateway
python scripts/prepare_dataset.py \
  --source mirage-jsonl \
  --input data/raw/runtime/training_events.jsonl \
  --output-dir data/prepared/runtime-v1 \
  --dataset-name runtime-export \
  --dataset-version v1
```

Then train from the prepared split:

```bash
python scripts/train_model.py \
  --input data/prepared/runtime-v1/train.jsonl \
  --output artifacts/risk_model.joblib
```

Review `data/prepared/runtime-v1/manifest.json` before enabling the artifact in
shadow mode. It records row counts, label balance, split ratio, seed, feature
names, and generated files.

## Prepare CICIDS-Style CSV

Place the raw CSV in an ignored local dataset path and run:

```bash
cd apps/gateway
python scripts/prepare_dataset.py \
  --source cicids-csv \
  --input data/raw/cicids2017/sample.csv \
  --output-dir data/prepared/cicids2017-v1 \
  --dataset-name cicids2017 \
  --dataset-version v1
```

The current adapter maps common CICIDS columns such as `Flow Duration`,
`Flow Packets/s`, `Packet Length Mean`, `SYN Flag Count`,
`Destination Port`, and `Average Packet Size`. Columns without a MIRAGE
equivalent are intentionally not used yet.

## Readiness Rules

Preparation fails unless:

- at least 20 rows are present;
- both binary classes are present;
- each class has at least two rows, matching the trainer's stratified split.

These rules match the dashboard training readiness indicator and prevent a
dataset from being marked ready when the trainer would fail immediately.
