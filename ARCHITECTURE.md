# Architecture — FleetShield AI

A technical deep-dive into how FleetShield AI is built on **ShyftLabs Continuum**.
For the product story see [README.md](README.md); for security see [SECURITY.md](SECURITY.md).

## 1. System overview

Three processes (one command: `./scripts/dev.sh`):

| Process | Port | Role |
|---|---|---|
| Fleet MCP server (FastMCP) | 8765 | Exposes the 15 fleet tools the agent calls |
| FastAPI backend (+ Tasha) | 3000 | REST data API, the Continuum agent, missions, voice, telephony |
| Next.js frontend | 3001 | Operator + driver portals (proxies `/api` → :3000) |

Plus **Redis** (:6380) for Continuum session history.

The frontend was kept from the prior (proven) build; **the entire backend was rebuilt in Python on Continuum**, with a self-contained mock dataset replacing the original telematics provider.

## 2. Data layer (`backend/data/`)

- **`seed_data.py`** — a deterministic (seeded RNG) mock fleet: 25 vehicles, 30 drivers, and 90 days of safety events, daily trip summaries, and fleet KPIs. Dataclass fields are intentionally **camelCase** to match the frontend's `types/fleet.ts` contract, so `asdict()` serializes directly.
  - The "before" window (days 46–90) is deliberately worse than the "after" window (days 1–45), so the ROI before/after comparison shows a real improvement and the headline savings land on the proven figure (~$523K).
- **`driver_session.py`** — in-memory driver-portal state (loads, messages, HOS, action items, wellness check-ins) + the `add_driver_action_item` hook missions use to push tasks to drivers.
- **`live_fleet.py`** — deterministic GPS-trail / hotspot simulation for the live map.

## 3. Scoring engines (`backend/scoring/`)

Nine **pure functions** — no side effects, no I/O — each reading the mock dataset and returning plain dicts/lists with camelCase keys. They are the single source of truth, consumed by the MCP tools, the REST routes, **and** the mission runner.

`driver_risk` · `insurance_score` · `wellness_predictor` · `predictive_safety` · `roi_engine` · `alert_triage` · `green_score` · `gamification` · `what_if`.

Design rule: invalid input returns `None` (never raises); signatures are stable because three layers depend on them.

## 4. Tools (`backend/mcp_server/fleet_tools.py`)

A single **FastMCP** server exposes 15 tools (`@mcp.tool`). Tool **names are camelCase and chosen to match the frontend's `ComponentRenderer`** (`getFleetOverview`, `getDriverRiskScore`, `getFleetInsuranceScore`, `getDriverWellness`, `getFinancialImpact`, `getFleetForecast`, `getAlertBriefing`, `getCoachingRecommendations`, `getPreShiftRisk`, `getFleetComparison`, `getGreenFleetMetrics`, `getFleetTrends`, `getSafetyEvents`, `deployMission`, `callDispatch`) — so each tool result renders as its rich card with zero frontend changes.

The server runs standalone (`python -m backend.mcp_server.fleet_tools`); the agent connects over `MCPServerStreamableHttp`.

## 5. The agent — Tasha (`backend/agent/`)

- **`prompts.py`** — Tasha's system prompt (role detection, brevity rules, the `<voice>…</voice>` voice-first format, the mission-offer playbook, deep domain knowledge).
- **`tasha.py`** — `TashaAgent`:
  - **Per-request MCP session.** A fresh `MCPServerStreamableHttp` connection + `ToolExecutor` + `BaseAgent` + `AgentRunner` is built per request. A *persistent* MCP connection raises `ClosedResourceError` on the 2nd request, so we connect-and-clean-up around each turn.
  - **`CapturingToolExecutor`** — Continuum's stream only carries a truncated string in `TOOL_CALL_END`, so we override `_on_tool_result` and JSON-parse the tool's full content string. That payload feeds the rich cards.
  - **`_VoiceSplitter`** — buffers `CONTENT_DELTA` tokens and separates the spoken `<voice>` block (emitted once as `voice_summary` for TTS) from the visible markdown — so the spoken summary never flashes on screen.
  - **Sessions** — `_ensure_session()` calls `get_or_create_session(session_id=conversationId)`; the runner then loads + persists conversation history in Redis automatically. A history-fold fallback covers the no-Redis case.

### Assistant SSE contract (what the frontend consumes)

`POST /api/assistant/stream` emits Server-Sent Events:

