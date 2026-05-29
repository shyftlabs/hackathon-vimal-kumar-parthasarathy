<div align="center">

# 🛡️ FleetShield AI

### An autonomous **AI workforce** for fleet safety — built end-to-end on [ShyftLabs Continuum](https://continuum.shyftlabs.io)

> **AgentShyft Hackathon 2026** (ShyftLabs · Toronto) — *build with agentic AI, not talk about it.*
> Powered by the **Continuum** agent runtime · **Claude Sonnet 4.5** · real-time voice AI · a **real two-way dispatch phone call**.

`Python 3.13` · `Continuum agent runtime` · `15 MCP tools` · `9 scoring engines` · `5 autonomous missions` · `Next.js 16 / React 19` · `92 tests passing` · `ruff clean`

</div>

> ### 🔗 Live demo — **[fleetshield-ai.vercel.app](https://fleetshield-ai.vercel.app)**
> **Operator portal** (`/operator`) is open — no login. **Driver portal** (`/driver-portal`) logs in with **Employee # `405` · PIN `7234`** (Marcus Rivera, the fleet's highest-risk driver — the richest data for a demo).

---

## The Problem We're Solving

Commercial trucking moves **$940 billion** of freight a year — and bleeds money to a crisis hiding in plain sight. The telematics data to prevent all of it **already exists** in the devices installed in millions of vehicles. But fleet managers are drowning in raw signals with no time to turn them into decisions, dollars, or impact.

| Pain Point | Scale | Cost |
|---|---|---|
| **Preventable accidents** | 500,000+ large-truck crashes/year (FMCSA) | ~$91,000 average per incident |
| **Insurance overcharges** | Underwriters can't see behavioral improvement | fleets overpay **18–32%** on premiums |
| **Driver turnover** | **87%** annual rate (ATA) | $35,000+ per replacement |
| **Driver health crisis** | Life expectancy ~61 years (16 below average) | 25% report chronic loneliness |
| **Carbon emissions** | 444M metric tons CO₂/year from trucking | billions in avoidable fuel waste |

A fleet manager doesn't need *more* data. They need **someone to look at it, decide what to do, and do it.** That someone has never existed — until now.

---

## The Solution

**FleetShield AI** is an agentic intelligence layer that turns telematics into the three things a fleet actually needs — **money saved, lives protected, a planet preserved** — and it does this not as a dashboard, but as an **AI workforce** that *acts*:

1. **It answers.** **Tasha** is a Continuum agent wired into the live fleet via 15 tools. Ask "who's our riskiest driver and what's it costing us?" and she chooses the right tools, pulls the real numbers, and replies with rich visual cards **and** a spoken voice summary.
2. **It acts.** Give an assignment — *"run a coaching sweep"* — and an **autonomous mission agent** executes a multi-step analysis across the whole fleet, streams its findings live, writes an executive report, and pushes coaching tasks to drivers' phones. An analyst's afternoon in 30 seconds.
3. **It reaches the driver.** When a driver needs dispatch, Tasha places a **real outbound phone call** to a human dispatcher, conducts a live two-way conversation on the driver's behalf, and relays the outcome back — no texting and driving.

---

## What Makes FleetShield AI Different

### 1. An agentic *workforce*, not a chatbot
Traditional fleet AI answers questions. FleetShield's **Mission Agents** do work. Say *"run a wellness check across my fleet"* — an autonomous Continuum pipeline analyzes every driver's telematics through 9 scoring engines and delivers a report with findings, root causes, dollar impact, and an action plan. The operator keeps working; the agent does the analyst's job in seconds.

### 2. It closes the loop into the physical world
Most "AI agents" stop at text. When a driver says *"I'm stuck in snow, call dispatch,"* Tasha places a **real phone call** via Twilio, has a multi-turn conversation with a human dispatcher, and relays the result back to the driver. A working, end-to-end voice-AI ↔ telephony bridge driven by a Continuum LLM persona.

### 3. Two surfaces, one brain
The same Continuum agent serves a fleet manager's analytics portal **and** a driver's voice-first cab tablet — different personas, different tools, one runtime.

### 4. Proactive driver wellness, not surveillance
While competitors use invasive dashcam fatigue detection drivers hate, FleetShield uses **privacy-respecting wellness check-ins**, burnout signals derived from driving telematics, and **Hours-of-Service** compliance gauges — giving drivers agency over their own wellbeing.

### 5. Every insight is in dollars
Not "you should reduce speeding" but "coaching your top 5 drivers prevents an estimated *N* incidents and recovers *$X* a year." Safety, wellness, and sustainability are all translated into the language executives and underwriters fund.

