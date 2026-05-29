# How FleetShield AI uses ShyftLabs Continuum

FleetShield AI is a **product built on the Continuum agent runtime** — not a wrapper
around it. This document is a precise, file-referenced accounting of every Continuum
primitive we use, how, and why. (Continuum is vendored at `./continuum-src` and
imported as the `orchestrator` package.)

## TL;DR — what we use

| Continuum primitive | Where (file) | What it powers |
|---|---|---|
| `BaseAgent` | `backend/agent/tasha.py` | **Tasha**, the fleet assistant |
| `AgentRunner` — `run_stream()` / `run()` | `backend/agent/tasha.py` | Streaming chat (SSE) + non-stream turns (voice, summaries) |
| `AgentConfig`, `RunnerConfig` | `backend/agent/tasha.py` | Turn limits, session logging, no-persist runner |
| `AgentMemoryConfig`, `AgentMemoryScope` | `backend/agent/tasha.py` | Per-user memory config (one-flag-ready) |
| **FastMCP** (`@mcp.tool`) | `backend/mcp_server/fleet_tools.py` | The **14 fleet tools** the agent calls |
| `MCPServerStreamableHttp` | `backend/agent/tasha.py` | Agent ↔ MCP tool-server connection |
| `ToolExecutor` (subclassed) | `backend/agent/tasha.py` | Tool execution + capturing structured results for rich cards |
| `EventType` streaming | `backend/agent/tasha.py` | `CONTENT_DELTA` / `TOOL_CALL_*` / `RUN_END` → our SSE contract |
| **Sessions** (`get_or_create_session`) | `backend/agent/tasha.py` | **Multi-turn conversation memory** (Redis), auto-loaded by the runner |
| DI **Container** (`get_container`) + **Lifecycle** | `backend/agent/tasha.py` | Service wiring + startup/health |
| **LLM client** (`llm_client.chat`, `LLMConfig`) | `backend/missions/runner.py`, `backend/voice/twilio_dispatch.py` | Mission executive summaries + the phone dispatcher persona |
| **Provider routing** (model-string prefix) + fallback | `.env` (`DEFAULT_/FALLBACK_LLM_MODEL`) | Claude Sonnet 4.5 with graceful fallback |
| `get_logger` | across `backend/` | Structured logging through the framework |

---

## 1. The agent — `BaseAgent` + `AgentRunner`

`backend/agent/tasha.py` builds **Tasha** as a Continuum `BaseAgent` and runs her with `AgentRunner`:

```python
from orchestrator import (
    AgentConfig, AgentMemoryConfig, AgentMemoryScope, AgentRunner,
    BaseAgent, MCPServerStreamableHttp, RunnerConfig, ToolExecutor, get_logger,
)
from orchestrator.agent.types import EventType

agent = BaseAgent(
    name="tasha",
    instructions=build_system_prompt(voice_mode=True, current_page=...),
    model=MODEL,                       # "claude-sonnet-4-5"
    temperature=0.4,
    tools=tools,                       # discovered from the MCP server
    tool_executor=executor,            # our CapturingToolExecutor
    memory_config=AgentMemoryConfig(search_memories=MEMORY_ON, store_memories=MEMORY_ON,
                                     search_scope=AgentMemoryScope.USER, store_scope=AgentMemoryScope.USER),
    config=AgentConfig(max_turns=6, log_to_session=SESSION_ON),
)
runner = AgentRunner(container=self._container, tool_executor=executor,
                     config=RunnerConfig(persist_state=False, default_max_turns=6))
runner.register_agent(agent)
```

- **`run_stream()`** drives the operator chat (token + tool-call streaming).
- **`run()`** drives the voice turn (`respond_voice`) and is reused for one-shot generations.

## 2. Tools — FastMCP + `MCPServerStreamableHttp` + `ToolExecutor`

The 14 fleet tools live in **one FastMCP server** (`backend/mcp_server/fleet_tools.py`):

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("fleet")

@mcp.tool(name="getDriverRiskScore", description="…")
def driver_risk_score(driver_id: str = "", driver_name: str = "") -> dict: ...
```

The agent connects over Continuum's **`MCPServerStreamableHttp`** and discovers them via the **`ToolExecutor`**. We subclass the executor to capture each tool's full structured result (MCP `structured_content` is None, so we parse the content string) — that payload feeds the frontend's rich cards:

```python
class CapturingToolExecutor(ToolExecutor):
    def _on_tool_result(self, tool_name, result, artifact):
        structured = getattr(artifact, "structured_content", None) or json.loads(result)
        self.captures.append((tool_name, structured))
