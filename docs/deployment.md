# Deploying MIRAGE to Supabase, Railway and Vercel

This runbook takes an empty set of accounts to a running MIRAGE stack and
ends with `scripts/smoke_deploy.py` passing over HTTPS and WSS. Do the steps
in order: later steps need values from earlier ones.

| Piece | Provider | Reachable from |
| --- | --- | --- |
| PostgreSQL | Supabase | gateway, and your machine for migrations and the smoke test |
| `real-app-demo` | Railway | the gateway only (private network) |
| `decoy` | Railway | the gateway only (private network) |
| `gateway` | Railway | the internet (public domain): proxy, operator API, dashboard stream |
| `web` dashboard | Vercel | the internet |

Never commit any value you generate here. Put secrets in the provider
dashboards or CLIs only. `.env.supabase.example` lists every variable as an
empty checklist.

## 0. Generate secrets

Run this once per value and keep the results in a password manager:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

| Name | Used by | Notes |
| --- | --- | --- |
| `MIRAGE_API_KEY` | gateway, Vercel | 32+ characters |
| `MIRAGE_DASHBOARD_TICKET_SECRET` | gateway, Vercel | 32+ characters; the same value on both |
| `MIRAGE_OPERATOR_SESSION_SECRET` | Vercel only | 32+ characters |
| `DECOY_LOGIN_TOKEN`, `DECOY_OAUTH_TOKEN`, `DECOY_SERVICE_TOKEN` | gateway, decoy | Synthetic. The same three values on both services. Never real credentials |
| first admin password | you | 12 to 256 characters |

## 1. Supabase

1. Create a project. Store the database password it asks for.
2. **Turn off the Data API** (Project Settings → Data API). MIRAGE never uses
   it, and with it on, Supabase serves every table in the `public` schema to
   anyone holding the project's public `anon` key. Migration `0012` also
   enables row-level security on every MIRAGE table as a second line of
   defence, but nothing needs the API on.
3. Open **Connect** and copy the **Session pooler** connection string. It
   looks like
   `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`.
   Put the database password in place of `<password>`, URL-encoded if it
   contains reserved characters, and append `?sslmode=require`.
   - Use the session pooler (port 5432). The gateway refuses to start with
     the transaction pooler (port 6543), which breaks asyncpg's prepared
     statements.
   - Use the direct connection (`db.<ref>.supabase.co`) only if your Railway
     environment has outbound IPv6 or you bought Supabase's IPv4 add-on.
   - The scheme and `sslmode` can stay as pasted. The gateway rewrites
     `postgres://`/`postgresql://` to `postgresql+asyncpg://` and `sslmode`
     to asyncpg's `ssl`.

   This string is `DATABASE_URL` below.
4. Run the migrations from your machine. The gateway also runs them on every
   start, but running them first shows connection problems before anything
   is deployed:

   ```bash
   cd apps/gateway
   python -m venv venv && . venv/bin/activate      # Windows: venv\Scripts\activate
   pip install -e ".[postgres]"
   read -rs DATABASE_URL && export DATABASE_URL    # paste, then Enter
   alembic upgrade head
   alembic current                                 # prints 20261110_0012 (head)
   ```

5. Create the first admin. It prompts for the password twice:

   ```bash
   python scripts/manage_operators.py create admin --role admin
   python scripts/manage_operators.py list         # admin admin enabled
   ```

   Keep this shell open: step 5 reuses `DATABASE_URL`.

## 2. Railway

Create one Railway project with three services, all from this GitHub
repository. For each service, set **Settings → Source → Root Directory** and
**Settings → Config-as-code → Railway config file** to the absolute paths
below. Railway then builds the service's `Dockerfile` and uses its
`/health` check.

| Service name | Root directory | Config file |
| --- | --- | --- |
| `real-app-demo` | `/apps/real-app-demo` | `/apps/real-app-demo/railway.json` |
| `decoy` | `/apps/decoy` | `/apps/decoy/railway.json` |
| `gateway` | `/apps/gateway` | `/apps/gateway/railway.json` |

Variables can be set under each service's **Variables** tab or with the
Railway CLI (`railway link`, then
`railway variables --service <name> --set "KEY=value"`). `${{...}}` values
are Railway reference variables: type them literally and Railway resolves
them.

### Private versus public networking

- `real-app-demo` and `decoy` get **no public domain**. The gateway reaches
  them at `<service>.railway.internal` on Railway's private network. An
  attacker can then only reach the decoy through the gateway, as in the
  Compose network layout (`infra/docker-compose.yml`).
- Only the `gateway` gets a public domain (**Settings → Networking →
  Generate Domain**, or `railway domain --service gateway`). That domain
  serves the attacker-facing proxy, the operator API (API key required) and
  the dashboard WebSocket.
- The private network can be IPv6-only, so both upstreams listen on `::`
  (`HOST=::`). The images default to `0.0.0.0` (IPv4) because uvicorn on
  `::` refuses IPv4, which Compose needs. If your environment's private
  network also carries IPv4 you can drop `HOST`. The smoke test's routing
  checks show whether the gateway can reach them.