### 6. Genuinely built *on* Continuum
The agent, the 15 MCP tools, the multi-step missions, the multi-turn Redis sessions, the model routing, and the dispatcher persona are all **Continuum primitives**. We didn't build an agent framework — we built a product on one. See **[CONTINUUM.md](CONTINUUM.md)** for the file-referenced breakdown.

### 7. Transparent, deterministic methodology
Every score is a **pure function** over a **deterministic** dataset (fixed RNG seed). No LLM hallucinating a risk score — the LLM's job is to decide what to *do* about it. The numbers are reproducible on every boot.

---

## Platform Overview — 8 Core Pillars

| # | Pillar | What It Does |
|---|---|---|
| 1 | **Insurance Premium Optimization** | Fleet insurability score (0–100, A+ to F) with weighted component breakdown, what-if simulator, and savings projections |
| 2 | **Predictive Safety Analytics** | Pre-shift risk scoring, driver-deterioration detection, dangerous-corridor mapping, 7-day forecasting |
| 3 | **Smart Incident Prevention** | AI alert triage with urgency scoring (0–100), event clustering, and prioritized interventions |
| 4 | **Autonomous Mission Agents** | 5 mission types that run multi-step analyses in the background — coaching sweeps, wellness checks, safety investigations, insurance optimization, pre-shift sweeps |
| 5 | **Operator AI Assistant (Tasha)** | Full-screen voice + text assistant with 15 tools, mission deployment, and rich visual reports |
| 6 | **Driver Voice AI Portal** | Personal dashboard with voice AI, **real Twilio dispatch calls**, HOS compliance, wellness check-ins, load management, gamification |
| 7 | **Live Fleet Map** | Real-time vehicle tracking with risk-colored markers, speeding hotspots, and GPS trails |
| 8 | **ROI & Sustainability** | Before/after comparisons, dollar-quantified savings, retention risk, green-fleet scoring, EV-readiness analysis |

---

## The Market Opportunity — Why Transportation AI Is Wide Open

Roughly **half of all AI-agent activity is concentrated in software engineering** — nearly the entire market in a single category. The remaining half is spread thin across a dozen-plus verticals, with travel and logistics representing a tiny sliver of agent market share.

This isn't a crowded space. It's a **greenfield.**

The North American trucking industry is a **$940 billion** sector running on razor-thin 3–6% net margins. It employs ~3.5 million drivers and powers the physical economy — yet it has almost zero AI-agent penetration. The few tools that exist are either:
- **Hardware-first** (Samsara, Motive) — selling cameras and ELD devices, not intelligence
- **Broker-focused** (Lanesurf, FleetWorks) — optimizing freight markets, not fleet operations
- **Infrastructure layers** (Terminal) — normalizing data, not analyzing it

Nobody is building **AI employees for fleet operations** — agents that autonomously investigate safety events, optimize insurance, coach drivers, and coordinate across specialized workers. That's the gap FleetShield AI fills.

### Why transportation is uniquely ready

| Factor | Why It Matters |
|---|---|
| **Billions of data points, almost none analyzed** | Millions of telematics devices generate data daily; <1% turns into a decision. |
| **Decisions are time-critical** | A pre-shift risk assessment delivered 2 hours late is worthless. Agents deliver in seconds. |
| **3.5M drivers, zero offices** | You can't walk a distributed workforce through coaching. Voice AI goes to them. |
| **3–6% net margins** | The compound effect of many agents each saving a fraction is the difference between surviving and thriving. |
| **Regulatory maze** | HOS, FMCSA, DOT — agents handle the tedium so humans focus on strategy. |

---

## Competitive Landscape — How We Compare

The fleet/logistics space has attracted billions in venture funding. Here's how FleetShield differentiates from the leaders:

| Company | Focus | What They Do | What FleetShield Does Differently |
|---|---|---|---|
| **Samsara** | Hardware + software | AI dashcams, GPS, ELD, CV driver monitoring. Hardware-first, surveillance-heavy. | **Software-only, no hardware cost.** Works with existing telematics. Privacy-respecting wellness, not cameras. |
| **Motive** (KeepTruckin) | ELD + fleet mgmt | ELD compliance, dashcams with collision alerts. Invasive fatigue detection. | **Proactive prediction vs. reactive camera alerts.** Forecasts risk *before* shifts; voice-first driver UX. |
| **Flexport** | Global supply chain | Freight forwarding + supply-chain intelligence. | **Trucking fleet-specific.** Deep telematics intelligence + quantified insurance ROI, not shipment tracking. |
| **FleetWorks** | AI freight marketplace | AI agents match trucks to cargo (broker↔carrier). | **Fleet operator tool, not a marketplace.** Optimizes the fleet internally; our AI calls real dispatchers, not brokers. |
| **Palace** | Dispatch automation | AI-native load assignment + scheduling. | **Safety + insurance intelligence, not just dispatch.** Mission agents do analyst work, not scheduling. |
| **Lanesurf** | Voice AI for freight | Voice AI negotiates rates with carriers for brokers. | **Voice AI for drivers and operators, not brokers.** Serves the people *in* the truck. |
| **Terminal** | Telematics API | "Plaid for telematics" — universal data access layer. | **Intelligence layer, not infrastructure.** We *analyze* the data: 9 engines, predictive safety, AI missions. |
| **Carma** | Fleet maintenance | Marketplace for commercial repairs. | **Prevention over repair.** We predict and prevent incidents upstream. |

