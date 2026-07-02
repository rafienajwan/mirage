# Honeytoken Tracking

MIRAGE exposes synthetic decoy credentials in fake responses. When a later
request reuses one of those configured values or an issued per-actor canary
token, the gateway records a honeytoken hit and raises a critical alert.

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

It also matches issued in-process canary tokens shaped like:

```text
mirage-issued-{kind}-canary-{assignment}
```

Issued tokens are deterministic per actor, token kind, and
`DECOY_CANARY_EPOCH`. Increase the epoch and restart gateway/decoy services to
rotate newly issued canaries while retaining detection for older canary-shaped
values.

The gateway now persists canary assignment records for generated in-process
decoy responses and successful proxy redirects to the external decoy service.
Assignment records store actor id, token kind, epoch, decoy type, source path,
status, timestamps, and a SHA-256 token hash. They do not store the raw token
value.

The stored hit records token kind and label, masked source IP, path, method,
event id, and evidence text. It does not store the full token value.

## Dashboard API

```text
GET /api/v1/dashboard/honeytokens
GET /api/v1/dashboard/canary-assignments
POST /api/v1/dashboard/canary-assignments/{assignment_id}/revoke
```

The dashboard can use these endpoints to show honeytoken hits, review issued
canary assignments, and revoke an assignment. Revoke is an operator lifecycle
control: it marks the persisted assignment as revoked for audit and rotation
tracking. Honeytoken hits also create critical alerts.

## Current Boundaries

This is still a bounded tracking workflow. The in-process decoy response API and
the redirected external decoy service can issue deterministic per-actor
synthetic canary tokens with epoch-based rotation, and the gateway records
assignment/revoke lifecycle state for operator review. It is not yet a
multi-operator lifecycle system with approval queues or external incident
response integrations.
