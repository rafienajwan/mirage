# Project MIRAGE Gateway

FastAPI backend for request inspection, hybrid defense experimentation, safe
decoy responses, event persistence, dashboard APIs, and ML data preparation.

## Quick Start

```bash
cd apps/gateway
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev,ml,postgres]"
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API documentation is available at `http://localhost:8000/docs`.

## Test

```bash
python -m pytest tests -v
```

## Security Configuration

- Set `MIRAGE_API_KEY` to protect inspection, simulation, and decoy-write endpoints.
- Send the key in `X-Mirage-API-Key`.
- Set `RATE_LIMIT_PER_MINUTE` to control per-client API traffic.
- Restrict `FRONTEND_ORIGIN` to the deployed dashboard origin.

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

- `/inspect` accepts metadata; it is not yet a transparent reverse proxy.
- Decoy responses are static templates rather than isolated adaptive services.
- Dashboard updates use HTTP polling rather than WebSocket.
- Honeytoken-use tracking and persistent actor profiles are not implemented.
- API-key protection is disabled when `MIRAGE_API_KEY` is unset.
