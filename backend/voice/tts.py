"""Text-to-speech via Smallest AI Waves (lightning-v3.1)."""

from __future__ import annotations

import os
import struct

import httpx

WAVES_TTS_URL = "https://waves-api.smallest.ai/api/v1/lightning-v3.1/get_speech"
DEFAULT_VOICE = os.environ.get("SMALLEST_VOICE_ID", "sophia")
SAMPLE_RATE = 24000


def wav_wrap(pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw little-endian PCM16 in a minimal WAV container (browser-decodable)."""
    n = len(pcm)
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    header = (
        b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
        + b"data" + struct.pack("<I", n)
    )
    return header + pcm


async def synthesize_pcm(text: str, voice_id: str | None = None, sample_rate: int = SAMPLE_RATE, speed: float = 1.0) -> bytes:
    """Return raw PCM16 audio bytes from Smallest AI Waves."""
    key = os.environ.get("SMALLEST_API_KEY")
    if not key:
        raise RuntimeError("SMALLEST_API_KEY not set")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            WAVES_TTS_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "text": text,
                "voice_id": voice_id or DEFAULT_VOICE,
                "sample_rate": sample_rate,
                "speed": speed,
                "add_wav_header": False,
            },
        )
        resp.raise_for_status()
        return resp.content


async def synthesize_speech(text: str, voice_id: str | None = None, sample_rate: int = SAMPLE_RATE, speed: float = 1.0) -> bytes:
    """Return WAV audio bytes (PCM wrapped in a WAV header) for browser playback."""
    pcm = await synthesize_pcm(text, voice_id=voice_id, sample_rate=sample_rate, speed=speed)
    # Some Waves responses already include a RIFF header; only wrap raw PCM.
    if pcm[:4] == b"RIFF":
        return pcm
    return wav_wrap(pcm, sample_rate=sample_rate)