**No one combines all of these in one platform:** predictive safety analytics · quantified insurance ROI · autonomous AI mission agents · real phone calls to dispatch · voice-first driver wellness · dual operator + driver portals — all on a single agent runtime.

---

## Built on Continuum

FleetShield is a **product built on Continuum**, not a framework wrapper. Every agentic capability maps to a Continuum primitive:

| Capability | Continuum primitive |
|---|---|
| Tasha (the assistant) | `BaseAgent` + `AgentRunner.run_stream()` → SSE |
| 15 fleet tools | one **FastMCP** server, discovered over `MCPServerStreamableHttp` + `ToolExecutor` |
| Rich cards + spoken summary | streamed `EventType` tool-call / content-delta events adapted to the frontend contract |
| Multi-turn memory | **Redis-backed sessions** (`get_or_create_session`) — history loaded/saved automatically |
| Autonomous missions | multi-step agent pipelines streaming `mission_progress` / `mission_finding` / `mission_complete` |
| Dispatcher conversation | a second Continuum LLM persona driving a live two-way phone call |
| Model routing | provider-prefix routing (Claude Sonnet 4.5) with graceful fallback |

**One-flag upgrades** (off by default, documented): mem0 long-term memory, Langfuse observability, native workflow agents (`SequentialAgent` / `PlannerAgent`), Temporal durable workflows, Smart Gateway routing.

> **📘 Full, file-referenced breakdown of every Continuum primitive we use → [CONTINUUM.md](CONTINUUM.md).**

---

