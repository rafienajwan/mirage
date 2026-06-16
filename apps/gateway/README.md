# Project MIRAGE — Gateway

FastAPI backend for the MIRAGE AI-powered cyber deception defense platform.

## Purpose

The gateway receives simulated API request metadata, calculates risk scores, detects anomalies, decides whether traffic is normal or suspicious, routes suspicious traffic to safe decoy responses, logs activity, and exposes dashboard-ready API endpoints.

**No real offensive functionality is implemented.** All data is simulated and safe.

## Folder Structure

```txt
apps/gateway/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── core/
│   │   ├── config.py         # Environment configuration
│   │   └── cors.py           # CORS middleware
│   ├── api/
│   │   ├── router.py         # Route registration
│   │   └── routes/
│   │       ├── health.py     # GET /health
│   │       ├── inspect.py    # POST /api/v1/inspect
│   │       ├── dashboard.py  # GET /api/v1/dashboard/*
│   │       ├── decoy.py      # GET/POST /api/v1/decoy/*
│   │       └── simulate.py   # POST /api/v1/simulate/*
│   ├── schemas/              # Pydantic models
│   ├── services/             # Business logic engines
│   │   ├── risk_engine.py    # Risk scoring (0–100)
│   │   ├── anomaly_engine.py # Heuristic anomaly detection
│   │   ├── fingerprint.py    # Privacy-safe hashing
│   │   ├── decision_engine.py# Allow/monitor/redirect logic
│   │   ├── decoy_engine.py   # Safe fake response generator
│   │   ├── logger.py         # Activity logging + alerts
│   │   └── threat_analysis.py# Summary statistics
│   ├── storage/
│   │   └── memory_store.py   # In-memory event store
│   └── utils/
│       └── time.py           # Time utilities
├── tests/                    # pytest tests
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

| Method | Path                          | Description                          |
|--------|-------------------------------|--------------------------------------|
| GET    | `/health`                     | Service health check                 |
| POST   | `/api/v1/inspect`             | Inspect request and get decision     |
| GET    | `/api/v1/dashboard/overview`  | Aggregate dashboard stats            |
| GET    | `/api/v1/dashboard/events`    | Recent activity events               |
| GET    | `/api/v1/dashboard/alerts`    | Security alerts                      |
| GET    | `/api/v1/dashboard/threat-analysis` | Threat analysis summary        |
| GET    | `/api/v1/decoy/status`        | Decoy environment status             |
| POST   | `/api/v1/decoy/respond`       | Generate safe fake decoy response    |
| POST   | `/api/v1/simulate/normal`     | Generate safe normal traffic event   |
| POST   | `/api/v1/simulate/suspicious` | Generate safe suspicious traffic     |

## Quick Start

```bash
cd apps/gateway
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

## Running Tests

```bash
cd apps/gateway
pytest tests/ -v
```

## Current Limitations

- **In-memory storage only** — events and alerts are lost on restart.
- **Heuristic detection only** — no real ML model yet.
- **Single-process** — not designed for production concurrency.
- **No authentication** — API is open for local development.

## Future Scope

- Real anomaly detection model (scikit-learn / PyTorch)
- PostgreSQL / Supabase persistent logging
- WebSocket live event streaming to frontend
- Authentication and rate limiting
- Production Docker deployment
