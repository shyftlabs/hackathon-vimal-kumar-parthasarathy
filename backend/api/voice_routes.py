"""Voice routes — TTS synthesis (Smallest AI Waves)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.voice.tts import synthesize_speech

try:
    from orchestrator import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)

router = APIRouter()

# Cap synthesis input to avoid abuse / runaway cost.
_MAX_TTS_CHARS = 1500


@router.post("/api/tts/synthesize")
async def tts_synthesize(req: Request):
    body = await req.json()
    text = (body.get("text") or "").strip()[:_MAX_TTS_CHARS]
    if not text:
        return JSONResponse({"error": "no text"}, status_code=400)
    try:
        audio = await synthesize_speech(text)
        return Response(content=audio, media_type="audio/wav")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"TTS synthesis failed: {e}")  # detail stays server-side
        return JSONResponse({"error": "Speech synthesis is temporarily unavailable"}, status_code=502)