### `real-app-demo` variables

| Variable | Value | Source |
| --- | --- | --- |
| `PORT` | `8001` | fixed; set explicitly so the gateway's URL can reference it |
| `HOST` | `::` | private network listener, see above |

### `decoy` variables

| Variable | Value | Source |
| --- | --- | --- |
| `PORT` | `8002` | fixed |
| `HOST` | `::` | private network listener |
| `DECOY_LOGIN_TOKEN` | synthetic value | step 0 |
| `DECOY_OAUTH_TOKEN` | synthetic value | step 0 |
| `DECOY_SERVICE_TOKEN` | synthetic value | step 0 |
| `DECOY_CANARY_EPOCH` | `v1` | increase to rotate canary tokens |
| `DECOY_DATABASE_URL` | `postgresql://synthetic.invalid:5432/decoy` | synthetic; never a real database |

### `gateway` variables

Leave `PORT` unset: Railway injects it and points the public domain at it.

| Variable | Value | Source |
| --- | --- | --- |
| `APP_ENV` | `production` | fixed; enables startup validation and hides docs |
| `DATABASE_URL` | session pooler URL | step 1.3 |
| `MIRAGE_API_KEY` | secret | step 0 |
| `MIRAGE_DASHBOARD_TICKET_SECRET` | secret | step 0 |
| `REAL_APP_URL` | `http://${{real-app-demo.RAILWAY_PRIVATE_DOMAIN}}:${{real-app-demo.PORT}}` | Railway reference |
| `DECOY_SERVICE_URL` | `http://${{decoy.RAILWAY_PRIVATE_DOMAIN}}:${{decoy.PORT}}` | Railway reference |
| `FRONTEND_ORIGIN` | `https://<project>.vercel.app` | step 3; set a placeholder until then |
| `DECOY_LOGIN_TOKEN`, `DECOY_OAUTH_TOKEN`, `DECOY_SERVICE_TOKEN` | same as `decoy` | step 0; also `${{decoy.DECOY_LOGIN_TOKEN}}` etc. |
| `DECOY_CANARY_EPOCH` | same as `decoy` | |
| `DECOY_DATABASE_URL` | same as `decoy` | |
| `ML_ROUTING_MODE` | `heuristic` | keep until the promotion gates pass |
| `ML_LIVE_ROUTING_APPROVED` | `false` | |
| `TRUSTED_PROXIES` | empty at first | step 5 |
| `RATE_LIMIT_PER_MINUTE` | `120` | optional; see limitations |

The private hop to the upstreams is plain `http://` inside Railway's
network. Everything that leaves Railway uses TLS: the public domain, the
Vercel calls and Supabase (`ssl=require`).

The gateway runs `alembic upgrade head` before it starts listening. Its
health-check timeout is 60 seconds to cover that. A failed migration fails
the deploy and leaves the previous deployment serving.

`MIRAGE_MODEL_ARTIFACT` stays empty: the image does not include model files,
and routing is heuristic.

Deploy all three. Check that each shows **Active** and the gateway's public
domain answers:

```bash
curl -s https://<gateway>.up.railway.app/health     # {"status":"ok"}
```

## 3. Vercel

1. Import the repository and set **Root Directory** to `apps/web`.
   `apps/web/vercel.json` sets the Next.js build. Or use the CLI from
   `apps/web`: `vercel link`.
2. Add these as **server-side** variables for the Production environment
   (Settings → Environment Variables, or `vercel env add <NAME> production`).
   None of them may be `NEXT_PUBLIC_*`.

| Variable | Value | Source |
| --- | --- | --- |
| `MIRAGE_INTERNAL_API_URL` | `https://<gateway>.up.railway.app` | step 2 public domain |
| `MIRAGE_DASHBOARD_WS_URL` | `wss://<gateway>.up.railway.app/api/v1/dashboard/ws` | step 2 public domain |
| `MIRAGE_API_KEY` | same as gateway | step 0 |
| `MIRAGE_DASHBOARD_TICKET_SECRET` | same as gateway | step 0 |
| `MIRAGE_OPERATOR_SESSION_SECRET` | secret | step 0 |
| `MIRAGE_SECURE_COOKIES` | `true` | fixed for HTTPS |
| `MIRAGE_TRUST_PROXY_HEADERS` | `true` | Vercel sets `X-Forwarded-For` itself |

3. Deploy to production (`vercel --prod`) and note the production URL,
   for example `https://<project>.vercel.app`.

## 4. Point the gateway at the dashboard

The gateway accepts dashboard WebSockets only from `FRONTEND_ORIGIN`, and it
is the only browser origin CORS allows outside development. Set the
gateway's `FRONTEND_ORIGIN` to the Vercel production origin exactly: scheme
and host, no path, no trailing slash. Then redeploy the gateway.

Preview deployments have other origins, so their live stream is refused.
Test against the production URL.

## 5. Run the smoke test

From `apps/gateway` in the shell from step 1 (venv active, `DATABASE_URL`
exported):

