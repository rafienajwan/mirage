# Project MIRAGE - Architecture

## Implemented MVP

```mermaid
graph TD
    A[Client or simulator] --> B[FastAPI inspection and proxy API]
    B --> C[Feature extraction]
    C --> D[Heuristic risk and anomaly engines]
    D --> E{Decision engine}
    E -->|Allow or monitor| F[Isolated demo application]
    E -->|Redirect| G[Isolated static decoy service]
    E --> H[Event and alert storage]
    H --> K[Polling security dashboard]
    C --> I[ML-ready feature vectors]
    I --> J[Offline Random Forest trainer]
```

The gateway evaluates submitted metadata and forwards requests received under
`/api/v1/proxy/*`. It does not yet intercept arbitrary application ingress.

## Target Architecture From The Proposal

```mermaid
graph TD
    A[Incoming traffic] --> B[Transparent defense gateway]
    B --> C[Hybrid heuristic and ML analysis]
    C --> D{Traffic decision}
    D -->|Normal| E[Real application]
    D -->|Suspicious| F[Isolated adaptive decoy]
    F --> G[Honeytokens and interaction capture]
    E --> H[Threat intelligence database]
    G --> H
    H --> I[WebSocket dashboard and incident response]
```

See `docs/PROPOSAL_ALIGNMENT.md` for the exact implementation gap.
