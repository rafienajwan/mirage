# Project MIRAGE - Architecture

## Implemented MVP

```mermaid
graph TD
    A[Client or simulator] --> B[FastAPI inspection API]
    B --> C[Feature extraction]
    C --> D[Heuristic risk and anomaly engines]
    D --> E{Decision engine}
    E -->|Allow or monitor| F[Event and alert storage]
    E -->|Redirect| G[Safe decoy response templates]
    G --> F
    F --> H[Polling security dashboard]
    C --> I[ML-ready feature vectors]
    I --> J[Offline Random Forest trainer]
```

The gateway currently evaluates submitted request metadata. It does not yet
forward arbitrary traffic to a protected application or isolated decoy service.

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
