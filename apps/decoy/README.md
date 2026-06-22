# MIRAGE Static Decoy

Isolated FastAPI upstream for suspicious proxy traffic. It returns static,
synthetic responses and never receives browser cookies, authorization headers,
or the MIRAGE operator key from the gateway.

All `DECOY_*` values must be fake and invalid on real systems. This service does
not issue or track active honeytokens.

```bash
cd apps/decoy
python -m pip install -e .
uvicorn app.main:app --reload --port 8002
```

Health endpoint: `http://localhost:8002/health`.
