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
| Hybrid risk scoring | Partial | Heuristic risk scoring is active. Random Forest training/inference can run in reviewed shadow mode, and local CICIDS2017 DDoS plus full-directory artifacts have passed review, but they do not control live routing. |
| Scikit-learn anomaly detection | Partial | Scikit-learn is configured and training/shadow inference plus artifact review are implemented; runtime anomaly detection remains heuristic. |
| Threat fingerprint matching | Partial | Stable request fingerprints, persistent actor profiles, lightweight triage clusters, and assigned case workflows exist; trained clustering does not. |
| Automated real/decoy routing | Implemented for demo | The proxy routes to separate real-app and decoy services using the live decision engine. |
| Fake endpoints and fake data | Implemented for demo | The isolated decoy service exposes static, synthetic responses without real secrets. |
| Honeytoken detection | Implemented for demo | Configured decoy credential use and per-actor canary tokens are detected, stored, alerted, and shown on the dashboard; issued canary assignments are persisted without raw token values and can be revoked for operator review. |
| PostgreSQL/Supabase storage | Partial | Async PostgreSQL and Alembic are supported for events, alerts, honeytoken hits, and actor profiles; Supabase deployment is pending. |
| Feature-vector storage | Implemented | Request and optional CICIDS-style flow features are stored with events. |
| CICIDS2017 dataset | Partial | CICIDS-style single-CSV and directory adapters exist; local DDoS and full-directory CICIDS2017 splits have been prepared, reviewed, trained, and evaluated. Dataset provenance review is local-only and custom API-domain data is still pending. |
| Custom API logs | Partial | Runtime events, features, analyst-corrected labels, JSONL export, raw API-log JSONL ingestion with common access-log aliases, validation, split tooling, deterministic local API-domain fixture generation, and local retraining are available; reviewed production-like API-domain datasets are still pending. |
| Precision/recall/F1/FPR evaluation | Implemented | The Random Forest trainer calculates all four metrics. |
| Real-time WebSocket dashboard | Implemented for demo | A dedicated read-only WebSocket sends immediate events/alerts and complete coalesced snapshots after traffic or operator changes; adaptive HTTP polling remains as reconciliation and disconnect fallback. Production session/edge authentication is pending. |
| Security dashboard and alerts | Implemented for demo | Live metrics, events, risk history, decoy status, actor triage, and internal alerts are available. |
| Adaptive decoy generation | Partial | The in-process decoy API and redirected external decoy service select variants and issue epoch-rotatable per-actor synthetic canary tokens; assignment/revoke lifecycle records exist, while multi-operator lifecycle workflows are pending. |
| Docker Compose | Locally verified | Compose, health checks, and Dockerfiles exist; local image build and service startup have been verified, but CI and production deployment are still pending. |
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
- has locally trained and reviewed shadow-ready Random Forest artifacts from
  CICIDS2017 DDoS and full-directory splits;
- records and alerts on configured and per-actor issued decoy credential reuse as honeytoken hits;
- generates adaptive decoy responses with epoch-rotatable synthetic per-actor
  canary tokens;
- persists issued canary assignment records with hashed token values and
  supports operator revocation for lifecycle review;
- persists actor profiles from fingerprints, events, and honeytoken hits;
- groups actor profiles into lightweight dashboard triage clusters;
- recommends, assigns, filters, and persists investigation case workflows from actor clusters;
- supports analyst labels for correcting event classification outcomes;
- exports analyst-labeled feature vectors as JSON Lines for model training;
- trains local shadow-mode candidate artifacts from analyst-labeled events;
- prepares validated train/test splits from MIRAGE JSONL, custom API-log JSONL,
  CICIDS-style CSV, and CICIDS-style CSV directory sources;
- can generate deterministic API-domain fixture logs for local adapter and
  shadow-artifact validation;
- displays live backend data, actor clusters, and recommended triage cases on a
  dashboard with complete authenticated WebSocket snapshots, reconnect handling,
  and adaptive polling fallback;
- can train and evaluate a Random Forest model from labeled feature records.

It should not yet claim arbitrary ingress interception, a production ML model,
trained actor clustering, multi-analyst queues, multi-operator token lifecycle
approval workflows, production dashboard authentication, or deployed Supabase/Railway/Vercel
infrastructure.
