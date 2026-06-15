# Project MIRAGE — Demo Flow

## Demonstration Scenario

This document describes the planned demonstration flow for Project MIRAGE.

### Step 1: Normal Traffic

A legitimate user sends a standard API request:

```
GET /api/v1/users
User-Agent: NormalBrowser
```

**Expected result**: The AI Risk Scorer evaluates the request as normal (score < 0.65). The request is routed to the production application and returns real data.

### Step 2: Suspicious Request

An attacker sends a request with suspicious parameters:

```
GET /api/v1/users?id=suspicious-parameter
User-Agent: UnknownScript
```

**Expected result**: The AI Risk Scorer flags the request as suspicious (score >= 0.65). The request is transparently redirected to the Decoy Environment.

### Step 3: Decoy Engagement

The attacker interacts with the decoy environment:

- Accesses fake endpoints returning fabricated data
- Discovers fake credentials (honeytokens)
- Attempts to access restricted files (e.g., `.env`)

**Expected result**: All interactions are logged by the Activity Logger. The attacker believes they are in the real system.

### Step 4: Dashboard Visualization

The Security Dashboard displays:

- A spike in the anomaly chart
- New entries in the threat activity feed
- Decoy environment status changes
- Alert notifications with severity labels

### Step 5: Incident Response

The platform generates:

- Threat fingerprint records
- Behavioral analysis summary
- Attacker IP and source information
- Automated alert notifications

## Mock Data

The current frontend uses safe, simulated mock data defined in `apps/web/src/lib/mock-data.ts`. No real exploits, credentials, or offensive payloads are included.
