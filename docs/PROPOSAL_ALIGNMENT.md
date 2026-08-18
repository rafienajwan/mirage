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
proposal's custom API-log requirement is still incomplete at representative
scale. The first hash-bound runtime batch has been independently reviewed and
finalized with 40 events split evenly between normal and suspicious labels.
A pilot candidate has been trained and evaluated, but a varied local shadow
observation reached only `0.642857` agreement and monitored all 15 normal
requests. The artifact remains local and shadow-only. Multi-batch collection
now supports unlabeled borderline scenarios and hash-verified aggregation, but
no additional analyst-reviewed rows have been claimed yet.

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
| Custom API logs | Partial | JSONL adapters, analyst-label export, hash-bound manual runtime review, deterministic multi-batch aggregation, and synthetic fixtures exist. The first independently labeled 40-row batch has been trained and evaluated as a shadow-only pilot; collection still needs to reach 1,000 representative analyst-reviewed rows. |
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

1. Collect additional independently reviewed runtime batches until the
   promotion dataset minimum of 1,000 rows is met, emphasizing diverse normal
   and borderline traffic as well as suspicious requests. Use the hash-verified
   multi-batch workflow and do not treat scenario categories as labels.
2. Retrain with a representative holdout and collect at least 500 shadow events
   with acceptable false-positive impact and the configured agreement gate.
3. Approve active hybrid routing only after dataset, artifact, false-positive,
   and shadow-observation gates pass; keep `ml_only` experimental.
4. Provision Vercel, Railway, and Supabase, run migrations, verify private and
   public networking, and execute an end-to-end HTTPS/WSS smoke test.
