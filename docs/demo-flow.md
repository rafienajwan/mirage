# Project MIRAGE - Current Demo Flow

1. Start the FastAPI gateway and Next.js dashboard.
2. Trigger normal or suspicious traffic from the dashboard simulation panel.
3. The gateway extracts a numeric feature vector and calculates heuristic risk.
4. The decision engine returns `allow`, `monitor`, or `redirect_to_decoy`.
5. The event, decision, alert, and feature vector are persisted.
6. The dashboard refreshes metrics, charts, alerts, and decoy status every 10 seconds.

The demo does not currently proxy requests to a real application or an isolated
decoy container. Decoy responses are safe in-process templates, and the ML
trainer is offline until a reviewed labeled dataset is available.
