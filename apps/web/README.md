# MIRAGE Web

Next.js application containing the landing page, real-time security dashboard,
and a server-side bridge for authenticated simulation requests.

## Setup

```bash
cd apps/web
npm install
# Windows: Copy-Item .env.example .env.local
# Linux/macOS: cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000` or `http://localhost:3000/dashboard`.

## Environment

| Variable | Exposure | Purpose |
| --- | --- | --- |
| `MIRAGE_INTERNAL_API_URL` | Server only | Internal gateway URL used by dashboard bridges |
| `MIRAGE_API_KEY` | Server only | Authenticates all dashboard calls to the gateway |
| `MIRAGE_OPERATOR_PASSWORD` | Server only | Operator password; minimum 16 characters |
| `MIRAGE_OPERATOR_SESSION_SECRET` | Server only | Signs eight-hour operator sessions |
| `MIRAGE_DASHBOARD_TICKET_SECRET` | Server only | Signs 60-second WebSocket tickets |
| `MIRAGE_DASHBOARD_WS_URL` | Server only | Browser-reachable dashboard WebSocket URL |
| `MIRAGE_SECURE_COOKIES` | Server only | Enables Secure session cookies for HTTPS |

Never rename `MIRAGE_API_KEY` with a `NEXT_PUBLIC_` prefix. That would expose it
in the browser bundle.

The server also uses `MIRAGE_API_KEY` for the promotion-readiness bridge. The
dashboard receives sanitized readiness through that bridge and authenticated
WebSocket snapshots; artifact and dataset filesystem paths remain server-only.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the development server |
| `npm run lint` | Run ESLint |
| `npm test` | Compile and run stream contract tests with Node |
| `npm run build` | Build production assets |
| `npm start` | Serve a production build |

The authenticated WebSocket sends complete snapshots plus immediate event and
alert updates. The client obtains a fresh 60-second ticket for every reconnect.
HTTP reconciliation runs every 60 seconds while connected and every 10 seconds
while disconnected.
