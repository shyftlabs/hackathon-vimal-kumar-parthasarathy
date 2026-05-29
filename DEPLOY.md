# Deploying FleetShield AI — Vercel (frontend) + Railway (backend)

The Next.js frontend goes on **Vercel**; the Python backend (FastAPI + the fleet
MCP server + the Continuum agent) goes on **Railway** with a managed **Redis**.
The frontend is already wired for a remote backend via `NEXT_PUBLIC_API_URL`
(`frontend/src/middleware.ts`) and `NEXT_PUBLIC_WS_URL` (voice WebSocket).

```
Browser ─▶ Vercel (Next.js)  ──/api/* rewrite──▶  Railway (FastAPI + MCP + Continuum)
                              ──wss /ws (voice)──▶  Railway
                                                     └─▶ Railway Redis (sessions)
Twilio ──webhooks──▶ Railway (PUBLIC_BASE_URL)
```

Files used: `Dockerfile`, `scripts/start-prod.sh`, `railway.json`, `.dockerignore`.

---

## Part A — Backend on Railway

**Prereqs:** a [Railway](https://railway.app) account and the CLI (`npm i -g @railway/cli`, then `railway login`). The Dockerfile pulls Continuum from its public GitHub repo, so you do **not** need to commit `continuum-src/`.

1. **Create the project + service**
   ```bash
   railway init                 # create a project
   ```
2. **Add Redis** (Railway dashboard → *New* → *Database* → *Redis*), or:
   ```bash
   railway add --database redis
   ```
3. **Deploy the backend** (Docker build runs on Railway; first build ~3-5 min):
   ```bash
   railway up                   # uploads this dir, builds the Dockerfile, deploys
   ```
   (Alternatively connect a GitHub repo for auto-deploys.)
4. **Generate a public domain**: service → *Settings* → *Networking* → *Generate Domain*. You'll get e.g. `https://fleetshield-api.up.railway.app`.
5. **Set environment variables** (service → *Variables*). Use Railway's reference syntax for Redis:

   | Variable | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | your key |
   | `DEFAULT_LLM_MODEL` | `claude-sonnet-4-5` |
   | `SESSION_ENABLED` | `true` |
   | `SESSION_REDIS_HOST` | `${{Redis.REDISHOST}}` |
   | `SESSION_REDIS_PORT` | `${{Redis.REDISPORT}}` |
   | `SESSION_REDIS_PASSWORD` | `${{Redis.REDISPASSWORD}}` |
   | `MEMORY_ENABLED` | `false` |
   | `LANGFUSE_ENABLED` | `false` |
   | `CONTEXT_MANAGEMENT_ENABLED` | `false` |
   | `ALLOWED_ORIGINS` | your Vercel URL (set after Part B), e.g. `https://fleetshield.vercel.app` |
   | `PUBLIC_BASE_URL` | this backend's own URL, e.g. `https://fleetshield-api.up.railway.app` |
   | `SMALLEST_API_KEY` | your key (voice — optional) |
   | `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_NUMBER` / `DISPATCHER_NUMBER` | for the dispatch call (optional) |
   | `TWILIO_VALIDATE_SIGNATURE` | `true` (now that the URL is stable) |

   Redeploy after setting variables. Verify: `curl https://<backend>/api/health` → `{"status":"ok",...}`.

---

## Part B — Frontend on Vercel

**Prereqs:** a [Vercel](https://vercel.com) account (+ `npm i -g vercel` for CLI).

1. **Import the repo** in Vercel and set **Root Directory = `frontend`** (Vercel auto-detects Next.js). Or via CLI from `frontend/`:
   ```bash
   cd frontend && vercel        # follow prompts; link/create the project
   ```
2. **Set environment variables** (Vercel → Project → Settings → Environment Variables), for Production:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<backend>.up.railway.app` |
   | `NEXT_PUBLIC_WS_URL` | `wss://<backend>.up.railway.app/ws` |

3. **Deploy:**
   ```bash
   vercel --prod
   ```
   You'll get e.g. `https://fleetshield.vercel.app`.

---

## Part C — Wire the two together

1. Put the **Vercel URL** into the backend's `ALLOWED_ORIGINS` (Railway) and redeploy.
2. Confirm `PUBLIC_BASE_URL` (Railway) = the backend's own URL so **Twilio** webhooks resolve (no ngrok needed anymore).
3. If your Twilio account is on **trial**, the dispatcher number must be a verified caller ID (see [SECURITY.md](SECURITY.md) / [README.md](README.md)).

## Part D — Verify

```bash
curl https://<backend>.up.railway.app/api/health         # {"status":"ok","provider":"AgentShyft Continuum",...}
curl https://<backend>.up.railway.app/api/fleet/overview # 25 vehicles / 30 drivers
```
Open the Vercel URL → `/operator/assistant` (chat + cards + voice), deploy a mission, and `/driver-portal` (login `405`/`7234`) → Call Dispatch.

---

## How it runs in one container
`scripts/start-prod.sh` launches the **MCP tool server on internal `:8765`** (the agent connects to it via `localhost`), waits for it to be ready, then runs **uvicorn on Railway's `$PORT`** (the public API). One service, one public port; Redis is a separate Railway service reached over private networking.

## Notes & alternatives
- **Image size/build:** Continuum's deps (pymilvus, grpcio, etc.) make the image ~1–2 GB and the first build a few minutes — fine on Railway (unlike Vercel's serverless size limits, which is why the backend isn't on Vercel).
- **Render / Fly.io** work the same way (same `Dockerfile`): Render via a Web Service + Redis add-on (`healthCheckPath: /api/health`); Fly via `fly launch` + Upstash Redis.
- **Upstash Redis** is an alternative managed Redis (set `SESSION_REDIS_HOST/PORT/PASSWORD` + `SESSION_REDIS_SSL=true`).
- **If `pip install git+https://github.com/shyftlabs/continuum.git` ever fails**, vendor the framework instead: un-ignore `continuum-src/` (remove its nested `.git`), `COPY continuum-src ./continuum-src`, and `pip install -e ./continuum-src` in the Dockerfile.
- **Cost:** Railway + Vercel both have free/hobby tiers sufficient for a demo; the always-on backend uses Railway usage credits.
