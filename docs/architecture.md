# MIRAGE Architecture

## Implemented MVP

```mermaid
graph LR
    A[Browser or API Client] --> B[FastAPI Gateway]
    B --> C[Feature Extraction]
    C --> D[Heuristic Risk and Anomaly Engines]
    D --> E{Decision Engine}
    E -->|Allow or monitor| F[Protected Demo App]
    E -->|Redirect| G[Static Decoy Service]
    D --> H[(Events and Alerts)]
    H --> I[API-Key-Protected Dashboard API]
    I --> J[Session-Protected Next.js Dashboard]
    H --> K[Origin and Ticket-Protected WebSocket]
    K --> J
    C --> L[ML-ready Feature Vectors]
    L --> M[Offline Random Forest Trainer]
```

The gateway only proxies requests received under `/api/v1/proxy/*`. Inspection,
simulation, dashboard, and decoy-management routes remain separate APIs.

## Request Path

1. The gateway reads a bounded request body and extracts path, query, user-agent,
   request-frequency, and payload indicators.
2. Heuristic risk and anomaly engines produce a decision: `allow`, `monitor`, or
   `redirect_to_decoy`.
3. Allowed and monitored requests go to the protected demo app. Redirected
   requests go to the isolated static decoy.
4. For decoy responses, the gateway records issued canary assignments with
   hashed token values for later operator review and revoke tracking.
5. The gateway persists the event, optional alert, and numeric feature vector.
6. The gateway sends immediate events/alerts and coalesced complete snapshots.
   The dashboard reconciles over HTTP every 60 seconds while connected and
   every 10 seconds while disconnected.

## Trust Boundaries

- Upstream URLs come only from server configuration; clients cannot choose a host.
- Hop-by-hop headers are never forwarded.
- Decoy forwarding uses an allowlist and removes cookies, authorization values,
  and `X-Mirage-API-Key`.
- Every dashboard API endpoint requires `X-Mirage-API-Key` in Docker
  deployments. Browser calls pass through session-protected Next.js bridges, so
  the key never enters the browser bundle.
- The dashboard uses an eight-hour signed `HttpOnly`, `SameSite=Strict` session.
- Each WebSocket connection receives a new 60-second HMAC ticket. The gateway
  validates its signature, audience, lifetime, and configured browser origin;
  it never accepts `MIRAGE_API_KEY` as a stream credential.
- Request body size, upstream timeout, rate limit, and tracked-source count are bounded.

## Persistence

Standalone development defaults to SQLite. Docker Compose uses PostgreSQL and
runs Alembic migrations before starting the gateway. Events include the extracted
feature vector used by the offline training workflow.

## Target Architecture

```mermaid
graph LR
    A[Application Ingress] --> B[Transparent Defense Gateway]
    B --> C[Heuristic and Validated ML Analysis]
    C --> D{Traffic Decision}
    D -->|Normal| E[Real Application]
    D -->|Suspicious| F[Adaptive Decoy]
    F --> G[Tracked Honeytokens and Interaction Capture]
    E --> H[(Threat Intelligence Store)]
    G --> H
    H --> I[Authenticated Streaming Dashboard]
    H --> J[Incident Response Integrations]
```

This target is not implemented yet. See `docs/PROPOSAL_ALIGNMENT.md` for the
capability-by-capability gap.
