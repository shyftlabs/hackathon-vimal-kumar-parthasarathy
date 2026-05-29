"""Speech-to-text via Smallest AI Pulse (per-utterance WebSocket)."""

from __future__ import annotations

import array
import asyncio
import json
import math
import os

import websockets

PULSE_URL = "wss://waves-api.smallest.ai/api/v1/pulse/get_text?language=en&sample_rate=16000&encoding=linear16"


class PulseSTT:
    """One Pulse WebSocket per utterance: connect -> send_audio* -> end_utterance.

    Pulse closes the socket after {type:"end"}, so a fresh instance/connection is
    used per utterance (matching the reference implementation).
    """

    # Auto-gain (matches the reference TS pipeline): boost quiet audio so Pulse can
    # transcribe even when the browser's echo cancellation suppresses the mic after TTS.
    _TARGET_RMS = 0.08
    _MAX_GAIN = 8.0
    _GAIN_SMOOTHING = 0.15

    def __init__(self) -> None:
        self._key = os.environ.get("SMALLEST_API_KEY")
        self._ws = None
        self._reader: asyncio.Task | None = None
        self._final = ""
        self._interim = ""
        self._got_response = False
        self._got_last = False
        self._last_emitted = ""
        self._gain = 1.0

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
                await self._ws.send(self._apply_gain(pcm))
            except Exception:
                pass

    def take_interim(self) -> str | None:
        """Best partial so far (accumulated final + latest interim), returned only when it
        changes — lets the session stream a live transcript to the client as the user speaks."""
        display = self._final
        if self._interim:
            display = (display + " " + self._interim).strip() if display else self._interim
        display = display.strip()
        if display and display != self._last_emitted:
            self._last_emitted = display
            return display
        return None

    def _apply_gain(self, pcm: bytes) -> bytes:
        """Adaptive gain toward TARGET_RMS, capped at MAX_GAIN. Returns the original bytes
        on any error so a gain bug can never break transcription."""
        try:
            samples = array.array("h")
            samples.frombytes(pcm)
            n = len(samples)
            if n == 0:
                return pcm
            acc = 0.0
            for v in samples:
                x = v / 32768.0
                acc += x * x
            raw = math.sqrt(acc / n)
            if raw > 0.001:
                ideal = min(self._TARGET_RMS / raw, self._MAX_GAIN)
                self._gain = self._gain * (1 - self._GAIN_SMOOTHING) + ideal * self._GAIN_SMOOTHING
            if self._gain < 1.2:
                return pcm
            g = self._gain
            out = array.array("h", samples)
            for i in range(n):
                amp = int(samples[i] * g)
                out[i] = 32767 if amp > 32767 else -32768 if amp < -32768 else amp
            return out.tobytes()
        except Exception:
            return pcm

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
