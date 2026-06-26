# Actor Profiles

MIRAGE builds lightweight actor profiles from recent stored events. Profiles
group repeated activity by the privacy-safe `fingerprint_hash` generated during
inspection, then enrich the profile with risk scores, decoy redirects, paths,
and honeytoken hits.

## Dashboard API

```text
GET /api/v1/dashboard/actors
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

## Current Boundaries

Profiles are computed from recent events and are intended for dashboard
triage. MIRAGE does not yet persist long-lived actor records, cluster related
fingerprints, assign cases, or issue per-attacker honeytokens.
