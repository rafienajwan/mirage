# Dataset Preparation Workflow

Project MIRAGE can train a local Random Forest risk model from validated JSON
Lines records. The proposal target includes CICIDS2017-style traffic data and
custom API logs, so raw data should be prepared before training rather than fed
directly into the trainer.

## Supported Sources

| Source | Adapter | Status |
| --- | --- | --- |
| Analyst-labeled MIRAGE export | `mirage-jsonl` | Ready |
| Custom API JSONL fixtures | `api-log-jsonl` | Flexible adapter for local experiments |
| Reviewed custom API JSONL logs | `reviewed-api-log-jsonl` | Requires a hash-bound sanitized source review |
| CICIDS2017-style CSV | `cicids-csv` | Basic adapter for one compatible CSV |
| CICIDS2017-style CSV directory | `cicids-csv-dir` | Loads all immediate `*.csv` files in stable filename order |
| HTTP CSIC 2010 directory | `csic-http-dir` | Parses the three official raw HTTP request files with provenance and deduplication |

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
training and inference keep the same feature order. Prepared manifests and
trained artifacts record `feature_contract_version`. A dataset or artifact from
an older contract must be regenerated instead of being mixed with runtime
features from the current contract.

Feature contract version 2 adds five bounded, runtime-compatible payload-shape
features: log-scaled payload length, Shannon entropy, non-alphanumeric ratio,
log-scaled percent-encoded token count, and log-scaled parameter count. The
extractor uses at most 4,096 characters from the combined query and request
body. The proxy, custom API-log adapter, and HTTP CSIC adapter all construct this
excerpt in the same query-then-body order.

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
| Payload excerpt | Explicit `payload_excerpt`, or query aliases combined with `body_excerpt`, `request_body`, `body`, or `payload` |

For production-like logs, create a source review before preparing a split. Use
generic origin text that does not contain credentials or customer identifiers.
The two boolean flags are explicit operator attestations, not automatic claims:

```bash
cd apps/gateway
python scripts/review_api_log_source.py \
  --input data/raw/api-logs/labeled_requests.jsonl \
  --output data/raw/api-logs/labeled_requests-review.json \
  --data-origin staging-api-gateway \
  --collection-started-at 2026-07-01T00:00:00Z \
  --collection-ended-at 2026-07-02T00:00:00Z \
  --labeling-method analyst-reviewed \
  --sanitized \
  --approved-for-training

python scripts/prepare_dataset.py \
  --source reviewed-api-log-jsonl \
  --input data/raw/api-logs/labeled_requests.jsonl \
  --source-review data/raw/api-logs/labeled_requests-review.json \
  --output-dir data/prepared/api-logs-v1 \
  --dataset-name api-logs \
  --dataset-version v1
```

The review records only provenance, input SHA-256, bounded quality statistics,
class counts, and blocker codes. It does not store request bodies, IP addresses,
user agents, or source record identifiers. Rows larger than 1 MiB, malformed
rows, invalid collection windows, conflicting labels for the same canonical
request, missing sanitization, or missing training approval block preparation.
Same-label duplicate requests are removed before splitting. Prepared record IDs
are one-way hashes, and a sanitized copy of the review is hash-bound into the
dataset manifest. Any change to the raw input or copied review invalidates the
workflow.

Use the flexible `api-log-jsonl` source only for local fixtures and adapter
experiments that do not claim reviewed production provenance.

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

For proposal-aligned staging collection, run the manual-review collector
against a running gateway. It sends 20 normal and 20 suspicious requests through
the real proxy path but does not attach or submit any labels:

```bash
cd apps/gateway
python scripts/collect_runtime_review_batch.py \
  --base-url http://localhost:8000 \
  --normal-count 20 \
  --suspicious-count 20 \
  --queue-output data/raw/runtime/manual-review-queue.json \
  --manifest-output data/raw/runtime/manual-review-manifest.json
```

The operator API key is read from `MIRAGE_API_KEY`. It is used only to read the
dashboard event queue and is never forwarded through the protected proxy. The
queue contains only event ID, timestamp, method, and path; it omits expected
labels, IP addresses, risk decisions, payloads, and credentials. Existing queue
or manifest files must be archived before another collection can start. Review
all queued event IDs in the operator dashboard. Once the labels have been
checked and the batch is approved for training, finalize it explicitly:

```bash
python scripts/finalize_runtime_review_batch.py \
  --approved-for-training \
  --output data/raw/runtime/manual-reviewed-events.jsonl \
  --summary-output data/raw/runtime/manual-reviewed-summary.json
```

The finalizer verifies the queue SHA-256, requires every queued ID to appear in
the analyst-labeled dashboard export, requires both binary classes, filters out
unrelated historical events, and emits only the feature vector plus manual
label fields. The summary records the collection window, class counts, queue
hash, and output dataset hash.

