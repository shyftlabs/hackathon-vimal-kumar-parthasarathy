# CLAUDE.md — FleetShield AI (AgentShyft / Continuum) Development Guide

## !!! READ FIRST !!!
This project is for the **AgentShyft Hackathon** by ShyftLabs. Full rules, schedule,
judging, prizes, our pitch, and the demo flow are in **`COMPETITION.md`** — read it.
**Goal: win 1st place** by building FleetShield AI genuinely on the **Continuum** agent framework.

## Project Overview
FleetShield AI is an intelligent fleet-operations platform: real-time-style telematics →
AI analytics, an autonomous **AI workforce** (mission agents), dual voice/chat assistants,
and a **real outbound dispatch phone call**. It rebuilds a prior Geotab-hackathon winner on
**Continuum + self-contained mock data** (no Geotab).

## Architecture
```
Browser
  ├─ Next.js frontend (KEPT from the original, rebranded)         :3001
  │     REST + SSE + WebSocket  (frontend/src/lib/api.ts contract)
  ▼
FastAPI backend (Python 3.13)                                      :3000
  ├─ Tasha   = Continuum BaseAgent ──run_stream──► SSE (text + voice_summary + tool_result)
  ├─ Missions = in-process runner streamed into the same SSE (deploy via Tasha)
  ├─ Driver portal routes + voice (P6) + Twilio (P7)
  └─ calls ▼
Fleet MCP server (FastMCP)  — 14 @mcp.tool() over the scoring engines :8765
```
- **Continuum** is vendored at `continuum-src/` (installed editable; importable as `orchestrator`). See [reference] in memory + `continuum-src/playground/` for examples.
- **Reference** (TS original) is at `existing-solution/` — read-only source of truth for shapes/behavior.

## Repo Layout
```
backend/
  data/seed_data.py        # mock fleet: 25 vehicles, 30 drivers, 90d events/trips/KPIs (seeded RNG)
  data/driver_session.py   # driver portal state (loads, messages, HOS, action items)
  data/live_fleet.py       # map GPS simulation
  scoring/                 # 9 pure-function engines (driver_risk, insurance_score, wellness_predictor,
                           #   predictive_safety, roi_engine, alert_triage, green_score, gamification, what_if)
  mcp_server/fleet_tools.py# FastMCP server: 14 tools (names MATCH the frontend ComponentRenderer)
  agent/prompts.py         # Tasha system prompt (de-Geotabbed)
  agent/tasha.py           # Tasha agent + per-request MCP session + SSE adapter
  missions/store.py        # mission registry (active/completed; /api/missions + driver /training)
  missions/runner.py       # 5 missions as async-generator pipelines + Continuum LLM summary
  api/server.py            # FastAPI app: ~35 fleet routes + includes assistant & driver routers
  api/assistant_routes.py  # /api/assistant/stream, /api/chat[/stream]
  api/driver_routes.py     # 22 /api/driver/* routes
frontend/                  # Next.js 16 + React 19 (kept; rebranded Geotab→AgentShyft Continuum)
scripts/dev.sh             # start MCP + backend + frontend
.env                       # secrets + config (gitignored)
```

## Running
```bash
# one-shot (all three services):
./scripts/dev.sh

# or manually (ALWAYS from repo root, ALWAYS PYTHONPATH=repo root):
PYTHONPATH=. .venv/bin/python -m backend.mcp_server.fleet_tools                 # :8765
PYTHONPATH=. .venv/bin/python -m uvicorn backend.api.server:app --port 3000     # :3000
cd frontend && npm run dev                                                      # :3001 (pinned via -p 3001)
```
- Backend deps: `.venv` (Python 3.13) with `pip install -e ./continuum-src` + fastapi/uvicorn/httpx/twilio/sse-starlette.
- Open **http://localhost:3001** (landing), `/operator` (manager portal), `/driver-portal` (driver; login `405`/`7234` = Marcus Rivera, the high-risk demo driver).

