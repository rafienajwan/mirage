# MIRAGE Demo Flow

## 1. Configure

From the repository root, copy `.env.example` to `.env` and fill every variable
marked `REQUIRED`. Decoy values must be synthetic and invalid on real systems.

## 2. Start

```bash
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

Wait for the gateway health check:

```bash
curl http://localhost:8000/health
```

## 3. Send Normal Traffic

```bash
curl -H "User-Agent: Mozilla/5.0" http://localhost:8000/api/v1/proxy/api/products
```

Expected result: product data from the protected demo application.

## 4. Send Suspicious Traffic

```bash
curl -H "User-Agent: sqlmap/1.8" http://localhost:8000/api/v1/proxy/.env
```

Expected result: synthetic configuration data from the static decoy service.

## 5. Observe

Open `http://localhost:3000/dashboard`. The event feed, risk metrics, alerts, and
decoy count refresh through HTTP polling. Event and alert updates can also use
the optional authenticated WebSocket stream when configured.

The dashboard simulation buttons call a server-side Next.js route that adds the
operator API key before contacting the gateway. The key remains outside the
browser bundle.

To call a simulation endpoint directly:

```bash
curl -X POST -H "X-Mirage-API-Key: YOUR_LOCAL_MIRAGE_API_KEY" http://localhost:8000/api/v1/simulate/suspicious
```

## 6. Stop

```bash
docker compose --env-file .env -f infra/docker-compose.yml down
```

## Demo Boundaries

- Proxy coverage is limited to `/api/v1/proxy/*`.
- Routing is heuristic rather than model-driven.
- Decoy payloads are synthetic and can issue deterministic per-actor canary
  tokens; token rotation and assignment lifecycle controls are still pending.
- Aggregate dashboard metrics are polled; event and alert updates can stream
  over WebSocket when configured.