```

Tool **names are chosen to match the frontend renderer**, so every tool result renders as a rich card with zero UI changes.

## 3. Streaming — `EventType` → SSE

We translate Continuum's stream into the exact SSE contract the Next.js frontend speaks:

```python
async for event in runner.run_stream(agent=agent, input=agent_input,
                                     session_id=session_id, user_id="operator"):
    if event.type == EventType.CONTENT_DELTA:   # → {"type":"text"} / {"type":"voice_summary"}
    elif event.type == EventType.RUN_ERROR:     # → graceful error
    elif event.type == EventType.RUN_END:       # → done
```

Tool results captured in §2 are emitted as `{"type":"tool_result", toolName, result}`; the spoken `<voice>` block is split out as `{"type":"voice_summary"}` for TTS.

## 4. Memory — Continuum **Sessions** (the multi-turn fix)

Conversation continuity uses Continuum's **Redis-backed sessions**, not a hand-rolled history hack. We create/find the session and pass its id to the runner, which **loads and persists history automatically**:

```python
session_id = await self._container.session_client.get_or_create_session(
    session_id=conversation_id, user_id="operator")
# runner.run_stream(..., session_id=session_id) → history loaded & saved in Redis
```

This is why "who's riskiest?" → "go ahead" correctly deploys the mission instead of re-asking. (`AgentConfig(log_to_session=True)` enables persistence; a context-fold fallback covers a no-Redis environment.)

## 5. Autonomous missions — deployed by the agent, synthesized by Continuum's LLM

The agent's **`deployMission`** tool launches a multi-step fleet analysis. Honest design note: the per-step orchestration is a custom async generator (`backend/missions/runner.py`) for **deterministic, demo-reliable streaming**, but it is **deployed by the Continuum agent** (tool call) and the **executive summary is written by Continuum's LLM client**:

```python
from orchestrator.core.container import get_container
from orchestrator.llm.config import LLMConfig
llm = get_container().llm_client
resp = await llm.chat(messages=[...], config=LLMConfig(model=MODEL, max_tokens=350))
```

> Evolution path: these pipelines map directly onto Continuum's native **`SequentialAgent` / `PlannerAgent`** workflow agents — see §8.

## 6. The phone dispatcher — a Continuum LLM persona

The real two-way Twilio call (`backend/voice/twilio_dispatch.py`) is driven by a Continuum-LLM "driver-advocate" persona that generates each spoken turn from the live transcript via `container.llm_client.chat()`.

## 7. Infrastructure — Container, Lifecycle, providers, logging

- **DI Container + Lifecycle** (`get_container()`, `get_lifecycle_manager()`) wire and health-check the session/LLM/memory services at startup.
- **Provider routing** is by model-string prefix — `DEFAULT_LLM_MODEL=claude-sonnet-4-5` (Anthropic) with `FALLBACK_LLM_MODEL` and `LLM_ENABLE_FALLBACK`.
- **Configuration** is Continuum's pydantic-settings, fed from `.env`.
- **Logging** uses `get_logger` throughout.

---

## 8. What we deliberately did *not* enable (and the on-ramps we left)

Engineering honesty + a clear roadmap (each is a documented one-flag change — see `CLAUDE.md` → *Continuum upgrades*):

| Capability | Status | Why / on-ramp |
|---|---|---|
| **mem0 long-term memory** | off | Needs a vector store (Qdrant/Milvus → Docker, unavailable here). Agent is already memory-gated (`MEMORY_ON`); flip `MEMORY_ENABLED=true` + embedder. |
| **Langfuse observability** | off | One flag (`LANGFUSE_ENABLED=true` + keys) for full causal traces of every agent decision. |
| **Native workflow agents** (`SequentialAgent`, `PlannerAgent`, `Parallel`, …) | not used | Missions use a custom pipeline for deterministic streaming; these are the natural next step for richer multi-agent missions. |
| **Temporal durable workflows** | not used | For crash-safe, resumable long-running missions + human-in-the-loop gates. |
| **Smart Gateway** (`gateway_mode`) | not used | Cost-aware multi-model routing across 250+ models. |
| **Context compression** | off | Continuum's window map keys the dotted model name; the dashed API id defaults small. We bound history via sessions instead (see `CLAUDE.md` gotchas). |

## 9. Why Continuum was the right substrate

- **Agent + tools + streaming + sessions** out of the box — we built fleet *product* logic, not agent plumbing.
- **MCP-native tooling** let us expose 14 deterministic scoring engines to the LLM with type-safe schemas and zero glue.
- **One brain, many surfaces** — the same `BaseAgent` serves the manager portal, the driver cab, voice, and the phone call.
- **A clear scaling path** — memory, observability, durable workflows, and multi-model routing are all one configuration step away.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design and [README.md](README.md) for the product story.
