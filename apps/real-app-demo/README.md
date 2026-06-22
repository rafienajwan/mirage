# MIRAGE Protected Demo App

Small FastAPI upstream used to demonstrate traffic that the gateway allows or
monitors. It is sample data only and is not a production application.

```bash
cd apps/real-app-demo
python -m pip install -e .
uvicorn app.main:app --reload --port 8001
```

Health endpoint: `http://localhost:8001/health`.
