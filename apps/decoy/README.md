# MIRAGE Static Decoy

Isolated FastAPI upstream for suspicious proxy traffic. It returns static,
synthetic responses and never receives browser cookies, authorization headers,
or the MIRAGE operator key from the gateway.

All `DECOY_*` values must be fake and invalid on real systems. This service can
issue deterministic per-actor canary tokens for decoy responses. Increase
`DECOY_CANARY_EPOCH` to rotate newly issued canary values; the service does not
track persistent assignments or revocations.

```bash
cd apps/decoy
python -m pip install -e .
uvicorn app.main:app --reload --port 8002
```

Health endpoint: `http://localhost:8002/health`.
