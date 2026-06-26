# Honeytoken Tracking

MIRAGE exposes synthetic decoy credentials in fake responses. When a later
request reuses one of those configured decoy values, the gateway records a
honeytoken hit and raises a critical alert.

## What Is Tracked

The detector checks bounded request metadata:

- request path;
- user agent;
- payload indicators;
- a small request excerpt captured by the proxy route.

It matches configured decoy values:

- `DECOY_LOGIN_TOKEN`;
- `DECOY_OAUTH_TOKEN`;
- `DECOY_SERVICE_TOKEN`;
- `DECOY_DATABASE_URL`.

The stored hit records token kind and label, masked source IP, path, method,
event id, and evidence text. It does not store the full token value.

## Dashboard API

```text
GET /api/v1/dashboard/honeytokens
```

The dashboard uses this endpoint to show total honeytoken hits and the latest
interaction. Honeytoken hits also create critical alerts.

## Current Boundaries

This is a first tracking workflow. Token issuance, rotation, per-attacker token
assignment, and cross-session actor profiling are still future work.
