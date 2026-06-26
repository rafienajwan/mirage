# MIRAGE Gateway

FastAPI service for request inspection, guarded proxy routing, persistence,
dashboard APIs, and offline ML preparation.

Use the root Docker workflow for a complete stack. Running this service alone
supports inspection and dashboard development, but proxy requests require the
protected demo app on port `8001` and decoy service on port `8002`.

## Standalone Setup

```bash
cd apps/gateway
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev,ml,postgres]"
# Windows: Copy-Item .env.example .env
# Linux/macOS: cp .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the generated API reference.

## Configuration

`apps/gateway/.env.example` is the standalone template. Important variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async SQLite or PostgreSQL connection |
| `MIRAGE_API_KEY` | Protects inspection, simulation, and decoy-write endpoints |
| `REAL_APP_URL` | Upstream for allowed or monitored requests |
| `DECOY_SERVICE_URL` | Upstream for redirected requests |
| `RISK_THRESHOLD` | Heuristic risk escalation threshold |
| `ANOMALY_REDIRECT_CONFIDENCE` | Anomaly-confidence escalation threshold |
| `RATE_LIMIT_PER_MINUTE` | Rolling per-client request limit |
| `PROXY_TIMEOUT_SECONDS` | Upstream timeout |
| `PROXY_MAX_BODY_BYTES` | Maximum forwarded request body |
| `MIRAGE_MODEL_ARTIFACT` | Optional trained artifact path for shadow scoring |
| `ML_SHADOW_*` | Model-only thresholds; live routing remains heuristic |
| `DECOY_*` | Synthetic values only; never real credentials |

Docker Compose requires `MIRAGE_API_KEY`; standalone development permits it to
be empty. Send protected requests with `X-Mirage-API-Key`.

## Proxy Example

```bash
curl -H "User-Agent: Mozilla/5.0" http://localhost:8000/api/v1/proxy/api/products
```

The gateway strips hop-by-hop headers for every upstream and removes credentials
before decoy forwarding. It returns a generic `502` when an upstream is
unavailable and rejects request bodies above the configured limit.

## Database Migrations

```bash
python -m alembic upgrade head
```

For a legacy database created before Alembic, back it up before stamping the
baseline revision. See `docs/CONTINUATION.md` in local development context for
the current migration note.

## Tests

```bash
python -m pytest tests -q
```

## Offline Model Training

```bash
python scripts/prepare_dataset.py \
  --source mirage-jsonl \
  --input data/raw/runtime/training_events.jsonl \
  --output-dir data/prepared/runtime-v1 \
  --dataset-name runtime-export \
  --dataset-version v1

python scripts/train_model.py \
  --input data/prepared/runtime-v1/train.jsonl \
  --output artifacts/risk_model.joblib

python scripts/review_model_artifact.py \
  --artifact artifacts/risk_model.joblib
```

Training computes precision, recall, F1, and false-positive rate. Runtime
routing remains heuristic until a reviewed artifact is enabled in shadow mode.
Set `MIRAGE_MODEL_ARTIFACT` to a trained artifact path to store model-only
scores beside events without changing live routing.

Analyst-labeled events can be exported from the running gateway as JSON Lines:

```bash
curl -H "X-Mirage-API-Key: YOUR_LOCAL_MIRAGE_API_KEY" \
  http://localhost:8000/api/v1/dashboard/training-data/export \
  -o data/training_events.jsonl
```

Check dataset readiness before training:

```bash
curl -H "X-Mirage-API-Key: YOUR_LOCAL_MIRAGE_API_KEY" \
  http://localhost:8000/api/v1/dashboard/training-data/summary
```

The readiness summary follows the same export filter: analyst-labeled events
must include a feature vector. A first local training run is considered ready
after at least 20 exportable rows exist and each binary class has at least two
rows for stratified splitting.

## Known Limitations

- proxy coverage is limited to `/api/v1/proxy/*`;
- no trained artifact participates in live decisions;
- actor profiles and per-attacker honeytoken issuance are not implemented;
- dashboard APIs are polled rather than streamed.
