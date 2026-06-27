# MIRAGE Web

Next.js application containing the landing page, polling security dashboard,
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
| `NEXT_PUBLIC_API_URL` | Browser | Public gateway base URL for dashboard reads |
| `MIRAGE_INTERNAL_API_URL` | Server only | Gateway URL used by the simulation bridge |
| `MIRAGE_API_KEY` | Server only | Authenticates simulation calls to the gateway |

Never rename `MIRAGE_API_KEY` with a `NEXT_PUBLIC_` prefix. That would expose it
in the browser bundle.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the development server |
| `npm run lint` | Run ESLint |
| `npm run build` | Build production assets |
| `npm start` | Serve a production build |

Dashboard data is refreshed with HTTP polling. Event and alert updates can use
the optional `NEXT_PUBLIC_DASHBOARD_WS_URL` WebSocket stream when configured;
polling remains the fallback for aggregate metrics.