## !!! HARD-WON GOTCHAS — do not regress these !!!
1. **Claude model string is `claude-sonnet-4-5` (DASHES).** The dotted `claude-sonnet-4.5` only exists in Continuum's context-window map; the Anthropic API 404s on it. Set `DEFAULT_LLM_MODEL=claude-sonnet-4-5`.
2. **`CONTEXT_MANAGEMENT_ENABLED=false`.** Because our model string isn't in Continuum's context map, the window defaults to ~3072 tokens and truncates tool results mid-call (corrupting tool_use/tool_result pairing → API error). Disabling compression fixes it (Claude has 200K; turns are short).
3. **MCP session is PER-REQUEST.** A persistent StreamableHTTP MCP connection raises `ClosedResourceError` on the 2nd request. `TashaAgent` connects + cleans up around each turn. Don't make it persistent.
4. **Tool results come from `_on_tool_result(tool_name, result, artifact)`** — MCP `structured_content` is None, so we JSON-parse the `result` string. That payload feeds the frontend rich cards.
5. **MCP tool NAMES must match `frontend/src/components/assistant/ComponentRenderer.tsx`** (getFleetOverview, getDriverRiskScore, getFleetInsuranceScore, getDriverWellness, getFinancialImpact, getFleetForecast, getAlertBriefing, getCoachingRecommendations, getPreShiftRisk, getFleetComparison, deployMission). Renaming a tool silently drops its rich card to a generic fallback.
6. **Lean infra:** `MEMORY_ENABLED=false`, `SESSION_ENABLED=false`, `LANGFUSE_ENABLED=false` → no Docker/Redis/Milvus/OpenAI needed. (mem0's embedder otherwise forces an OPENAI_API_KEY at startup.)

## Conventions
- **Scoring engines** are pure functions returning **dicts/lists with camelCase keys** (matching `frontend/src/types/fleet.ts`). No side effects; return `None` on invalid input. They are imported by the MCP tools, REST routes, AND the mission runner — don't change their signatures casually.
- **The assistant SSE contract** (consumed by `frontend/src/app/operator/assistant/page.tsx`): `{type:"text"|"voice_summary"|"tool_result"|"mission_progress"|"mission_finding"|"mission_complete"|"done"}`. Keep it exact.
- **Missions** stream into the SAME assistant SSE: the agent calls `deployMission` (returns a `{missionId,type}` intent); the SSE handler runs `missions.runner.run_mission(...)` in-process and forwards its events. `deployMission` MUST run in the FastAPI process side (the in-process runner owns the live event stream), so the MCP tool only returns the intent.
- **Don't break working features.** Verify after changes: backend imports (`python -c "import backend.api.server"`), a live Tasha turn (curl `/api/assistant/stream`), and a mission deploy.

## Phase Status
- ✅ P0 setup · P1 data+9 engines · P2 MCP tools + ~35 REST routes · P3 Tasha (live) · P4 missions (live) · P5 driver portal + rebrand · P6 voice (TTS live; hands-free `/ws` wired) · P7 real two-way Twilio call (logic verified; needs `PUBLIC_BASE_URL`/ngrok + a live test) · P9 numbers calibrated to ~$523K + `DEMO_SCRIPT.md`.
- ⏳ P8 Continuum observability/memory — OPTIONAL, off by default (see below).

## Continuum upgrades (optional — for the "depth" story)
These are native Continuum features, intentionally OFF for the zero-infra demo. To show them:
- **Memory** (Tasha remembers per-user facts): `docker compose up -d` in `continuum-src/` (Redis :6380 + vector store), set `MEMORY_ENABLED=true` and `SESSION_ENABLED=true` in `.env`. mem0's default embedder needs an `OPENAI_API_KEY`; to avoid that, set `EMBEDDER_PROVIDER=huggingface` (local, `pip install sentence-transformers`). The agent is already memory-gated (`MEMORY_ON` in `tasha.py`), so it activates automatically.
- **Observability** (Langfuse trace of every LLM/tool/memory call — great to show judges): set `LANGFUSE_ENABLED=true` + `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` (Langfuse Cloud free tier, or self-host via `continuum-src` docker compose).
- **Multi-model routing/fallback**: set `LLM_ENABLE_FALLBACK=true` + a `FALLBACK_LLM_MODEL`. All one-flag changes — the point for the pitch: we built a *product on Continuum*, not a framework.

## LLM Provider Notes
Continuum routes to the provider by model-string prefix (it's a router, not a model gate). You're limited to what **your Anthropic key** can call. Confirmed on this key: `claude-sonnet-4-5` (Tasha) and `claude-opus-4-5` work; `claude-opus-4-7`/`4-8` do **not** (4.8 doesn't exist; the latest Opus is 4.7, not available to this key). Use Sonnet 4.5 for the interactive agent (fast); Opus 4.5 is an option for mission summaries (deeper, slower).
