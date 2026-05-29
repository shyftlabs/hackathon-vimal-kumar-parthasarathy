<div align="center">

# 🛡️ FleetShield AI

### The intelligence layer that turns raw fleet telematics into **money saved, lives protected, and a planet preserved.**

**Two AI assistants · Autonomous mission agents · A real phone call to dispatch — all built on [ShyftLabs Continuum](https://continuum.shyftlabs.io).**

`Python 3.13` · `Continuum agent runtime` · `Claude Sonnet 4.5` · `Next.js 16 / React 19` · `92 tests passing` · `ruff clean`

</div>

> ### 🔗 Live demo — **[fleetshield-ai.vercel.app](https://fleetshield-ai.vercel.app)**
> **Operator portal** (`/operator`) is open, no login. **Driver portal** (`/driver-portal`) logs in with **Employee # `405` · PIN `7234`** (Marcus Rivera).

---

## The Problem

Commercial trucking moves **$940B** of freight a year — and bleeds money to a crisis hiding in plain sight:

| | |
|---|---|
| 🚛 **500,000+** large-truck crashes/year (FMCSA) | at an average of **$91,000** per incident |
| 📈 Insurers can't see behavioral improvement | so fleets **overpay 18–32%** on premiums |
| 🔁 **87%** annual driver turnover (ATA) | each replacement costs **$35,000+** |
| 💔 Driver life expectancy **61 years** | 16 below the national average; 25% report chronic loneliness |
| 🌍 **444M metric tons CO₂/year** from trucking | with billions in avoidable fuel waste |

The data to prevent all of this **already exists** inside the telematics devices in millions of vehicles. But fleet managers are drowning in raw signals with no way to turn them into decisions, dollars, or impact.

## The Solution

**FleetShield AI** is an agentic intelligence layer that turns telematics into the three things a fleet actually needs:

1. **💰 Money saved** — quantified insurance reductions, accident-prevention, and fuel savings in *exact dollars*. Not "reduce speeding" but "coaching your top 5 drivers saves **$157K/year**."
2. **🦺 Lives protected** — predictive safety that flags at-risk drivers and dangerous corridors *before* incidents, plus proactive wellness + Hours-of-Service monitoring.
3. **🌱 Planet preserved** — driving behavior mapped to CO₂, EV-transition readiness, and decarbonization actions.

It does this not as a dashboard, but as an **AI workforce**:

- **Tasha** — a Continuum agent (operator + driver) who answers any fleet question with rich visual cards *and* a spoken voice summary, and who you talk to hands-free.
- **Autonomous Mission Agents** — give an assignment ("run a coaching sweep on my riskiest drivers"); the agent executes a multi-step analysis across the whole fleet and streams back a findings report with dollar impact — an analyst's afternoon in 30 seconds.
- **A real phone call to dispatch** — when a driver needs dispatch, Tasha places a **real outbound Twilio call** to a human dispatcher, converses on the driver's behalf, and relays the outcome — no screen, no texting-and-driving.

## What Makes It Unique

- **An agentic *workforce*, not a chatbot.** Continuum's multi-step mission agents do real analyst work autonomously and report back — the literal theme of the hackathon, executed end-to-end.
- **It closes the loop into the physical world.** Most "AI agents" stop at text. FleetShield's agent **picks up the phone and has a real conversation** with a human dispatcher.
- **Two surfaces, one brain.** The same Continuum agent serves a manager's analytics portal *and* a driver's voice-first cab tablet.
- **Every insight is in dollars.** Safety, wellness, and sustainability are all translated into the language executives and underwriters fund.

## Impact — by the numbers

These figures are **computed live** by the platform's engines over a realistic, deterministic mock fleet (25 vehicles, 30 drivers, 90 days of telematics) and surface in the UI + Tasha's answers:

| Metric | Value |
|---|---|
| Potential annual fleet savings | **$523,470** |
| CO₂ reduction (sustainability recommendations) | **936 tons/year** |
| Insurance premium reduction potential | **18–32%** |
| ROI / payback | **~2,000%** · **<1 month** |
| Analyst work replaced by mission agents | **15–20 hrs/week** |
| Drivers coached by AI, not surveilled | **30** |

## Built on Continuum (how the framework is used)

FleetShield is a **product built on Continuum**, not a framework wrapper:

| Capability | Continuum primitive |
|---|---|
| Tasha (the assistant) | `BaseAgent` + `AgentRunner.run_stream()` → SSE |
| 14 fleet tools | one **FastMCP** server, discovered over `MCPServerStreamableHttp` |
| Rich cards + spoken summary | streamed `TOOL_CALL`/`CONTENT_DELTA` events adapted to the frontend contract |
| Multi-turn memory | **Redis-backed sessions** (`session_id`) — history loaded/saved automatically |
| Autonomous missions | multi-step agent pipelines streaming `mission_progress`/`finding`/`complete` |
| Dispatcher conversation | a second Continuum LLM persona driving a live phone call |
| Model routing | provider-prefix routing (Claude Sonnet 4.5) with graceful fallback |

> **📘 Full, file-referenced breakdown of every Continuum primitive we use → [CONTINUUM.md](CONTINUUM.md).** Observability (Langfuse) and long-term memory (mem0) are native Continuum features wired one-flag-away.

## Architecture

```
                          ┌───────────────────────────── Browser ─────────────────────────────┐
                          │  Next.js 16 / React 19  ·  Operator portal + Driver cab portal      │
                          └───────────────┬───────────────────────────────┬────────────────────┘
                         REST + SSE (/api)│                        WebSocket│ (/ws voice)   ☎ Twilio (real call)
                          ┌───────────────▼───────────────────────────────▼────────────────────┐
                          │                 FastAPI backend (Python 3.13)                        │
                          │                                                                      │
                          │   Tasha = Continuum BaseAgent ──run_stream──▶ SSE (text+voice+cards) │
                          │   Sessions (Redis) ─ native multi-turn conversation history          │
                          │   Missions = async agent pipelines ─ streamed into the same channel  │
                          │   Voice = Smallest AI STT (Pulse) + TTS (Waves)                       │
                          │   Dispatch = Twilio <Gather>/<Say> driven by a Continuum agent        │
                          └───────────────┬──────────────────────────────────────────────────────┘
                            MCP (StreamableHTTP)│
                          ┌───────────────▼──────────────────────────────────────────────────────┐
                          │  Fleet MCP server (FastMCP) — 14 tools over 9 pure scoring engines     │
                          │  risk · insurance · wellness · predictive · ROI · alerts · green ·      │
                          │  gamification · what-if   ◀──  deterministic mock telematics dataset    │
                          └───────────────────────────────────────────────────────────────────────┘
```

**Tech stack:** Python 3.13 · ShyftLabs Continuum · Anthropic Claude Sonnet 4.5 · FastAPI · FastMCP · Redis · Next.js 16 / React 19 / Tailwind · Smallest AI (voice) · Twilio (telephony).

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full technical deep-dive.

## Quickstart

**Prerequisites:** Python 3.13, Node 20+, Redis (`brew install redis`), and an Anthropic API key. (Smallest AI + Twilio keys optional — for voice + the phone call.)

```bash
# 1. Backend deps (Continuum is vendored in ./continuum-src)
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ./continuum-src
pip install fastapi "uvicorn[standard]" httpx twilio python-multipart sse-starlette audioop-lts websockets

# 2. Frontend deps
( cd frontend && npm install )

# 3. Configure secrets
cp .env.example .env   # then add ANTHROPIC_API_KEY (+ SMALLEST/TWILIO if using voice/calls)

# 4. Run everything (Redis + MCP :8765 + API :3000 + frontend :3001)
./scripts/dev.sh
```

Open **http://localhost:3001** (or the **[live demo](https://fleetshield-ai.vercel.app)**):

| Surface | Path | Login |
|---|---|---|
| Operator dashboard | `/operator` | — *(no login)* |
| Tasha assistant | `/operator/assistant` | — *(no login)* |
| Driver portal | `/driver-portal` | **Employee # `405` · PIN `7234`** → Marcus Rivera |

**Driver Portal credentials — Employee Number `405`, PIN `7234`** (Marcus Rivera, the fleet's highest-risk driver — the richest portal data for a demo). All 30 seeded drivers have unique credentials; a few others to try different profiles:

| Employee # | PIN | Driver |
|---|---|---|
| **`405`** | **`7234`** | **Marcus Rivera** — *recommended demo login* |
| `241` | `1847` | James Wilson |
| `318` | `2956` | Sarah Chen |
| `127` | `4081` | Emily Davis |
| `562` | `3619` | Robert Kim |

To enable the real dispatch call: `ngrok http 3000`, set `PUBLIC_BASE_URL` in `.env`, restart, then tap "Call Dispatch."

## Demo

A verbatim, scene-by-scene **3-minute presentation script** (with setup checklist and graceful fallbacks) is in **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)**.

## Testing

```bash
pytest          # 92 tests: data invariants, all 9 engines (every driver), all routes, all 5 missions
ruff check backend/
```

## Scaling & productionization

FleetShield is a faithful prototype with a clear path to production:

- **Real telematics** — swap the mock dataset for a live feed (Geotab/Samsara/Motive). The scoring engines, MCP tools, and agent are **provider-agnostic** and unchanged.
- **Multi-tenant** — per-fleet data isolation; Continuum memory/session scopes (`USER`/`AGENT`) already support tenancy.
- **Scale-out** — FastAPI on Fluid Compute; Redis + a managed vector store (Qdrant/Milvus) for memory; the MCP tool server scales independently.
- **Observability at scale** — flip on Continuum's native Langfuse tracing for full causal traces of every agent decision.
- **Hardening** — see the roadmap in **[SECURITY.md](SECURITY.md)** (auth, rate limiting, TLS, Twilio signature validation, output sanitization).

## Repository structure

```
backend/        Python + Continuum backend
  data/         deterministic mock fleet + driver-session state + live-map sim
  scoring/      9 pure-function scoring engines (camelCase dict contracts)
  mcp_server/   FastMCP server — 14 fleet tools
  agent/        Tasha (BaseAgent) + prompts + SSE adapter + sessions
  missions/     5 autonomous mission pipelines + store
  voice/        Smallest AI STT/TTS + Twilio two-way dispatch call
  api/          FastAPI app + assistant/driver/voice routers
  tests/        pytest suite (92 tests)
frontend/       Next.js operator + driver portals (kept, rebranded)
continuum-src/  vendored ShyftLabs Continuum framework (pip install -e)
scripts/dev.sh  one-command local startup
```

## Documentation

| Doc | What |
|---|---|
| **[CONTINUUM.md](CONTINUUM.md)** | **Exactly which Continuum primitives we use, where, and why (file-referenced)** |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical deep-dive + request flows |
| [COMPETITION.md](COMPETITION.md) | Hackathon rules, judging, our pitch, why we win |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | The 3-minute live demo script |
| [SECURITY.md](SECURITY.md) | Security posture + production roadmap |
| [CLAUDE.md](CLAUDE.md) | Engineering guide + gotchas for contributors/agents |

---

<div align="center">
Built for the <b>AgentShyft Hackathon</b> by ShyftLabs · Toronto, May 2026 · on the <b>Continuum</b> agent runtime.
</div>
