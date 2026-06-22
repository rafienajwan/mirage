# Project MIRAGE Gateway

FastAPI backend for request inspection, hybrid defense experimentation, safe
decoy routing, event persistence, dashboard APIs, and ML data preparation.

## Quick Start

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

API documentation is available at `http://localhost:8000/docs`.

## Test

```bash
python -m pytest tests -v
```

## Proxy Route

Requests sent to `/api/v1/proxy/{path}` are inspected and forwarded to either
`REAL_APP_URL` or `DECOY_SERVICE_URL`. The proxy enforces a body-size limit,
filters hop-by-hop headers, and removes credentials before decoy forwarding.

## Security Configuration

- Set `MIRAGE_API_KEY` to protect inspection, simulation, and decoy-write endpoints.
- Send the key in `X-Mirage-API-Key`.
- Set `RATE_LIMIT_PER_MINUTE` to control per-client API traffic.
- Restrict `FRONTEND_ORIGIN` to the deployed dashboard origin.
- Keep operational credentials only in `.env`; the file is ignored by Git.
- Configure `DECOY_*` with synthetic values that are invalid on real systems.
- Update `.env.example` whenever a new environment variable is introduced.

## ML Pipeline

Every inspection produces a stable numeric feature vector. Labeled JSON Lines
records can be trained with:

```bash
python scripts/train_model.py \
  --input data/training_events.jsonl \
  --output artifacts/risk_model.joblib
```

Runtime routing still uses heuristic scoring until a trained artifact is
reviewed and enabled through a shadow-deployment phase.

## Current Limitations

- Proxying is limited to `/api/v1/proxy/*`; arbitrary ingress is not intercepted.
- The isolated decoy service is static rather than adaptive.
- Dashboard updates use HTTP polling rather than WebSocket.
- Honeytoken-use tracking and persistent actor profiles are not implemented.
- API-key protection is disabled when `MIRAGE_API_KEY` is unset.