```
data: {"type":"voice_summary","content": "...spoken..."}
data: {"type":"tool_result","toolName":"getDriverRiskScore","result":{...}}   # → rich card
data: {"type":"text","content":"...markdown delta..."}
data: {"type":"mission_progress|mission_finding|mission_complete", ...}        # if a mission is deployed
data: {"type":"done"}
```

## 6. Missions (`backend/missions/`)

Five autonomous "AI employees": `coaching_sweep`, `wellness_check`, `safety_investigation`, `insurance_optimization`, `preshift_sweep`.

- **`runner.py`** — each mission is an **async generator** that yields `mission_progress` / `mission_finding` events (with a small delay so the operator watches it work), gathers data deterministically from the scoring engines, then writes an executive **summary via a Continuum LLM call** (graceful deterministic fallback if no key). Completed coaching/wellness/safety missions **sync action items to the affected drivers' portals**.
- **`store.py`** — in-memory mission registry powering `/api/missions/active`, `/api/missions/{id}`, and the driver `/training` feed.

**Deploy flow (cross-process):** the agent calls the `deployMission` tool, which (in the MCP process) returns only a lightweight *intent* `{missionId, type}`. The SSE handler (in the FastAPI process) detects that capture, runs `run_mission()` **in-process**, and forwards its events into the same stream. This avoids needing shared state across the MCP and API processes.

## 7. Voice (`backend/voice/`)

- **`tts.py`** — Smallest AI Waves; returns raw PCM wrapped in a WAV header (browser-decodable). `POST /api/tts/synthesize`.
- **`stt.py`** — Smallest AI Pulse, one WebSocket per utterance.
- **`session.py`** — the `/ws` WebSocket: receives PCM frames + `speech_start/end`, runs STT → Tasha → TTS, streams `state_change` / `transcript` / `tool_result` / `audio_chunk` back, and shares the same Continuum session for multi-turn voice.

## 8. Telephony — the real dispatch call (`backend/voice/twilio_dispatch.py`)

For reliability over raw Media Streams, the two-way call uses Twilio's built-in speech **`<Gather>` + `<Say>`** with a Continuum "driver-advocate" LLM persona:

1. Driver taps "Call Dispatch" → `POST /api/driver/{id}/dispatch-call` → `start_call()` places a real outbound Twilio call to the dispatcher.
2. Twilio fetches `POST /twilio/voice` → the agent's opening line (the driver's request) + `<Gather speech>`.
3. Dispatcher speaks → Twilio STT → `POST /twilio/gather` → the agent's next line, looping until resolved (`[END_CALL]`) or `MAX_TURNS`.
4. The live transcript is polled by the driver UI via `/dispatch-call/{callId}/status`.

Requires `PUBLIC_BASE_URL` (ngrok) so Twilio can reach the callbacks. Signature validation is available (gated by `TWILIO_VALIDATE_SIGNATURE`).

## 9. REST API (`backend/api/`)

- **`server.py`** — the FastAPI app: ~35 fleet/operator data routes (thin wrappers over the scoring engines), the mission routes, restricted CORS, and the `/ws` + `/twilio/*` endpoints. Includes the three routers.
- **`assistant_routes.py`** — `/api/assistant/stream`, `/api/chat/stream`, `/api/chat`.
- **`driver_routes.py`** — the 22 `/api/driver/*` routes.
- **`voice_routes.py`** — `/api/tts/synthesize`.

## 10. Key design decisions / gotchas

| Decision | Why |
|---|---|
| Model string `claude-sonnet-4-5` (dashes) | the dotted form is only Continuum's context-window key; the API 404s on it |
| `CONTEXT_MANAGEMENT_ENABLED=false` | the dashed model misses the context map → defaults to ~3072 tokens → truncates tool results mid-call. Claude has 200K; sessions bound history |
| Per-request MCP connection | a persistent StreamableHTTP session raises `ClosedResourceError` on the 2nd request |
| Tool results via `_on_tool_result` (JSON-parse) | MCP `structured_content` is None; the content string holds the full payload |
| Tool names == ComponentRenderer keys | renders the existing rich cards unchanged |
| `deployMission` returns an intent; SSE runs the mission | the MCP tool process can't stream into the API process's response |
| camelCase dataclass fields + dict returns | match the frontend contract; `asdict()` serializes directly |

## 11. Testing

`pytest` — 92 tests across `backend/tests/`: data invariants, all 9 engines (parametrized over every driver), all REST routes (+ 404/401/edge cases), and all 5 missions end-to-end. `ruff` is clean (config in `ruff.toml`).
