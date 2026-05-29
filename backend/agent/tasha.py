"""
Tasha — the FleetShield AI assistant, built on ShyftLabs Continuum.

A BaseAgent connected (over MCP) to the fleet-tools server, run via
AgentRunner.run_stream and adapted into the SSE event contract the existing
Next.js frontend already speaks:
  {type: "text", content}                  -> markdown delta (voice tag stripped)
  {type: "voice_summary", content}         -> the <voice>..</voice> content, for TTS
  {type: "tool_result", toolName, result}  -> full structured dict -> rich card
  {type: "mission_*"}                      -> streamed when the agent deploys a mission
  {type: "done"}

The MCP connection + tool executor + agent are built FRESH PER REQUEST: the
StreamableHTTP MCP session does not survive across separate request tasks
(reusing it raises ClosedResourceError on the 2nd call), so we connect and
clean up around each turn. This costs a few hundred ms but is bulletproof.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncGenerator
from typing import Any, Optional

# Load .env (LLM keys, MEMORY_ENABLED=false, etc.) BEFORE importing orchestrator,
# which reads settings via pydantic-settings at import time.
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from orchestrator import (  # noqa: E402
    AgentConfig,
    AgentMemoryConfig,
    AgentMemoryScope,
    AgentRunner,
    BaseAgent,
    MCPServerStreamableHttp,
    RunnerConfig,
    ToolExecutor,
    get_logger,
)
from orchestrator.agent.types import EventType  # noqa: E402
from orchestrator.core.container import get_container  # noqa: E402
from orchestrator.core.lifecycle import get_lifecycle_manager  # noqa: E402

from backend.agent.prompts import build_system_prompt  # noqa: E402

logger = get_logger(__name__)

FLEET_MCP_URL = os.environ.get("FLEET_MCP_URL", "http://localhost:8765/mcp")
MODEL = os.environ.get("DEFAULT_LLM_MODEL", "claude-sonnet-4-5")
# Continuum memory is one flag away: set MEMORY_ENABLED=true (+ Redis/vector store +
# an embedder) and Tasha remembers per-user facts across turns. Off by default so the
# demo runs with zero infra. See CLAUDE.md "Continuum upgrades".
MEMORY_ON = os.environ.get("MEMORY_ENABLED", "false").lower() == "true"
# Sessions ON -> Continuum loads/saves conversation history in Redis natively,
# keyed by session_id (we use the frontend's conversationId). This is the real
# multi-turn fix; a history-fold is kept as a fallback when sessions are off.
SESSION_ON = os.environ.get("SESSION_ENABLED", "false").lower() == "true"


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _build_input(message: str, history: list | None) -> str:
    """Fold recent conversation turns into the input so the stateless agent has
    context (e.g. so 'go ahead' after a mission offer actually deploys it)."""
    if not history:
        return message
    lines = []
    for turn in history[-10:]:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        who = "User" if turn.get("role") == "user" else "Tasha"
        lines.append(f"{who}: {content[:800]}")
    if not lines:
        return message
    return (
        "Conversation so far (continue it naturally; if you previously offered to deploy a "
        "mission agent and the user is now confirming — 'yes', 'go ahead', 'do it' — then call "
        "deployMission immediately with the agreed mission_type instead of re-asking):\n"
        + "\n".join(lines)
        + f"\n\nUser: {message}"
    )


class _VoiceSplitter:
    """Splits a token stream into a spoken <voice> summary + visible text.

    Holds output until it can tell whether a leading <voice>...</voice> block is
    present, so the spoken summary never flashes as visible text. Emits one
    voice_summary event, then streams the remaining text (voice block removed).
    """

    def __init__(self) -> None:
        self.buf = ""
        self.resolved = False
        self.has_voice = False
        self.display_emitted = 0

    def _display(self) -> str:
        if self.has_voice:
            return re.sub(r"<voice>.*?</voice>\s*", "", self.buf, count=1, flags=re.S)
        return self.buf

    def feed(self, delta: str) -> list[dict]:
        self.buf += delta
        out: list[dict] = []
        if not self.resolved:
            if "<voice>" in self.buf:
                if "</voice>" in self.buf:
                    m = re.search(r"<voice>(.*?)</voice>", self.buf, flags=re.S)
                    if m:
                        out.append({"type": "voice_summary", "content": m.group(1).strip()})
                        self.has_voice = True
                        self.resolved = True
                # else: inside an open voice tag — hold
            else:
                stripped = self.buf.lstrip()
                if stripped and not "<voice>".startswith(stripped[:7]):
                    self.resolved = True  # plain text, no voice tag
        if self.resolved:
            disp = self._display()
            if len(disp) > self.display_emitted:
                out.append({"type": "text", "content": disp[self.display_emitted:]})
                self.display_emitted = len(disp)
        return out

    def finish(self) -> list[dict]:
        out: list[dict] = []
        self.resolved = True
        disp = self._display()
        if len(disp) > self.display_emitted:
            out.append({"type": "text", "content": disp[self.display_emitted:]})
            self.display_emitted = len(disp)
        return out


class CapturingToolExecutor(ToolExecutor):
    """ToolExecutor that records each tool's full structured result for the SSE.

    Continuum's stream only carries a truncated string in TOOL_CALL_END, so we
    capture here. MCP structured_content is usually None, so we parse the tool's
    JSON content string (exactly what the LLM received) into the rich-card payload.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.captures: list[tuple[str, Any]] = []

    def _on_tool_result(self, tool_name: str, result: str, artifact: Any) -> None:
        structured = getattr(artifact, "structured_content", None) if artifact else None
        if structured is None and isinstance(result, str):
            try:
                structured = json.loads(result)
            except Exception:
                structured = None
        self.captures.append((tool_name, structured))


