# CLAUDE.md — FleetShield AI Engineering Guide

Engineering guide for contributors and AI agents working in this repo. For the
product story read **[README.md](README.md)**; for how we use the framework read
**[CONTINUUM.md](CONTINUUM.md)**; for the system design read **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## Documentation map
| Doc | Purpose |
|---|---|
| [README.md](README.md) | Problem · solution · uniqueness · impact · quickstart |
| [CONTINUUM.md](CONTINUUM.md) | **Exactly which Continuum primitives we use, where, and why** |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full technical design + request flows |
| [SECURITY.md](SECURITY.md) | Security posture + production roadmap |
| [COMPETITION.md](COMPETITION.md) | Hackathon rules, judging, pitch |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 3-minute live demo script |

## Project overview
FleetShield AI is an agentic fleet-safety platform: telematics → AI analytics, an
autonomous **AI workforce** (mission agents), dual voice/chat assistants, and a
**real two-way dispatch phone call** — all on the **ShyftLabs Continuum** agent
runtime, over a self-contained mock telematics dataset (no external provider).

## Architecture
```
Browser ── Next.js operator + driver portals                         :3001
   │  REST + SSE + WebSocket  (frontend/src/lib/api.ts contract)
   ▼
FastAPI backend (Python 3.13)                                        :3000
   ├─ Tasha   = Continuum BaseAgent ──run_stream──► SSE (text + voice + tool cards)
   ├─ Sessions (Redis) ── native multi-turn conversation history
   ├─ Missions = async pipelines streamed into the same channel (deployed by Tasha)
   ├─ Voice  = Smallest AI STT (Pulse) + TTS (Waves) over /ws
   └─ Dispatch = real Twilio <Gather>/<Say> call driven by a Continuum LLM persona
   │  calls ▼ (MCP / StreamableHTTP)
Fleet MCP server (FastMCP) — 15 tools over 9 scoring engines          :8765
Redis — Continuum session store                                      :6380
```
- **Continuum** is vendored at `continuum-src/` (install editable; imported as `orchestrator`). Examples in `continuum-src/playground/`.
- **`existing-solution/`** is the TS original — read-only reference for shapes/behavior. Both are git-ignored.

## Repo layout
```
backend/
  data/seed_data.py        # deterministic mock fleet (25 vehicles, 30 drivers, 90d telematics)
  data/driver_session.py   # driver-portal state (loads, messages, HOS, action items)
  data/live_fleet.py       # live-map GPS simulation
  scoring/                 # 9 pure-function engines (camelCase dict contracts)
  mcp_server/fleet_tools.py# FastMCP server — 15 tools (names MATCH the frontend renderer)
  agent/{prompts,tasha}.py # Tasha BaseAgent, per-request MCP session, SSE adapter, Continuum sessions
  missions/{store,runner}.py# 5 autonomous mission pipelines + registry
  voice/{stt,tts,session,twilio_dispatch}.py  # Smallest AI STT/TTS, /ws handler, real Twilio call
  api/{server,assistant_routes,driver_routes,voice_routes}.py  # FastAPI app + routers + /ws + /twilio/*
  tests/                   # pytest suite (92 tests)
frontend/                  # Next.js 16 / React 19 (kept; rebranded to AgentShyft Continuum)
scripts/{dev.sh,twilio-up.sh}   # local startup + ngrok/Twilio helper
.env(.example)             # config + secrets (.env git-ignored)
pytest.ini · ruff.toml     # test + lint config
```