The older collector below assigns deterministic scenario labels automatically.
Use it only to validate API, labeling, and export plumbing, never as independent
human-reviewed model-quality evidence:

```bash
cd apps/gateway
python scripts/collect_api_domain_training_data.py \
  --base-url http://localhost:8000 \
  --api-key YOUR_LOCAL_MIRAGE_API_KEY \
  --normal-count 10 \
  --suspicious-count 10 \
  --output data/raw/runtime/api-domain-training-events.jsonl \
  --summary-output data/raw/runtime/api-domain-training-summary.json
```

The generated files should stay in ignored local `data/` paths unless they have
been reviewed and explicitly approved for publication. Both collector outputs
use `--source mirage-jsonl` because they already contain MIRAGE feature vectors.

When a running gateway is not available, use the deterministic API-domain
fixture generator to exercise the same custom API-log adapter path locally:

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

The fixture records are synthetic, balanced, and deterministic. They are useful
for adapter, split, training, and shadow-smoke checks, but they are not a
substitute for reviewed production-like API logs.

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

When the full CICIDS2017 CSV set is available in one ignored local directory,
prepare it as a single reviewed split with the directory adapter:

```bash
cd apps/gateway
python scripts/prepare_dataset.py \
  --source cicids-csv-dir \
  --input data \
  --output-dir data/prepared/cicids2017-full-v1 \
  --dataset-name cicids2017-full \
  --dataset-version v1
```

The directory adapter reads only immediate `*.csv` files, sorted by filename.
Each prepared row keeps a source record id in the form `filename.csv:line` so
reviewers can trace rows back to the raw CSV without committing raw data.

## Prepare HTTP CSIC 2010

HTTP CSIC 2010 supplements the network-flow CICIDS2017 data with labeled,
application-layer HTTP requests. Use the [official IMPACT catalog](https://www.impactcybertrust.org/dataset_view?idDataset=940)
for dataset context and the [ReData distribution DOI](https://doi.org/10.60895/redata/RWUUSV)
for the three files distributed under CC BY 4.0:

| File | Label | Bytes | Published MD5 |
| --- | --- | ---: | --- |
| `normalTrafficTraining.txt` | Normal | 20,640,988 | `80dc393c73afd08df28351e1470e3bbf` |
| `normalTrafficTest.txt` | Normal | 20,643,204 | `475d761acdb349a5d2e5404e9f3a4ebb` |
| `anomalousTrafficTest.txt` | Suspicious | 16,090,299 | `d03503ed45d198b4cebdefec1f540131` |

Place them in `apps/gateway/data/csic-2010/`. Verify the published MD5 values,
then create `data/csic-2010/sha256.json` with a JSON object that maps all three
filenames to their local SHA-256 values. The preparation command rejects a
partial checksum map or any mismatch.

```bash
cd apps/gateway
python scripts/prepare_dataset.py \
  --source csic-http-dir \
  --input data/csic-2010 \
  --output-dir data/prepared/csic-http-2010-v2 \
  --dataset-name csic-http-2010 \
  --dataset-version redata-rwuusv-v2 \
  --checksums data/csic-2010/sha256.json

python scripts/review_dataset.py \
  --manifest data/prepared/csic-http-2010-v2/manifest.json \
  --min-total-rows 10000 \
  --min-train-rows 7000 \
  --min-test-rows 2000 \
  --min-rows-per-class 1000
```

The verified local release contains 97,065 raw requests. MIRAGE removes 62,461
repeated request identities before splitting, leaving 34,604 rows: 18,640
normal and 15,964 suspicious. A request identity covers method, target, user
agent, and body, so the same canonical request identity cannot appear in both
train and test sets. The manifest records the official catalog,
distribution DOI, SHA-256 values, rejected rows, and removed duplicates.
Prepared manifests also record SHA-256 values for `train.jsonl` and
`test.jsonl` plus the current feature-contract version. Dataset review fails if
either split changes without regenerating the manifest, even when its row count
remains unchanged, or when the feature contract is outdated. Prepared
directories created before split hashes or feature-contract version 2 were
introduced must be regenerated before training a promotion-eligible artifact.

CSIC traffic was generated for a 2010 e-commerce application. It is useful for
reproducible parser, payload-signal, and model benchmarking, but it is not
modern production traffic and does not satisfy the proposal's pending need for
reviewed production-like custom API logs.

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

The command checks manifest integrity, train/test file hashes and row counts,
label presence in both splits, and the feature contract. It exits with code `1`
when blockers are found. Passing this review means the split is ready for local
training review, not that the resulting model should control live routing.
