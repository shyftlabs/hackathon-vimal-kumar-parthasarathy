"""Speech-to-text via Smallest AI Pulse (per-utterance WebSocket)."""

from __future__ import annotations

import asyncio
import json
import os

import websockets

PULSE_URL = "wss://waves-api.smallest.ai/api/v1/pulse/get_text?language=en&sample_rate=16000&encoding=linear16"


class PulseSTT:
    """One Pulse WebSocket per utterance: connect -> send_audio* -> end_utterance.

    Pulse closes the socket after {type:"end"}, so a fresh instance/connection is
    used per utterance (matching the reference implementation).
    """

    def __init__(self) -> None:
        self._key = os.environ.get("SMALLEST_API_KEY")
        self._ws = None
        self._reader: asyncio.Task | None = None
        self._final = ""
        self._interim = ""
        self._got_response = False
        self._got_last = False

    async def connect(self) -> None:
        if not self._key:
            raise RuntimeError("SMALLEST_API_KEY not set")
        self._ws = await websockets.connect(
            PULSE_URL, additional_headers={"Authorization": f"Bearer {self._key}"}, max_size=None
        )
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                self._got_response = True
                text = msg.get("transcript") or msg.get("text")
                if not text:
                    continue
                if msg.get("is_final"):
                    if not self._got_last:
                        ft = text.strip()
                        if ft:
                            self._final += (" " if self._final else "") + ft
                        if msg.get("is_last"):
                            self._got_last = True
                else:
                    self._interim = text.strip()
        except Exception:
            pass

    async def send_audio(self, pcm: bytes) -> None:
        if self._ws is not None:
            try:
                await self._ws.send(pcm)
            except Exception:
                pass

    async def end_utterance(self) -> str:
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "end"}))
            except Exception:
                pass
            await asyncio.sleep(0.3 if self._got_response else 0.8)
        text = (self._final.strip() or self._interim.strip())
        await self.close()
        return text

    async def close(self) -> None:
        if self._reader:
            self._reader.cancel()
            self._reader = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
