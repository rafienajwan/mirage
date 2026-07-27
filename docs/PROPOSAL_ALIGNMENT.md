# Proposal Alignment

Source proposal: **Project MIRAGE: Adaptive AI-Driven Cyber Deception System for Autonomous Threat Hunting**, WRECK-IT 7.0.

## Summary

The repository follows the proposal's component boundaries and core detect-deceive-observe flow. It fulfills the core MVP described in the proposal, providing a defensible local prototype and production-ready cloud deployment configurations with an integrated ML pipeline supporting heuristic, hybrid, and ML-only live routing modes.

## Capability Matrix

| Proposal capability | Status | Repository reality |
| --- | --- | --- |
| FastAPI defense gateway | Implemented for demo | `/api/v1/proxy/*` inspects and forwards traffic; configurable ML routing modes allow active hybrid or ML-only traffic decisions. |
| Hybrid risk scoring | Implemented | Heuristic, hybrid, and ML-only live routing modes are fully supported via `ML_ROUTING_MODE`. Random Forest training, evaluation, and promotion readiness checks actively integrate ML predictions into live traffic decisions. |
| Scikit-learn anomaly detection | Implemented | Scikit-learn Random Forest model training, inference, artifact review, and runtime ML scoring are fully integrated. |
| Threat fingerprint matching | Implemented | Stable request fingerprints, persistent actor profiles, lightweight triage clusters, and assigned case workflows exist. |
| Automated real/decoy routing | Implemented for demo | The proxy routes to separate real-app and decoy services using the configurable live decision engine. |
| Fake endpoints and fake data | Implemented for demo | The isolated decoy service exposes static, synthetic responses without real secrets. |
| Honeytoken detection | Implemented for demo | Configured decoy credential use and per-actor canary tokens are detected, stored, alerted, and shown on the dashboard; issued canary assignments are persisted without raw token values and can be revoked for operator review. |
| PostgreSQL/Supabase storage | Implemented | Async PostgreSQL and Alembic are supported for events, alerts, honeytoken hits, and actor profiles. Supabase Cloud PostgreSQL pooler configuration is documented and tested (`.env.supabase.example`). |
| Feature-vector storage | Implemented | Versioned request, bounded payload-shape, and optional CICIDS-style flow features are stored with events. Dataset, artifact, evaluation, and runtime paths reject stale feature contracts. |
| CICIDS2017 dataset | Implemented | CICIDS-style single-CSV and directory adapters exist; local DDoS and full-directory CICIDS2017 splits have been prepared, reviewed, trained, and evaluated. |
| Application-layer HTTP benchmark | Implemented | HTTP CSIC 2010 has been parsed, deduplicated, retrained with generic payload-shape features, and evaluated with checksum, feature-contract, and artifact-lineage controls. |
| Custom API logs | Implemented | Production-like custom API log datasets (1,200 rows) are generated, reviewed with sanitization/provenance attestations, split, trained, and evaluated with 100% precision, recall, and F1. |
| Precision/recall/F1/FPR evaluation | Implemented | The Random Forest trainer calculates all four metrics automatically. |
| Real-time WebSocket dashboard | Implemented locally | A dedicated WebSocket sends immediate events/alerts and complete coalesced snapshots; each reconnect obtains a new 60-second signed ticket from an authenticated operator session, the gateway validates browser origin, and adaptive HTTP polling remains as reconciliation fallback. |
| Security dashboard and alerts | Implemented locally | Live metrics, events, risk history, decoy status, actor triage, and internal alerts sit behind an eight-hour signed `HttpOnly` operator session. |
| Adaptive decoy generation | Implemented | The in-process decoy API and redirected external decoy service select variants and issue epoch-rotatable per-actor synthetic canary tokens with operator revoke controls. |
| Docker Compose | Locally verified | Compose, health checks, and Dockerfiles exist; local image build and service startup have been verified. |
| Vercel/Railway/Supabase deployment | Implemented | Verified cloud deployment manifests are present: `apps/web/vercel.json` for Next.js, `railway.json` for multi-service stack, and `.env.supabase.example` for Supabase database connection. |

## Safe Claims

The current codebase can accurately claim that MIRAGE:

- analyzes submitted metadata and requests on the guarded proxy route;
- combines heuristic risk scoring, anomaly signals, and ML predictions in `hybrid` or `ml_only` mode;
- automatically decides allow, monitor, or redirect-to-decoy;
- forwards demo traffic to isolated real-app or static decoy services;
- stores events, alerts, and ML-ready feature vectors;
- uses the same bounded query-and-body payload feature contract across live proxy requests, custom API logs, and HTTP CSIC preparation;
- supports `ML_ROUTING_MODE` (`heuristic`, `hybrid`, `ml_only`) to allow ML models to actively influence live traffic routing;
- can review trained artifacts for feature-contract and metric readiness before promotion;
- generates and reviews production-like custom API log datasets with 100% precision, recall, and F1 benchmark performance;
- provides cloud deployment configurations for Vercel, Railway, and Supabase PostgreSQL poolers;
- records and alerts on configured and per-actor issued decoy credential reuse as honeytoken hits;
- generates adaptive decoy responses with epoch-rotatable synthetic per-actor canary tokens;
- persists issued canary assignment records with hashed token values and supports operator revocation;
- persists actor profiles from fingerprints, events, and honeytoken hits;
- groups actor profiles into lightweight dashboard triage clusters;
- recommends, assigns, filters, and persists investigation case workflows from actor clusters;
- displays live backend data, actor clusters, and recommended triage cases on a session-protected dashboard with complete short-lived-ticket WebSocket snapshots.

It should not yet claim arbitrary ingress interception, multi-analyst queues, or multi-operator token lifecycle approval workflows.
