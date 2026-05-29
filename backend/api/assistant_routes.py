"""Assistant + chat routes — Tasha (Continuum agent) over SSE."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.agent.tasha import tasha

router = APIRouter()

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


@router.post("/api/assistant/stream")
async def assistant_stream(req: Request):
    body = await req.json()
    message = body.get("message", "")
    current_page = body.get("currentPage")
    history = body.get("history") or []
    conversation_id = body.get("conversationId")
    return StreamingResponse(
        tasha.stream_assistant(message, current_page, history, conversation_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/api/chat/stream")
async def chat_stream(req: Request):
    body = await req.json()
    message = body.get("message", "")
    current_page = body.get("currentPage")
    history = body.get("history") or []
    conversation_id = body.get("conversationId")
    return StreamingResponse(
        tasha.stream_assistant(message, current_page, history, conversation_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    text = await tasha.chat(message)
    return JSONResponse({"response": text})