## Running
```bash
./scripts/dev.sh          # starts Redis(:6380) + MCP(:8765) + backend(:3000) + frontend(:3001)
```
Manual (always from repo root, `PYTHONPATH=.`):
```bash
redis-server --port 6380 --daemonize yes
PYTHONPATH=. .venv/bin/python -m backend.mcp_server.fleet_tools
PYTHONPATH=. .venv/bin/python -m uvicorn backend.api.server:app --port 3000
( cd frontend && npm run dev )            # pinned to :3001
```
Open **http://localhost:3001** → `/operator` · `/driver-portal` (login `405`/`7234` = Marcus Rivera).
Setup + deps: see [README.md](README.md#quickstart). Real phone call: `./scripts/twilio-up.sh` (ngrok) + see [README.md] / [SECURITY.md].

## Testing & quality
```bash
pytest                    # 92 tests: data, all 9 engines (every driver), all routes, all 5 missions
ruff check backend/       # clean (config in ruff.toml)
```

## !!! HARD-WON GOTCHAS — do not regress these !!!
1. **Claude model string is `claude-sonnet-4-5` (DASHES).** The dotted `claude-sonnet-4.5` only exists in Continuum's context-window map; the Anthropic API 404s on it.
2. **`CONTEXT_MANAGEMENT_ENABLED=false`.** The dashed model misses Continuum's context map → window defaults to ~3072 tokens → truncates tool results mid-call (corrupts tool_use/tool_result pairing → API error). Sessions bound history instead; Claude has 200K.
3. **MCP session is PER-REQUEST.** A persistent StreamableHTTP connection raises `ClosedResourceError` on the 2nd request. `TashaAgent` connects + cleans up around each turn.
4. **Tool results via `_on_tool_result(tool_name, result, artifact)`** — MCP `structured_content` is None, so we JSON-parse the `result` string; that payload feeds the rich cards.
5. **MCP tool NAMES must match `frontend/.../ComponentRenderer.tsx`** (getFleetOverview, getDriverRiskScore, …, deployMission), or the rich card silently degrades to a generic fallback.
6. **Sessions need an explicit `get_or_create_session(session_id=…, user_id=…)` BEFORE the run** — passing a raw `session_id` the runner hasn't created raises *"Session not found"*. NB: that method takes `session_id`/`user_id`/`conversation_id` — **no `agent_id`**.
7. **Lean infra:** `SESSION_ENABLED=true` (Redis only). `MEMORY_ENABLED=false`, `LANGFUSE_ENABLED=false` → no Docker / vector store / OpenAI needed (mem0's embedder would otherwise force an `OPENAI_API_KEY` at startup).
8. **Ports:** backend 3000, frontend 3001 (pinned `-p 3001`), MCP 8765, Redis 6380. The Next.js "multiple lockfiles / middleware→proxy" warnings are cosmetic.

## Conventions
- **Scoring engines** are pure functions returning **camelCase dicts** (matching `frontend/src/types/fleet.ts`); no side effects; `None` on invalid input. Imported by tools, routes, AND missions — don't change signatures casually.
- **Assistant SSE contract** (consumed by `operator/assistant/page.tsx`): `{type: "text"|"voice_summary"|"tool_result"|"mission_progress"|"mission_finding"|"mission_complete"|"done"}`. Keep exact.
- **Missions** stream into the same assistant SSE: the agent calls `deployMission` (returns a `{missionId,type}` intent); the FastAPI-side SSE handler runs `missions.runner.run_mission(...)` in-process and forwards events (the MCP-process tool can't stream into the API-process response).
- **Multi-turn** uses Continuum Redis sessions keyed by the frontend's `conversationId`; a context-fold fallback covers a no-Redis environment.
- **Don't break working features.** After changes verify: `python -c "import backend.api.server"`, `pytest`, a live Tasha turn, and a mission deploy.

## Continuum: used vs. available
We use BaseAgent, AgentRunner (`run_stream`/`run`), FastMCP tools + `MCPServerStreamableHttp` + `ToolExecutor`, `EventType` streaming, **Redis sessions**, the DI container + LLM client, and provider routing — see **[CONTINUUM.md](CONTINUUM.md)** for the file-referenced breakdown.

**One-flag upgrades (off by default, documented):** mem0 long-term memory (needs a vector store), Langfuse observability, native workflow agents (`SequentialAgent`/`PlannerAgent`), Temporal durable workflows, Smart Gateway routing.
