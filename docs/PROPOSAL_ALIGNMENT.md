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
| FastAPI defense gateway | Partial | `/api/v1/proxy/*` inspects and forwards traffic, but arbitrary application ingress is not intercepted. |
| Hybrid risk scoring | Partial | Heuristic risk scoring is active. A Random Forest training/inference path can run in reviewed shadow mode, but it does not control live routing. |
| Scikit-learn anomaly detection | Partial | Scikit-learn is configured and training/shadow inference plus artifact review are implemented; runtime anomaly detection remains heuristic. |
| Threat fingerprint matching | Partial | Stable request fingerprints and computed actor profiles exist; persistent actor records and clustering do not. |
| Automated real/decoy routing | Implemented for demo | The proxy routes to separate real-app and decoy services using the live decision engine. |
| Fake endpoints and fake data | Implemented for demo | The isolated decoy service exposes static, synthetic responses without real secrets. |
| Honeytoken detection | Partial | Configured decoy credential use is detected, stored, alerted, and shown on the dashboard; per-attacker issuance and rotation are pending. |
| PostgreSQL/Supabase storage | Partial | Async PostgreSQL and Alembic are supported for events, alerts, and honeytoken hits; Supabase deployment and persistent actor tables are pending. |
| Feature-vector storage | Implemented | Request and optional CICIDS-style flow features are stored with events. |
| CICIDS2017 dataset | Partial | A basic CICIDS-style CSV adapter and train/test split workflow exist; reviewed raw dataset ingestion, cleaning, and provenance are still pending. |
| Custom API logs | Partial | Runtime events, features, analyst-corrected labels, JSONL export, validation, and split tooling are available; reviewed datasets are still pending. |
| Precision/recall/F1/FPR evaluation | Implemented | The Random Forest trainer calculates all four metrics. |
| Real-time WebSocket dashboard | Not implemented | Dashboard uses 10-second HTTP polling. |
| Security dashboard and alerts | Implemented for demo | Live metrics, events, risk history, decoy status, and internal alerts are available. |
| Adaptive decoy generation | Not implemented | Decoy selection and payloads are static templates. |
| Docker Compose | Configuration implemented | Compose, health checks, and Dockerfiles exist; image build still needs verification with Docker Desktop running. |
| Vercel/Railway/Supabase deployment | Not implemented | No verified online deployment configuration is present. |

## Safe Claims

The current demo can accurately claim that MIRAGE:

- analyzes submitted metadata and requests on the guarded proxy route;
- combines heuristic risk scoring and anomaly signals;
- automatically decides allow, monitor, or redirect-to-decoy;
- forwards demo traffic to isolated real-app or static decoy services;
- stores events, alerts, and ML-ready feature vectors;
- can store model-only shadow scores beside events when a reviewed artifact is configured;
- can review trained artifacts for feature-contract and metric readiness before shadow mode;
- records and alerts on configured decoy credential reuse as honeytoken hits;
- groups recent activity into actor profiles from fingerprints, events, and honeytoken hits;
- supports analyst labels for correcting event classification outcomes;
- exports analyst-labeled feature vectors as JSON Lines for model training;
- prepares validated train/test splits from MIRAGE JSONL and CICIDS-style CSV sources;
- displays live backend data on a dashboard;
- can train and evaluate a Random Forest model from labeled feature records.

It should not yet claim arbitrary ingress interception, a production ML model,
adaptive decoys, persistent actor clustering, per-attacker honeytoken issuance,
WebSocket updates, or deployed Supabase/Railway/Vercel infrastructure.
