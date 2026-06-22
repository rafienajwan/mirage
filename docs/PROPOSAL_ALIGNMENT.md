# Proposal Alignment

Source proposal: **Project MIRAGE: Adaptive AI-Driven Cyber Deception System
for Autonomous Threat Hunting**, WRECK-IT 7.0.

## Summary

The repository follows the proposal's component boundaries and core
detect-deceive-observe flow, but it does not yet fulfill the complete MVP
described in the proposal. It is currently a defensible local prototype with
the beginning of a real ML pipeline.

## Capability Matrix

| Proposal capability | Status | Repository reality |
| --- | --- | --- |
| FastAPI defense gateway | Partial | Accepts request metadata for inspection; it is not yet a transparent reverse proxy to a real application. |
| Hybrid risk scoring | Partial | Heuristic risk scoring is active. A Random Forest training/inference path exists but is not yet used for live decisions. |
| Scikit-learn anomaly detection | Partial | Scikit-learn is configured and training is implemented; runtime anomaly detection remains heuristic. |
| Threat fingerprint matching | Partial | Stable request fingerprints exist; persistent actor profiles and clustering do not. |
| Automated real/decoy routing | Partial | Decisions and safe fake responses exist; no isolated real-app and decoy services are being transparently routed. |
| Fake endpoints and fake data | Implemented for demo | Static safe templates are available through the decoy response API. |
| Honeytoken detection | Not implemented | Fake credential strings exist, but issuance, tracking, and use-triggered alerts do not. |
| PostgreSQL/Supabase storage | Partial | Async PostgreSQL and Alembic are supported; Supabase deployment and actor/honeytoken tables are pending. |
| Feature-vector storage | Implemented | Request and optional CICIDS-style flow features are stored with events. |
| CICIDS2017 dataset | Not integrated | Relevant fields are accepted, but dataset ingestion, cleaning, splitting, and provenance are pending. |
| Custom API logs | Partial | Runtime events and features are captured; analyst-corrected labels and export tooling are pending. |
| Precision/recall/F1/FPR evaluation | Implemented | The Random Forest trainer calculates all four metrics. |
| Real-time WebSocket dashboard | Not implemented | Dashboard uses 10-second HTTP polling. |
| Security dashboard and alerts | Implemented for demo | Live metrics, events, risk history, decoy status, and internal alerts are available. |
| Adaptive decoy generation | Not implemented | Decoy selection and payloads are static templates. |
| Docker Compose | Configuration implemented | Compose, health checks, and Dockerfiles exist; image build still needs verification with Docker Desktop running. |
| Vercel/Railway/Supabase deployment | Not implemented | No verified online deployment configuration is present. |

## Safe Claims

The current demo can accurately claim that MIRAGE:

- analyzes simulated API request metadata;
- combines heuristic risk scoring and anomaly signals;
- automatically decides allow, monitor, or redirect-to-decoy;
- produces safe fake decoy responses;
- stores events, alerts, and ML-ready feature vectors;
- displays live backend data on a dashboard;
- can train and evaluate a Random Forest model from labeled feature records.

It should not yet claim transparent traffic forwarding, a production ML model,
adaptive decoys, active honeytoken monitoring, WebSocket updates, or deployed
Supabase/Railway/Vercel infrastructure.