class TashaAgent:
    """Lifecycle/container are shared; the MCP session is per-request."""

    def __init__(self) -> None:
        self._lifecycle = None
        self._container = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._lifecycle = get_lifecycle_manager(
            fail_on_unhealthy=False, verify_connections=False, enable_signal_handlers=False
        )
        await self._lifecycle.initialize()
        self._container = get_container()
        self._initialized = True
        logger.info(f"Tasha lifecycle ready (model={MODEL})")

    async def _build_session(self, current_page: Optional[str]):
        mcp = MCPServerStreamableHttp(
            params={"url": FLEET_MCP_URL}, client_session_timeout_seconds=30
        )
        await mcp.connect()
        executor = CapturingToolExecutor({mcp: None})
        await executor.initialize()
        tools = executor.get_tool_definitions()
        agent = BaseAgent(
            name="tasha",
            instructions=build_system_prompt(voice_mode=True, current_page=current_page),
            model=MODEL,
            temperature=0.4,
            tools=tools,
            tool_executor=executor,
            memory_config=AgentMemoryConfig(
                search_memories=MEMORY_ON, store_memories=MEMORY_ON,
                search_scope=AgentMemoryScope.USER, store_scope=AgentMemoryScope.USER,
            ),
            config=AgentConfig(max_turns=6, log_to_session=SESSION_ON),
        )
        runner = AgentRunner(
            container=self._container,
            tool_executor=executor,
            config=RunnerConfig(persist_state=False, default_max_turns=6),
        )
        runner.register_agent(agent)
        return mcp, executor, agent, runner

    async def _ensure_session(self, conversation_id: str | None) -> str | None:
        """Create/find the Redis session for this conversation so the runner can
        load + persist history. Returns the session id, or None (-> fold history)."""
        if not (SESSION_ON and conversation_id):
            return None
        try:
            sc = self._container.session_client if self._container else None
            if sc and getattr(sc, "is_enabled", False):
                return await sc.get_or_create_session(
                    session_id=conversation_id, user_id="operator"
                )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"session init failed ({e}); falling back to folded history")
        return None

    async def stream_assistant(
        self, message: str, current_page: Optional[str] = None,
        history: list | None = None, conversation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        if not self._initialized:
            await self.initialize()

        mcp, executor, agent, runner = await self._build_session(current_page)
        session_id = await self._ensure_session(conversation_id)
        use_session = session_id is not None
        # With native sessions the runner loads history from Redis; otherwise fold it in.
        agent_input = message if use_session else _build_input(message, history)
        emitted = 0
        splitter = _VoiceSplitter()

        def _flush_tools() -> list[str]:
            nonlocal emitted
            lines = []
            while emitted < len(executor.captures):
                tname, structured = executor.captures[emitted]
                emitted += 1
                if structured is not None and tname != "callDispatch":
                    lines.append(_sse({"type": "tool_result", "toolName": tname, "result": structured}))
            return lines

        try:
            async for event in runner.run_stream(agent=agent, input=agent_input, session_id=session_id, user_id="operator"):
                for line in _flush_tools():
                    yield line
                if event.type == EventType.CONTENT_DELTA:
                    delta = event.data.get("content", "")
                    if delta:
                        for ev in splitter.feed(delta):
                            yield _sse(ev)
                elif event.type == EventType.RUN_ERROR:
                    logger.error(f"run_stream RUN_ERROR: {event.data}")
                    yield _sse({"type": "text", "content": "\n\n_(I hit an error processing that.)_"})
                    break
                elif event.type == EventType.RUN_END:
                    break

            for line in _flush_tools():
                yield line
            for ev in splitter.finish():
                yield _sse(ev)

            # If the agent deployed a mission this turn, run it in-process and
            # stream its progress/finding/complete events into the same SSE.
            deploy = next(
                (s for (n, s) in executor.captures
                 if n == "deployMission" and isinstance(s, dict)
                 and s.get("missionId") and not s.get("error")),
                None,
            )
            if deploy:
                from backend.missions import runner as mission_runner, store
                store.register(deploy["missionId"], deploy["type"])
                params = {}
                if deploy.get("driverName"):
                    params["driverName"] = deploy["driverName"]
                async for ev in mission_runner.run_mission(deploy["missionId"], deploy["type"], params):
                    yield _sse(ev)

            yield _sse({"type": "done"})
        except Exception as e:  # noqa: BLE001
            logger.error(f"Tasha stream error: {e}")
            yield _sse({"type": "text", "content": f"\n\n_(Connection error: {e})_"})
            yield _sse({"type": "done"})
        finally:
            try:
                await mcp.cleanup()
            except Exception:
                pass

    async def chat(self, message: str) -> str:
        if not self._initialized:
            await self.initialize()
        mcp, executor, agent, runner = await self._build_session(None)
        try:
            resp = await runner.run(agent=agent, input=message, user_id="operator")
            return resp.content or ""
        finally:
            try:
                await mcp.cleanup()
            except Exception:
                pass

    async def respond_voice(
        self, message: str, history: list | None = None, conversation_id: str | None = None
    ) -> dict:
        """Non-streaming turn for the voice pipeline.

        Returns {spoken, tools, deploy}: a short spoken summary (the <voice>
        block), the structured tool results (for rich cards), and any deployed
        mission intent (so the WS can stream the mission afterwards).
        """
        if not self._initialized:
            await self.initialize()
        mcp, executor, agent, runner = await self._build_session(None)
        session_id = await self._ensure_session(conversation_id)
        use_session = session_id is not None
        agent_input = message if use_session else _build_input(message, history)
        try:
            resp = await runner.run(agent=agent, input=agent_input, session_id=session_id, user_id="operator")
            content = resp.content or ""
            m = re.search(r"<voice>(.*?)</voice>", content, flags=re.S)
            spoken = m.group(1).strip() if m else re.sub(r"<voice>.*?</voice>\s*", "", content, flags=re.S).strip()
            tools = [(n, s) for (n, s) in executor.captures if s is not None and n not in ("deployMission", "callDispatch")]
            deploy = next(
                (s for (n, s) in executor.captures
                 if n == "deployMission" and isinstance(s, dict)
                 and s.get("missionId") and not s.get("error")),
                None,
            )
            dispatch = next(
                (s for (n, s) in executor.captures
                 if n == "callDispatch" and isinstance(s, dict) and s.get("action") == "dispatch_call"),
                None,
            )
            return {"spoken": spoken or "Here's what I found.", "tools": tools, "deploy": deploy, "dispatch": dispatch}
        finally:
            try:
                await mcp.cleanup()
            except Exception:
                pass


# Module-level singleton (lazy init on first request)
tasha = TashaAgent()
