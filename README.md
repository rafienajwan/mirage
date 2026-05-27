# Project MIRAGE
### Autonomous AI-Driven Cyber Deception & Threat Mitigation Platform

[![Next.js](https://img.shields.io/badge/Next.js-16.2-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![AI/ML](https://img.shields.io/badge/AI%2FML-Scikit--Learn-FF6F00?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://scikit-learn.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4.0-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

---

Project MIRAGE is an autonomous cybersecurity defense platform that secures modern APIs and application infrastructures. By combining real-time AI risk scoring with dynamic decoy containment, MIRAGE doesn't just block attacks—it absorbs, analyzes, and neutralizes them inside simulated execution sandboxes. The system dynamically redirects suspicious vectors into high-fidelity synthetic environments, exposing decoy databases and honeytoken credentials while generating threat intelligence to harden production systems.

---

## Technical Overview

### The Problem: Passive Firewalls & Alert Fatigue
Modern enterprise infrastructures face massive automated probes, zero-day vulnerabilities, and credential stuffing vectors. Traditional firewalls and intrusion prevention systems (IPS) operate on static blacklists, blocking requests flatly. This provides attackers with immediate feedback, allowing them to cycle payloads, rotating IPs, and mutate payloads until they bypass static rules. Concurrently, SOC analysts suffer from alert fatigue, sorting through millions of blocked requests to identify high-risk advanced persistent threats (APTs).

### The MIRAGE Approach: Active Cyber Deception
Project MIRAGE transforms cybersecurity from a passive defense posture to an **active deception campaign**. Instead of rejecting suspicious traffic with a `403 Forbidden` response, MIRAGE routes anomalies to an isolated container network:
- **Intrusion Detention**: Attackers believe they have successfully breached an endpoint. They waste resources exploring fake directories, scraping synthetically generated tables, and testing invalid API tokens.
- **Signal Hardening**: While the attacker is trapped, MIRAGE logs behavioral fingerprints, tracks command payloads, and flags their IP ranges across the network.
- **Honeytoken Traps**: Dynamic honeytoken files (e.g., false `.env` configurations or AWS credential keys) are leaked to the attacker. If the attacker attempts to use these credentials on actual cloud infrastructure, alert systems trigger immediate lockouts.

---

## Core Features

### 🧠 AI Risk Scoring & Anomaly Detection
Analyzes incoming headers, body payload signatures, routing behaviors, and request frequencies.
* **Security Purpose**: Employs isolation scoring to isolate zero-day exploit patterns and credential stuffing attempts that bypass traditional signature-based Web Application Firewalls (WAF).

### 🕸️ Dynamic Decoy Environments
Constructs a sandboxed network mimic layer loaded with fake schemas and endpoints.
* **Security Purpose**: Distracts and detains attackers inside a synthetic system, exhausting their time and resources while tracking their manual exploitation flows.

### 🔑 Canary Token System
Injects dynamically generated false credentials, dummy database strings, and honeytoken environment configs (`.env`) into decoy filesystems.
* **Security Purpose**: Generates high-confidence alert signals the moment canary credentials are exfiltrated and tested against actual system endpoints.

### 🔬 Threat Analysis Engine
Generates detailed command footprints, fingerprint logs, and payloads from trapped attackers.
* **Security Purpose**: Transforms active attacks into structured intelligence data, allowing operators to patch production gaps before real damage can occur.

### 📡 SOC Analytics Dashboard & Real-Time Alerts
A unified dashboard built on high-fidelity animations, real-time threat maps, and visual system states.
* **Security Purpose**: Streamlines security operations by highlighting critical risk anomalies and decoy redirect events while silencing standard noise.

---

## Architecture Flow

The diagram below outlines how the MIRAGE API Gateway routes traffic dynamically based on AI evaluation:

```mermaid
graph TD
    A[User / Attacker] --> B[API Gateway / Proxy]
    B --> C{AI Risk & Anomaly Analyzer}
    
    C -- "Normal Traffic (Score < 0.65)" --> D[Production Core App]
    D --> E[(Production PostgreSQL Database)]
    
    C -- "Suspicious Traffic (Score >= 0.65)" --> F[MIRAGE Decoy Sandbox]
    F --> G[Fake API Endpoint Templates]
    F --> H[Fake Database / Seed Data]
    F --> I[Honeytoken Canary Keys]
    
    F --> J[Deception Log Manager]
    J --> K[Real-time SOC Dashboard]
    J --> L[Automated Incident Response & SOC Alerts]
```

### Request Lifecycle
1. **Ingress**: Traffic hits the API Gateway.
2. **Analysis**: Request metadata is evaluated by the AI Risk Scorer.
3. **Branching**:
   - **Allowed**: Routed directly to production databases and APIs.
   - **Redirected**: Routed to the Decoy Container without dropping the connection, keeping the HTTP headers indistinguishable to the attacker.
4. **deception**: The attacker interacts with mock endpoints, extracting fake data.
5. **Mitigation**: Logs are pushed to the security dashboard, and alerts are dispatched via secure webhooks.

---

## Technology Stack

```
   ┌─────────────────────────────────────────────────────────────┐
   │                       PROJECT MIRAGE                        │
   └─────────────────────────────────────────────────────────────┘
          │                           │                       │
          ▼                           ▼                       ▼
   ┌──────────────┐            ┌──────────────┐        ┌──────────────┐
   │   FRONTEND   │            │   BACKEND    │        │ DATA & DEPLOY│
   ├──────────────┤            ├──────────────┤        ├──────────────┤
   │ Next.js      │            │ FastAPI      │        │ PostgreSQL   │
   │ Tailwind v4  │            │ Uvicorn      │        │ Supabase     │
   │ shadcn/ui    │            │ SQLAlchemy   │        │ Docker       │
   │ Framer Motion│            │ Pydantic     │        │ Vercel       │
   │ Recharts     │            │ Scikit-Learn │        │ Railway      │
   └──────────────┘            └──────────────┘        └──────────────┘
```

- **Frontend Dashboard**: React and Next.js App Router for server-rendered page assets. Styled with Tailwind CSS v4, shadcn/ui components, Framer Motion transitions, and Recharts graph animations.
- **Backend Services**: FastAPI implementation utilizing Uvicorn for asynchronous high-throughput request handling. Database interactions managed via SQLAlchemy models and Pydantic schemas.
- **AI Core**: Scikit-Learn classification algorithms running anomaly scoring over Pandas and Numpy request vector shapes.
- **Infrastructure**: Containerized using Docker Compose for staging multi-container decoy clusters.

---

## Project Structure

```
project-mirage/
├── backend/                  # API Gateway, Scorer, and Log Engine
│   ├── app/
│   │   ├── api/              # Route endpoints (Ingress, Logs, Stats)
│   │   ├── core/             # Configuration and database connectivity
│   │   ├── models/           # SQLAlchemy DB schema models
│   │   ├── schemas/          # Pydantic validation schemas
│   │   ├── services/         # AI Classifier, Decoy Router, logger
│   │   └── main.py           # FastAPI server entry point
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile            # Backend container configuration
├── frontend/                 # SOC Landing Page & Analytics Dashboard
│   ├── src/
│   │   ├── app/              # Next.js App Router root layout and pages
│   │   ├── components/       # Visual widgets, charts, and video elements
│   │   └── lib/              # Styling and framer-motion settings
│   ├── package.json          # Node dependencies
│   └── tsconfig.json         # TypeScript configuration
├── decoy-pages/              # High-Fidelity Decoy API & Honeytokens
│   ├── templates/            # Simulated folder structures & API responses
│   └── honeytokens/          # Injected fake configs (.env, AWS yaml)
└── docker-compose.yml        # Docker orchestrations config
```

---

## Landing Page Philosophy
The MIRAGE landing page layout is inspired by **MotionSites AI** and high-end enterprise SaaS architectures:
- **Cinematic Backdrop**: Replaced traditional static grids with a fullscreen HLS video background running an active cybernetic topology feed.
- **Cyberpunk Minimalism**: Uses HSL colors, cyan and emerald accents, and glassmorphic panels built on `backdrop-blur-xl` and low opacity borders.
- **Asymmetrical Balance**: Visual components are arranged to frame the typography organically, avoiding rigid grids.
- **Focused Hierarchy**: The screen centers on the primary headline `DETECT. DECEIVE. DEFEND.` while the active gauges and anomaly chart widgets drift slowly in the background as ambient HUD indicators.

---

## Installation & Setup

### Prerequisites
- Node.js LTS (v24+)
- Python (v3.11+)
- Docker & Docker Compose

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/project-mirage.git
cd project-mirage
```

### 2. Environment Configurations
Create a `.env` file in both the `/frontend` and `/backend` directories:

**Backend (`backend/.env`):**
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mirage
SECRET_KEY=your_deception_secret_key_here
AI_THRESHOLD=0.65
DECOY_API_URL=http://localhost:8000/decoy
```

**Frontend (`frontend/.env.local`):**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Running Backend Services
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use: .\venv\Scripts\activate
pip install -r requirements.txt
python app/main.py
```

### 4. Running Frontend Dashboard
```bash
cd ../frontend
npm install
npm run dev
```

### 5. Running with Docker Compose
To launch the entire platform stack along with decoy API containers and PostgreSQL instances:
```bash
docker-compose up --build
```

---

## MVP Demonstration Flow

To demonstrate the MIRAGE active containment workflow:

1. **Traffic Entry**: Execute a standard API payload request:
   ```bash
   curl -H "User-Agent: NormalBrowser" http://localhost:8000/api/v1/users
   ```
   *Response*: Returns standard production user metrics (`Status: 200 OK`).

2. **Attack Probe**: Execute a request containing a SQL injection payload:
   ```bash
   curl -H "User-Agent: AttackerScript" "http://localhost:8000/api/v1/users?id=1%20OR%201=1"
   ```
   *Response*: The AI Risk Scorer evaluates the parameters as highly anomalous (Score `0.94`). The gateway seamlessly detours the path to the Decoy Container.

3. **Decoy Engagement**: The response returns fake user data seeded with honeytoken emails (`admin@decoy-mirage.io`). 

4. **Alert Trigger**: The **Security Dashboard** updates in real-time, displaying a flashing anomalous spike on the chart and flagging the attacker's IP signature on the live logs.

---

## Future Roadmap

- **LLM Threat Analysis**: Integrate small language models to dynamically generate fake code file outputs and command-line shell scripts based on real-time commands entered by the trapped attacker.
- **AI Fingerprinting**: Implement behavioral graph clustering to identify repeat attackers even if they rotate IP addresses, User-Agents, and headers.
- **Honeynet Orchestration**: Deploy Kubernetes operators to spin up temporary Docker container decoys on-demand for each flagged IP network scope.
- **SIEM / SOC Connectors**: Out-of-the-box integrations with Splunk, Datadog, Slack, and PagerDuty to streamline notifications flows.