```bash
export SMOKE_GATEWAY_URL=https://<gateway>.up.railway.app
export SMOKE_WEB_URL=https://<project>.vercel.app
export SMOKE_OPERATOR_USERNAME=admin
read -rs SMOKE_OPERATOR_PASSWORD && export SMOKE_OPERATOR_PASSWORD
python scripts/smoke_deploy.py
echo "exit=$?"
```

Expected output, one line per check, exit status 0:

```
PASS gateway health      https://<gateway>/health -> 200
PASS web health          https://<project>.vercel.app/login -> 200
PASS route to real app   proxy /api/products -> real app
PASS route to decoy      proxy /.env (scanner) -> decoy
PASS operator login      signed in as admin
PASS operator API        dashboard -> gateway -> database: 1 operator(s)
PASS dashboard stream    wss://<gateway>/api/v1/dashboard/ws -> snapshot
PASS database migrated   aws-0-<region>.pooler.supabase.com at head 20261110_0012
8/8 checks passed
```

What each check proves:

| Check | Proves |
| --- | --- |
| gateway health, web health | both public endpoints answer over HTTPS |
| route to real app | gateway → `real-app-demo` over the private network |
| route to decoy | gateway → `decoy` over the private network, and the heuristic redirects a scanner |
| operator login | Vercel → gateway login with the shared API key; session secret and secure cookie work |
| operator API | an authenticated dashboard call crosses Vercel → gateway → Supabase |
| dashboard stream | the ticket secret matches on both sides, `FRONTEND_ORIGIN` is right, and WSS reaches the gateway |
| database migrated | Supabase is at the Alembic head this checkout expects |

HTTPS and WSS are mandatory. `http://` or `ws://` fail unless
`--allow-insecure` is passed, which is for the local Compose stack only. The
output never contains the password, session cookie, stream ticket or
database URL.

The routing checks send two proxy requests. The decoy one is recorded as an
attack event, so expect one high-risk event in the dashboard per run.

To prove the private upstreams are not public, check in Railway that
`real-app-demo` and `decoy` have no domain under **Networking**. Leave
`SMOKE_REAL_APP_URL` and `SMOKE_DECOY_URL` unset. Those direct health
checks are only for setups that deliberately expose the upstreams.

### Then set `TRUSTED_PROXIES`

Open the dashboard and look at the source IP of the smoke test's events. If
it is a private address rather than your machine's public address, Railway's
edge proxy is the peer. Set `TRUSTED_PROXIES` on the gateway to that
address's range so the gateway reads the client address from
`X-Forwarded-For`. Redeploy, rerun the smoke test, and check that new events
carry your public address. Without this, every client shares one rate-limit
budget and one actor profile.

### When a check fails

| Failing check | Usual cause |
| --- | --- |
| gateway health | deploy failed. Read the gateway's deploy logs; a validation error names the missing variable |
| route to real app / decoy (502) | `REAL_APP_URL`/`DECOY_SERVICE_URL` wrong, `PORT` not set on the upstream, or `HOST=::` missing on an IPv6-only private network |
| operator login (503) | a Vercel variable is missing |
| operator login (401) | wrong username or password, or the admin was created in a different database |
| operator login (403) | the `SMOKE_WEB_URL` origin differs from the URL Vercel serves (redirected domain) |
| dashboard stream | `FRONTEND_ORIGIN` does not match the Vercel origin exactly, the ticket secrets differ, or `MIRAGE_DASHBOARD_WS_URL` is not `wss://` |
| database migrated | the gateway has not deployed this revision, or `DATABASE_URL` points elsewhere |

## Run the same test locally

The Compose stack proves the script and images without any cloud account.
From the repository root with a populated `.env`:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build --wait
docker compose --env-file .env -f infra/docker-compose.yml exec gateway \
  python scripts/manage_operators.py create admin --role admin
cd apps/gateway
SMOKE_GATEWAY_URL=http://localhost:8000 SMOKE_WEB_URL=http://localhost:3000 \
SMOKE_OPERATOR_USERNAME=admin python scripts/smoke_deploy.py --allow-insecure
```

The database is on an internal Compose network, so `database migrated` fails
from the host unless you publish the `db` port with a local override file and
export a matching `DATABASE_URL` (host `127.0.0.1`).

## Rolling back

- Railway: redeploy the previous deployment from the service's
  **Deployments** tab. Migrations do not roll back on their own. If the new
  revision must be reverted, run `alembic downgrade -1` from step 1's shell
  first.
- Vercel: promote the previous production deployment.

## Known limitations

- **Login throttle on Vercel.** The five-failures-per-15-minutes throttle
  lives in one Node.js process's memory. Vercel runs many short-lived
  instances, so it is not enforced across them. Give every operator a long
  random password, or run the dashboard as one long-lived process (the
  `apps/web` Docker image) if you rely on it.
- **Rate limits are per gateway instance.** Run one gateway replica, or
  accept that each replica counts separately.
- **Not yet verified live.** The smoke test has passed against the local
  Compose stack only; see `docs/PROPOSAL_ALIGNMENT.md`. Record the date and
  output of the first passing live run there.
