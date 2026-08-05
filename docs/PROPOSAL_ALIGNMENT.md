# Proposal Alignment

Source proposal: **Project MIRAGE: Adaptive AI-Driven Cyber Deception System
for Autonomous Threat Hunting**, WRECK-IT 7.0.

## Summary

The repository implements the proposal's core local detect-deceive-observe
flow: a FastAPI gateway inspects explicit proxy traffic, applies explainable
risk rules, routes suspicious requests to an isolated decoy, persists events,
and updates a protected Next.js dashboard. This is a working MVP prototype,
not a verified production deployment.

The ML pipeline is implemented for dataset preparation, Random Forest
training, evaluation, artifact review, and runtime shadow scoring. Live ML
routing remains an experimental capability and is disabled by default. The
proposal's custom API-log requirement is still incomplete because the current
API-domain data is deterministic synthetic test data rather than independently
reviewed runtime logs.

## Capability Matrix

| Proposal capability | Status | Repository reality |
| --- | --- | --- |
| FastAPI defense gateway | Implemented for MVP | `/api/v1/proxy/*` inspects and forwards traffic through explicit guarded routes. It does not intercept arbitrary infrastructure traffic. |
| Hybrid risk scoring | Partial | Explainable heuristic scoring is the safe default. Experimental `hybrid` and `ml_only` modes require both a reviewed artifact and explicit `ML_LIVE_ROUTING_APPROVED=true`. |
| Scikit-learn anomaly detection | Partial | Random Forest training, evaluation, artifact lineage checks, and shadow inference exist. Runtime anomaly detection itself is still heuristic. |
| Threat fingerprint matching | Implemented for MVP | Stable fingerprints, persistent actor profiles, lightweight triage clusters, and case workflows are available. |
| Automated real/decoy routing | Implemented for MVP | The proxy routes allowed or monitored traffic to the demo app and suspicious traffic to the isolated decoy. |
| Fake endpoints and fake data | Implemented for MVP | The decoy exposes synthetic responses and never needs real credentials. |
| Honeytoken detection | Implemented for MVP | Configured decoy credentials and issued per-actor canaries are recorded, alerted, displayed, and revocable. |
| PostgreSQL/Supabase storage | Partial | Async PostgreSQL and Alembic are implemented and Compose-tested. Supabase connection guidance exists, but no live Supabase deployment is verified. |
| Feature-vector storage | Implemented | Versioned request and bounded payload-shape features are persisted with lineage and contract checks. |
| CICIDS2017 dataset | Implemented as supporting benchmark | Local ignored CICIDS2017 splits have been prepared and evaluated. Their network-flow domain does not by itself validate API routing quality. |
| Custom API logs | Partial | JSONL adapters, analyst-label export, runtime collection tooling, and deterministic synthetic fixtures exist. Real reviewed API logs and independent labels are still missing. |
| Precision, recall, F1, and FPR | Implemented | Training and holdout tools calculate all four metrics. Results must be reported with their dataset and sample size. |
| Real-time WebSocket dashboard | Implemented locally | Authenticated sessions, short-lived signed stream tickets, WebSocket snapshots, and polling reconciliation are implemented. |
| Security dashboard and alerts | Implemented locally | Metrics, events, alerts, risk history, actor triage, and cases are protected by the operator session and server-side API bridge. |
| Adaptive decoy generation | Partial | Route-aware variants and rotatable per-actor synthetic canaries exist; the decoy is template-driven rather than generative. |
| Docker Compose | Locally verified | The five-service stack, health checks, Dockerfiles, and PostgreSQL migration startup are present. |
| Vercel, Railway, and Supabase deployment | Configuration scaffold | Per-service manifests and environment guidance exist, but actual cloud provisioning, networking, migrations, and smoke tests remain to be completed. |

## Safe Claims

MIRAGE can accurately claim that it:

- demonstrates the proposal's core local request inspection, risk analysis,
  decoy routing, logging, alerting, and dashboard flow;
- keeps dashboard API credentials server-side and uses signed operator sessions
  plus short-lived WebSocket tickets;
- prepares, trains, evaluates, and reviews Random Forest artifacts with
  precision, recall, F1, false-positive rate, and dataset lineage;
- runs reviewed artifacts in shadow mode without changing routing by default;
- provides experimental hybrid and ML-only routing behind a separate explicit
  approval switch;
- supports PostgreSQL locally and provides cloud configuration scaffolding.

It should not yet claim production readiness, validated cloud deployment,
arbitrary ingress interception, production-quality custom API training data,
or real-world ML accuracy. Metrics from deterministic synthetic fixtures must
be labeled as pipeline validation, not model-quality evidence.

## Remaining Proposal Work

1. Collect sanitized runtime API logs from the MIRAGE proxy, define a human
   review protocol, and produce independently reviewed normal/suspicious labels.
2. Train and evaluate a candidate on that API-domain dataset with a separate
   holdout, then observe it in shadow mode against representative traffic.
3. Approve active hybrid routing only after dataset, artifact, false-positive,
   and shadow-observation gates pass; keep `ml_only` experimental.
4. Provision Vercel, Railway, and Supabase, run migrations, verify private and
   public networking, and execute an end-to-end HTTPS/WSS smoke test.