## Technical Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                  │
│                 Next.js 16 + React 19 + Tailwind 4                     │
│              Framer Motion + Recharts + Lucide  ·  :3001               │
│                                                                        │
│  ┌────────────────────────────┐    ┌──────────────────────────────┐  │
│  │   Operator Portal (12 pages)│    │   Driver Cab Portal          │  │
│  │   Dashboard · Tasha (15 tools)│   │   Home (Score, HOS, Wellness)│  │
│  │   Insurance · Predictive     │    │   Load + Dispatch (☎ call)   │  │
│  │   Alerts · ROI · Wellness    │    │   Training · Voice · Rank    │  │
│  │   Sustainability · Map ...   │    │   Floating mic on every tab  │  │
│  └────────────────────────────┘    └──────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│        REST + SSE (/api/*)   ·   WebSocket (/ws)   ·   ☎ Twilio        │
├──────────────────────────────────────────────────────────────────────┤
│                    FastAPI backend (Python 3.13)  ·  :3000             │
│                                                                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐   │
│  │ Tasha       │ │ Missions   │ │ Voice      │ │ REST routers     │   │
│  │ Continuum   │ │ 5 types    │ │ STT/TTS    │ │ fleet · driver   │   │
│  │ BaseAgent   │ │ autonomous │ │ Smallest AI│ │ assistant · voice│   │
│  │ run_stream  │ │ pipelines  │ │ Pulse/Waves│ │ SSE · WebSocket  │   │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │     Twilio Dispatch — real outbound call (TwiML Gather/Say)   │    │
│  │     two-way conversation driven by a Continuum LLM persona    │    │
│  └──────────────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────────┤
│                    MCP (StreamableHTTP, per-request)                   │
├──────────────────────────────────────────────────────────────────────┤
│        Fleet MCP server (FastMCP)  —  15 tools  ·  :8765               │
│        over 9 pure scoring engines                                     │
│  Driver Risk · Insurance · Wellness · Predictive · Alert Triage        │
│  ROI · What-If · Gamification · Green Score                            │
├──────────────────────────────────────────────────────────────────────┤
│   Data layer — deterministic mock telematics (seed=42)                 │
│   25 vehicles · 30 drivers · 90 days of events/trips                   │
├──────────────────────────────────────────────────────────────────────┤
│   Redis (:6380) — Continuum session store (multi-turn history)         │
└──────────────────────────────────────────────────────────────────────┘
```

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full technical deep-dive and request flows.

---

## Technical Deep Dives

### Tasha — a Continuum `BaseAgent` with per-request MCP

Each streaming request to `/api/assistant/stream` builds a fresh Continuum stack:

```
POST /api/assistant/stream  { message, conversationId }
  → get_or_create_session(session_id=conversationId)        # Redis multi-turn history
  → connect MCPServerStreamableHttp → http://localhost:8765/mcp
  → ToolExecutor(mcp)  → BaseAgent  → AgentRunner
  → run_stream(agent, input)  yields EventType events:
        tool_call    → (log)
        tool_result  → JSON-parse result → emit {type:"tool_result", toolName, result}  (rich card)
        content      → split <voice>…</voice> → {type:"voice_summary"} + {type:"text"}
        done         → {type:"done"}
  → close MCP connection
```

**Why reconnect per request:** a persistent StreamableHTTP connection raises `ClosedResourceError` on the 2nd request, so `TashaAgent` connects and cleans up around each turn. **Why JSON-parse the result:** MCP `structured_content` comes back `None`, so the tool's `result` string is parsed to feed the rich cards. **Voice-first:** the model wraps a spoken summary in `<voice>…</voice>`; a splitter emits that as a `voice_summary` event for TTS while the visible markdown streams as `text`.

### Autonomous Mission Agents

Not chatbots — autonomous workers that take an assignment, run a multi-step analysis, and report back. The agent calls the `deployMission` tool (returns a `{missionId, type}` intent); the FastAPI-side SSE handler runs the mission **in-process** and forwards its events into the same assistant channel.

```
Operator: "Run a coaching sweep on my riskiest drivers"
  → Tasha confirms + emits deployMission intent
  → missions.runner.run_mission(...) (async generator):
       1. scan all drivers' risk (driver_risk)
       2. per top-N driver: wellness + coaching plan + trend
       3. cross-reference deteriorating trends
       4. write executive summary (one LLM call; deterministic fallback)
  → streams mission_progress / mission_finding / mission_complete
  → syncs coaching action-items to affected drivers' portals
```

**5 mission types:**

| Mission (`type`) | Agent | What It Does |
|---|---|---|
| `coaching_sweep` | Coaching Agent | Analyzes riskiest drivers, builds individualized coaching plans with interventions + dollar impact |
| `wellness_check` | Wellness Agent | Scans the fleet for burnout/fatigue risk and retention flags |
| `safety_investigation` | Safety Agent | Deep-dives a driver's event patterns, correlates with wellness, builds root-cause analysis |
| `insurance_optimization` | Insurance Agent | Analyzes score components, finds quick wins, estimates premium savings + payback |
| `preshift_sweep` | Pre-Shift Agent | Real-time risk assessment of today's roster before drivers roll out |

**Key design:** scoring engines are called **directly** (no LLM sub-agents) — fast, deterministic, cheap. Only the executive summary uses the LLM.

### Real Twilio Dispatch Calls — voice AI ↔ telephony bridge

The most technically ambitious feature. When a driver invokes `callDispatch(intent=…)`:

```
Driver (voice): "I'm stuck in snow at the 401 and Don Valley — call dispatch"
  → voice.twilio_dispatch.start_call(driver_id, intent)
  → Twilio outbound call → DISPATCHER_NUMBER rings → human answers
  → POST /twilio/voice  (TwiML): <Say> greeting (Polly.Joanna) + <Gather> speech
  → driver-advocate LLM (Continuum) speaks on the driver's behalf
  → POST /twilio/gather: dispatcher's reply (Twilio STT) → LLM responds (1–2 sentences)
  → loop up to 8 turns; [END_CALL] token or max turns → hangup TwiML
  → driver portal polls /dispatch-call/{id}/status → live transcript + state
  → Tasha relays the outcome back to the driver
```

Uses Twilio's `<Gather>`/`<Say>` TwiML (stable for a live demo) rather than Media Streams. `/twilio/*` webhooks validate the Twilio signature in production.

### Voice AI Pipeline — Smallest AI

| Stage | Provider | Format |
|---|---|---|
| **STT** | Smallest AI **Pulse** (per-utterance WebSocket) | PCM16 linear, 16 kHz; auto-gain to recover quiet audio after TTS echo |
| **TTS** | Smallest AI **Waves** (`lightning-v3.1`) | PCM16 24 kHz, wrapped in a minimal RIFF/WAV header for the browser |

Browser mic → AudioContext (16 kHz PCM16) → energy-based VAD → WebSocket `/ws` → Pulse STT → Tasha (15 tools) → sentence-level Waves TTS → base64 audio → browser speaker.

### 9 Scoring Engines — pure functions, no side effects

All engines are pure functions returning **camelCase dicts** (matching `frontend/src/types/fleet.ts`), `None` on invalid input. They're imported by the MCP tools, the REST routes, **and** the missions — modular and testable.

| Engine (`backend/scoring/`) | Output | Method / Weighting |
|---|---|---|
| `driver_risk.py` | `riskScore` 0–100, `tier`, `annualizedCost` | event frequency 40% · severity 25% · pattern 20% · trend 15% |
| `insurance_score.py` | `overallScore` 0–100, `grade` A+–F, `premiumImpact` | safe driving 35% · compliance 25% · maintenance 20% · driver quality 20% |
| `wellness_predictor.py` | `burnoutRisk`, `burnoutProbability`, `retentionCost` | shift irregularity, consecutive long days, rest compression, event escalation, night-driving creep |
| `predictive_safety.py` | `preShiftRisk`, forecast, deteriorating, corridors | fatigue · behavior trend · recent severity · workload |
| `alert_triage.py` | urgency-scored `alerts` 0–100, daily briefing | severity + repeat-offender + recency + pattern + cluster size |
| `roi_engine.py` | `totalAnnualSavings`, `roiPercent`, `paybackMonths` | insurance · accident prevention · fuel · retention · productivity (45-day before/after) |
| `green_score.py` | `overallScore`, `carbonFootprintTonsCO2`, EV readiness | fuel efficiency 30% · idle 25% · eco-driving 25% · fleet modernity 20% |
| `gamification.py` | level, points, badges, daily challenge | trip distance, safety-event penalties, streaks |
| `what_if.py` | projected score/premium/savings per scenario | models intervention impact on the insurance score |

> Full methodology with exact formulas and worked examples lives in **[ARCHITECTURE.md](ARCHITECTURE.md)** and the in-code docstrings.

---

## Features — Complete List

### Operator Portal (`/operator`)

| Page | Route | Key Features |
|---|---|---|
| **Dashboard** | `/operator` | Fleet KPIs, insurance score (A+–F), driver risk rankings, wellness + financial summary cards |
| **Tasha AI Assistant** | `/operator/assistant` | Full-screen chat + voice, 15 tools, mission deployment, rich visual reports, live mission tracker |
| **Insurance** | `/operator/insurance` | Score breakdown by component, improvement opportunities, **what-if simulator** |
| **Predictive Safety** | `/operator/predictive` | 7-day forecast, pre-shift risk grid, deterioration trends, dangerous corridors |
| **Alerts** | `/operator/alerts` | AI-prioritized daily briefing, urgency-scored cards (0–100), suggested actions |
| **ROI** | `/operator/roi` | Animated savings counter, 5-category breakdown, before/after comparison, retention risk |
| **Sustainability** | `/operator/sustainability` | Green-fleet scoring, fuel efficiency, carbon footprint, EV-readiness analysis |
| **Wellness** | `/operator/wellness` | Fleet-wide burnout risk, individual signals, trend visualization |
| **Drivers** | `/operator/drivers` · `/drivers/[id]` | Driver list with risk/wellness, individual deep-dive detail pages |
| **Vehicles** | `/operator/vehicles` | Inventory, maintenance tracking, utilization |
| **Safety Events** | `/operator/safety` | Event log with filters, type/severity breakdown, temporal patterns |
| **Live Map** | `/operator/map` | Real-time tracking, risk-colored markers, speeding hotspots, GPS trails |

### Driver Voice AI Portal (`/driver-portal`)

Tab-based, mobile-first layout built for truck-mounted tablets, with an always-visible floating mic button.

| Tab | Features |
|---|---|
| **Home** | Safety-score gauge, HOS compliance gauges (drive/duty remaining), AI wellness check-in, pre-shift briefing, daily challenge |
| **Training** | Coaching programs from operator missions (checklists), action items with priority, badge when new programs arrive |
| **Voice** | Animated orb (listening/thinking/speaking/dispatching), real-time transcript, mute/end, text fallback |
| **Load** | Load card (origin→destination, commodity, weight, rate), broker info, **"Call Dispatch" → real Twilio phone call** with live transcript |
| **Rank** | Driver leaderboard, badge gallery (earned/locked), level progress |

---

## AI Agent Tools (15 total)

Tasha has access to 15 MCP tools, each backed by a scoring engine or data source. **Tool names match `ComponentRenderer.tsx`** so each result renders as a rich card.

| Tool | What It Does | Backing |
|---|---|---|
| `getFleetOverview` | Fleet KPIs, event counts, risk distribution, top risk drivers | `seed_data.get_fleet_summary` |
| `getFleetInsuranceScore` | Insurability score (0–100, A+–F) + components + premium impact | `insurance_score` |
| `getDriverRiskScore` | Per-driver or ranked risk scores with tier + annualized cost | `driver_risk` |
| `getDriverWellness` | Burnout/fatigue assessment + retention cost | `wellness_predictor` |
| `getSafetyEvents` | Recent events with severity/type/location, filterable | seed events |
| `getFinancialImpact` | Annual savings across 5 categories + ROI % + payback | `roi_engine` |
| `getFleetForecast` | 7-day safety forecast + top risk factors | `predictive_safety` |
| `getAlertBriefing` | Morning briefing — triaged, urgency-ranked alerts | `alert_triage` |
| `getPreShiftRisk` | Pre-shift risk from rest/hours/weather/route | `predictive_safety` |
| `getCoachingRecommendations` | Prioritized coaching with expected improvement + savings | `driver_risk` + `wellness_predictor` |
| `getFleetComparison` | Fleet vs. industry benchmarks | `insurance_score` |
| `getGreenFleetMetrics` | Carbon footprint, idle waste, EV readiness, eco scores | `green_score` |
| `getFleetTrends` | Drivers whose risk is deteriorating week-over-week | `predictive_safety` |
| `deployMission` | Deploy an autonomous background mission agent | `missions.runner` |
| `callDispatch` | Place a **real** outbound dispatch phone call for the driver | `voice.twilio_dispatch` |

---

## API Reference (selected)

REST + SSE + WebSocket. Routers: `server.py` (fleet/operator + Twilio), `assistant_routes.py`, `driver_routes.py`, `voice_routes.py`.

### Fleet analytics
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/fleet/overview` | Fleet KPIs & summary |
| GET | `/api/fleet/drivers` · `/drivers/{id}` | Drivers with risk scores / detail |
| GET | `/api/fleet/vehicles` | Vehicle inventory |
| GET | `/api/fleet/events` | Safety events (filterable) |
| GET | `/api/fleet/score` | Fleet insurability score |
| GET | `/api/fleet/risks` · `/risks/{id}` | Driver risk scores |
| GET | `/api/fleet/wellness` · `/wellness/{id}` · `/wellness-all` | Wellness summaries |

### Predictive · Alerts · ROI · Sustainability · Map
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/fleet/predictive/forecast` · `/pre-shift` · `/pre-shift/{id}` · `/trends` · `/corridors` | Predictive safety |
| GET | `/api/fleet/alerts` · `/alerts/briefing` | Triaged alerts + briefing |
| GET | `/api/fleet/roi` · `/roi/before-after` · `/roi/retention` | ROI calculations |
| GET / POST | `/api/fleet/what-if/defaults` · `/what-if` | What-if simulator |
| GET | `/api/fleet/sustainability` (+ `/drivers`, `/vehicles`) | Green metrics |
| GET | `/api/fleet/map/live` · `/map/trail/{id}` · `/map/hotspots` | Live map |

### Assistant · Missions · Voice · Twilio
| Method | Endpoint | Description |
|---|---|---|
| POST (SSE) | `/api/assistant/stream` | Stream Tasha's response (text + voice + tool cards) |
| GET | `/api/missions/active` · `/missions/{id}` | Mission status / detail |
| WS | `/ws` | Voice AI WebSocket |
| POST | `/api/tts/synthesize` | Smallest AI Waves TTS (WAV) |
| POST | `/twilio/voice` · `/twilio/gather` · `/twilio/status` | Twilio webhooks (signature-validated) |

### Driver portal (selected)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/driver/login` | PIN authentication |
| GET | `/api/driver/{id}/dashboard` · `/load` · `/hos` · `/messages` | Driver state |
| GET/POST | `/api/driver/{id}/wellness-checkin` · `/wellness-trend` | Wellness |
| GET | `/api/driver/{id}/gamification` · `/badges` · `/actions` · `/training` | Gamification + coaching |
| POST | `/api/driver/{id}/dispatch-call` · GET `/dispatch-call/{callId}/status` | Real dispatch call |

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **Python 3.13** | Runtime |
| **ShyftLabs Continuum** (vendored `continuum-src/`, imported as `orchestrator`) | Agent runtime — BaseAgent, AgentRunner, MCP, sessions, model routing |
| **FastAPI + Uvicorn** | Async HTTP, SSE, WebSocket |
| **FastMCP** (`mcp.server.fastmcp`) | MCP tool server (15 tools) |
| **Redis** (:6380) | Continuum session store (multi-turn history) |
| **Anthropic Claude Sonnet 4.5** | Agent reasoning, mission summaries, dispatcher persona |
| **Smallest AI** (Pulse STT / Waves TTS) | Voice pipeline |
| **Twilio** | Real outbound dispatch phone calls |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16.1.6 | React framework (App Router), proxies `/api/*` to backend |
| React | 19.2.3 | UI |
| Tailwind CSS | 4 | Styling |
| Recharts | 3.7 | Charts |
| Framer Motion | 12.34 | Animation |
| Lucide React | 0.574 | Icons |
| TypeScript | 5 | Type safety |

---

## Project Structure

```
AgentShyft-hackathon/
├── backend/
│   ├── api/
│   │   ├── server.py             # FastAPI app: fleet/operator routes + Twilio + /ws
│   │   ├── assistant_routes.py   # Tasha SSE streaming
│   │   ├── driver_routes.py      # Driver-portal routes
│   │   └── voice_routes.py       # TTS synthesis
│   ├── agent/
│   │   ├── tasha.py              # Continuum BaseAgent, per-request MCP, SSE adapter, sessions
│   │   └── prompts.py            # Tasha system prompt + voice-mode addendum
│   ├── data/
│   │   ├── seed_data.py          # deterministic fleet: 25 vehicles, 30 drivers, 90d (seed=42)
│   │   ├── driver_session.py     # loads, messages, HOS, action items
│   │   └── live_fleet.py         # live-map GPS simulation
│   ├── missions/
│   │   ├── store.py              # 5 mission types + registry
│   │   └── runner.py             # autonomous multi-step pipelines (async generators)
│   ├── mcp_server/
│   │   └── fleet_tools.py        # FastMCP server — 15 tools (names match the renderer)
│   ├── scoring/                  # 9 pure-function engines (camelCase dict contracts)
│   │   ├── driver_risk.py  insurance_score.py  wellness_predictor.py
│   │   ├── predictive_safety.py  alert_triage.py  roi_engine.py
│   │   └── green_score.py  gamification.py  what_if.py
│   ├── voice/
│   │   ├── stt.py                # Smallest AI Pulse (per-utterance WebSocket)
│   │   ├── tts.py                # Smallest AI Waves (lightning-v3.1)
│   │   ├── session.py            # voice session + VAD
│   │   └── twilio_dispatch.py    # real two-way dispatch call (Continuum persona)
│   └── tests/                    # pytest suite (92 tests)
├── frontend/
│   └── src/
│       ├── app/operator/         # 12 operator pages
│       ├── app/driver-portal/    # driver cab portal (tabs)
│       ├── components/assistant/ # ComponentRenderer (tool→card), MissionTracker
│       ├── lib/api.ts            # API client contract
│       └── types/fleet.ts        # TS interfaces (match backend camelCase)
├── continuum-src/                # vendored ShyftLabs Continuum (pip install -e) [git-ignored]
├── scripts/dev.sh                # one-command local startup
└── pytest.ini · ruff.toml        # test + lint config
```

---

## Getting Started

### Prerequisites
- **Python 3.13**, **Node 20+**, **Redis** (`brew install redis`)
- An **Anthropic API key** (required for the agent + missions)
- *(Optional)* Smallest AI key (voice) and Twilio credentials (the real phone call)

### Installation

```bash
# 1. Backend deps (Continuum is vendored in ./continuum-src)
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ./continuum-src
pip install fastapi "uvicorn[standard]" httpx twilio python-multipart sse-starlette audioop-lts websockets

# 2. Frontend deps
( cd frontend && npm install )

# 3. Configure secrets
cp .env.example .env   # add ANTHROPIC_API_KEY (+ SMALLEST/TWILIO if using voice/calls)

# 4. Run everything (Redis :6380 + MCP :8765 + API :3000 + frontend :3001)
./scripts/dev.sh
```

Open **http://localhost:3001** (or the **[live demo](https://fleetshield-ai.vercel.app)**).

### Environment variables
| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | Claude (assistant, missions, dispatcher persona) |
| `SMALLEST_API_KEY` | No* | Voice STT/TTS |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | No* | Real dispatch calls |
| `TWILIO_NUMBER` / `DISPATCHER_NUMBER` | No* | Outbound + dispatcher phone numbers |
| `PUBLIC_BASE_URL` | No* | Public URL for Twilio webhooks (ngrok in dev; Railway URL in prod) |
| `SESSION_ENABLED` | No | Redis multi-turn sessions (default on; falls back to in-context history) |

\* Optional — the analytics dashboards and Tasha's text/cards work without them; voice and the phone call activate when configured.

### Quick test
```bash
curl http://localhost:3000/api/health
curl http://localhost:3000/api/fleet/overview
```

---

## Demo Guide

### Driver portal logins (deterministic seed data)
| Employee # | PIN | Driver | Risk |
|---|---|---|---|
| **`405`** | **`7234`** | **Marcus Rivera** — *recommended demo login* | high (fleet's riskiest) |
| `241` | `1847` | James Wilson | low |
| `318` | `2956` | Sarah Chen | low |
| `714` | `5190` | Jake Thompson | high |
| `802` | `1382` | Derek Shaw | high |

### Recommended 3-minute flow
1. **Problem** (~20s) — the $940B crisis hiding in telematics.
2. **Tasha** (`/operator/assistant`) — *"Who's our riskiest driver and what's it costing us?"* → rich cards + spoken answer (Marcus Rivera, high risk, ~$25K/yr).
3. **Mission** — *"Deploy the coaching agent"* → watch the autonomous pipeline stream findings → executive report → tasks pushed to drivers.
4. **Driver portal** (`/driver-portal` as Marcus) — voice + HOS + wellness.
5. **Real phone call** — tap **Call Dispatch** → your phone rings → the AI negotiates with you (a human dispatcher) → relays the outcome back.
6. **Close** (`/operator/roi`) — the verified numbers.

> The full verbatim **3-minute presentation script** (with setup checklist, fallbacks, and the "where's the AI?" judge Q&A) is in **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)**.

---

## Deployment — Railway + Vercel

The backend is a stateful, long-running process (WebSocket, Twilio webhooks, in-memory mission store, Redis sessions); the frontend is a Next.js app. They have different hosting needs.

- **Backend → Railway** — always-on process, native WebSocket, a **permanent public URL** for Twilio callbacks, Redis add-on for Continuum sessions. Live: `fleetshield-api-production-0e8d.up.railway.app`.
- **Frontend → Vercel** — Next.js-native, global CDN, `/api/*` proxied to the Railway backend (single origin, no browser CORS). Live: **[fleetshield-ai.vercel.app](https://fleetshield-ai.vercel.app)**.
- **Twilio in prod** uses the Railway `PUBLIC_BASE_URL` (no ngrok), and `/twilio/*` validates the request signature.

Full runbook in **DEPLOY.md**.

---

## Impact — by the numbers

Computed **live** by the platform's engines over the deterministic mock fleet (25 vehicles, 30 drivers, 90 days) — reproducible on every boot and surfaced in the UI + Tasha's answers.

| Metric | Value |
|---|---|
| Total potential annual savings | **$523,470** |
| ROI / payback | **~2,081%** · **< 1 month** |
| Safety events (45-day before → after) | **down ~75%** (severe events **down ~80%**) |
| Fleet insurability score | **78 / 100 (B)** |
| Riskiest driver exposure (Marcus Rivera) | **~$25,000 / yr**, high risk |
| Analyst work replaced by mission agents | **15–20 hrs/week** |
| Drivers coached by AI, not surveilled | **30** |

**Savings breakdown** (`roi_engine`): accident prevention **$273K** · driver retention **$132K** · productivity **$75K** · insurance premium **$22K** · fuel **$22K**.

---

## Testing & Quality

```bash
pytest                 # 92 tests: data invariants, all 9 engines (every driver), all routes, all 5 missions
ruff check backend/    # clean (config in ruff.toml)
```

---

## Documentation

| Doc | What |
|---|---|
| **[CONTINUUM.md](CONTINUUM.md)** | **Exactly which Continuum primitives we use, where, and why (file-referenced)** |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical deep-dive + request flows |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | The 3-minute live presentation script + judge Q&A |
| [COMPETITION.md](COMPETITION.md) | Hackathon rules, judging, our pitch, why we win |
| [SECURITY.md](SECURITY.md) | Security posture + production roadmap |
| [CLAUDE.md](CLAUDE.md) | Engineering guide + hard-won gotchas for contributors/agents |

---

## License

**All rights reserved.** Copyright 2026 FleetShield AI.

Shared publicly for evaluation as part of the AgentShyft Hackathon 2026. No permission is granted to use, copy, modify, or distribute this code without explicit written consent from the copyright holder.

---

<div align="center">
Built for the <b>AgentShyft Hackathon</b> · ShyftLabs · Toronto, May 2026 · on the <b>Continuum</b> agent runtime.
</div>
</content>
</invoke>
