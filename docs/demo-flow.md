# Project MIRAGE - Current Demo Flow

1. Start the real-app, decoy, FastAPI gateway, and Next.js dashboard services.
2. Send normal or suspicious traffic through `/api/v1/proxy/{path}`.
3. The gateway extracts a numeric feature vector and calculates heuristic risk.
4. The decision engine returns `allow`, `monitor`, or `redirect_to_decoy`.
5. Traffic is forwarded to the isolated real-app or static decoy service.
6. The event, decision, alert, and feature vector are persisted.
7. The dashboard refreshes metrics, charts, alerts, and decoy status every 10 seconds.

The proxy only covers its explicit route prefix, the decoy is not adaptive, and
the ML trainer remains offline until a reviewed labeled dataset is available.
