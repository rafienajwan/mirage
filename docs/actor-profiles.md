# Actor Profiles

MIRAGE persists lightweight actor profiles from stored events. Profiles group
repeated activity by the privacy-safe `fingerprint_hash` generated during
inspection, then enrich the profile with risk scores, decoy redirects, paths,
and honeytoken hits.

## Dashboard API

```text
GET /api/v1/dashboard/actors
GET /api/v1/dashboard/actor-clusters
GET /api/v1/dashboard/actor-cases
GET /api/v1/dashboard/actor-case-workflows
POST /api/v1/dashboard/actor-cases/{case_id}/open
PATCH /api/v1/dashboard/actor-case-workflows/{case_id}
```

Each profile includes:

- actor id derived from the fingerprint;
- masked source IP;
- first and last seen timestamps;
- request, suspicious, decoy redirect, and honeytoken counts;
- maximum and average risk score;
- top observed paths;
- latest routing decision;
- profile status: `quiet`, `watch`, `suspicious`, or `confirmed_interaction`.

Actor clusters group profiles by current status and dominant target path. Each
cluster returns a stable cluster id, label, actor count, representative actor
ids, shared paths, decoy redirect count, honeytoken hit count, maximum risk
score, and latest seen timestamp.

Actor cases begin as recommendations derived from clusters. Operators can open
one into a persisted workflow record, then move it between `open`,
`investigating`, and `closed`.

The Next.js dashboard renders actor profiles, cluster signals, and recommended
cases in the actor triage section.

## Current Boundaries

Profiles and clusters are intended for dashboard triage. MIRAGE now persists
aggregate actor records, groups similar profiles, and persists basic case
workflows, but it does not yet assign case owners, rotate issued canary tokens,
manage token assignment lifecycles, or run a trained clustering model.
