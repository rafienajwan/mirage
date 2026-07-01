# Dataset Preparation Workflow

Project MIRAGE can train a local Random Forest risk model from validated JSON
Lines records. The proposal target includes CICIDS2017-style traffic data and
custom API logs, so raw data should be prepared before training rather than fed
directly into the trainer.

## Supported Sources

| Source | Adapter | Status |
| --- | --- | --- |
| Analyst-labeled MIRAGE export | `mirage-jsonl` | Ready |
| Custom API JSONL logs | `api-log-jsonl` | Ready for labeled request metadata |
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

## Prepare Custom API Logs

Use this adapter when you have labeled request logs that have not already been
exported by MIRAGE. Each JSON Lines row can provide request fields at the top
level or inside a nested `request`, `httpRequest`, `http_request`, or `http`
object:

```json
{"id":"req-1","label":"normal","source_ip":"10.0.0.10","method":"GET","path":"/api/products","user_agent":"Mozilla/5.0","request_count":3}
{"id":"req-2","label":"suspicious","request":{"client_ip":"10.0.0.66","http_method":"POST","endpoint":"/.env","ua":"curl/8.0","payload_indicators":["path-traversal","sql-like"],"destination_port":443}}
{"request_id":"req-3","decision":"redirected","httpRequest":{"remote_addr":"203.0.113.10","request_method":"GET","url":"https://target.example/.env?debug=true","headers":{"User-Agent":"sqlmap/1.8"},"tags":["sql-like","encoded"],"query_string":"debug=true","destinationPort":443}}
```

Supported label fields are `label`, `analyst_label`, `class`, `decision`,
`outcome`, `verdict`, and `classification`. Supported normal labels include
`normal`, `benign`, `allow`, `allowed`, `clean`, `ok`, `pass`,
`false_positive`, and `0`. Supported suspicious labels include `suspicious`,
`malicious`, `attack`, `monitor`, `redirect_to_decoy`, `redirected`, `blocked`,
`denied`, `decoy`, `threat`, `false_negative`, `true_positive`, and `1`.

Common field aliases are accepted to reduce preprocessing:

| MIRAGE field | Accepted aliases |
| --- | --- |
| Source IP | `ip_address`, `source_ip`, `client_ip`, `src_ip`, `remote_addr`, `remoteAddress`, `clientIp` |
| Method | `method`, `http_method`, `httpMethod`, `request_method` |
| Path | `path`, `endpoint`, `url_path`, `route`, `uri`, `url`, `request_uri` |
| User agent | `user_agent`, `userAgent`, `ua`, `user-agent`, or `headers.User-Agent` |
| Request count | `request_count`, `source_request_count`, `count`, `hits` |
| Payload indicators | `payload_indicators`, `indicators`, `signals`, `tags` |
| Payload excerpt | `payload_excerpt`, `body_excerpt`, `request_body`, `body`, `payload`, `query`, `query_string` |

Prepare a split with the same production feature extractor used by the gateway:

```bash
cd apps/gateway
python scripts/prepare_dataset.py \
  --source api-log-jsonl \
  --input data/raw/api-logs/labeled_requests.jsonl \
  --output-dir data/prepared/api-logs-v1 \
  --dataset-name api-logs \
  --dataset-version v1
```

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
python scripts/review_dataset.py \
  --manifest data/prepared/runtime-v1/manifest.json
```

Only continue when the dataset review reports `ready_for_training: true`.

```bash
python scripts/train_model.py \
  --input data/prepared/runtime-v1/train.jsonl \
  --output artifacts/risk_model.joblib
```

Review `data/prepared/runtime-v1/manifest.json` before training or enabling an
artifact in shadow mode. It records row counts, label balance, split ratio,
seed, feature names, and generated files.

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

## Dataset Review Gate

Run the review gate after preparing a split:

```bash
cd apps/gateway
python scripts/review_dataset.py \
  --manifest data/prepared/runtime-v1/manifest.json \
  --min-total-rows 20 \
  --min-train-rows 15 \
  --min-test-rows 5
```

The command checks manifest integrity, train/test file row counts, label
presence in both splits, and the feature contract. It exits with code `1` when
blockers are found. Passing this review means the split is ready for local
training review, not that the resulting model should control live routing.
