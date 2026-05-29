"""
Voice session handler for the /ws WebSocket (operator + driver hands-free voice).

Protocol (matches frontend/src/lib/voice-client.ts):
  client -> {type:start_session, driverId?} | {type:speech_start} | binary PCM16 frames
            | {type:speech_end} | {type:dispatch_call_start} | {type:dispatch_call_hangup}
            | {type:end_session}
  server -> {type:state_change,state} | {type:transcript,role,text}
            | {type:tool_result,toolName,result} | {type:audio_chunk,audio(base64 WAV)}
            | {type:mission_progress|finding|complete,...} | {type:error,message}
            | dispatch_* (Twilio — see backend/voice/twilio_dispatch.py)
"""

from __future__ import annotations

import base64
import json
import uuid

from starlette.websockets import WebSocketDisconnect

from backend.agent.tasha import tasha
from backend.voice.stt import PulseSTT
from backend.voice.tts import synthesize_pcm, wav_wrap

try:
    from orchestrator import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


async def handle_voice_ws(ws) -> None:
    await ws.accept()
    stt: PulseSTT | None = None
    driver_id: str | None = None
    conversation_id = f"voice-{uuid.uuid4().hex[:12]}"  # one voice session = one conversation

    async def send(obj: dict) -> None:
        await ws.send_text(json.dumps(obj))

    await send({"type": "state_change", "state": "listening"})

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break

            # Binary audio frame -> stream to STT, and forward any live partial transcript
            if msg.get("bytes") is not None:
                if stt is not None:
                    await stt.send_audio(msg["bytes"])
                    partial = stt.take_interim()
                    if partial:
                        logger.debug(f"[voice] partial: {partial[:60]!r}")
                        await send({"type": "partial_transcript", "role": "user", "text": partial})
                continue

            text = msg.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except Exception:
                continue
            t = data.get("type")

            if t == "start_session":
                driver_id = data.get("driverId")
                logger.info(f"[voice] start_session driverId={driver_id} conv={conversation_id}")
            elif t == "speech_start":
                if stt is None:
                    stt = PulseSTT()
                    try:
                        await stt.connect()
                        logger.info("[voice] speech_start — Pulse STT connected")
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"STT connect failed: {e}")
                        stt = None
                        await send({"type": "error", "message": "Voice transcription unavailable."})
            elif t == "speech_end":
                if stt is None:
                    continue
                try:
                    transcript = await stt.end_utterance()
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"STT end failed: {e}")
                    transcript = ""
                stt = None
                logger.info(f"[voice] speech_end — final transcript: {transcript!r}")
                await send({"type": "transcript", "role": "user", "text": transcript})
                if not transcript.strip():
                    await send({"type": "state_change", "state": "listening"})
                    continue

                await send({"type": "state_change", "state": "thinking"})
                msg_for_agent = transcript
                if driver_id:
                    msg_for_agent = f"[Driver {driver_id} is speaking.] {transcript}"
                try:
                    result = await tasha.respond_voice(msg_for_agent, conversation_id=conversation_id)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"voice respond failed: {e}")
                    await send({"type": "error", "message": "I hit an error. Please try again."})
                    await send({"type": "state_change", "state": "listening"})
                    continue

                for name, res in result["tools"]:
                    await send({"type": "tool_result", "toolName": name, "result": res})
                await send({"type": "transcript", "role": "assistant", "text": result["spoken"]})

                # Speak the response
                await send({"type": "state_change", "state": "speaking"})
                try:
                    pcm = await synthesize_pcm(result["spoken"])
                    audio_b64 = base64.b64encode(wav_wrap(pcm)).decode()
                    await send({"type": "audio_chunk", "audio": audio_b64})
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"TTS failed: {e}")

                # Stream a deployed mission, if any
                deploy = result.get("deploy")
                if deploy:
                    from backend.missions import runner as mission_runner, store
                    store.register(deploy["missionId"], deploy["type"])
                    params = {}
                    if deploy.get("driverName"):
                        params["driverName"] = deploy["driverName"]
                    async for ev in mission_runner.run_mission(deploy["missionId"], deploy["type"], params):
                        await send(ev)

                # If Tasha decided to contact dispatch this turn, place the REAL call now.
                dispatch = result.get("dispatch")
                if dispatch:
                    from backend.voice import twilio_dispatch
                    logger.info(f"[voice] callDispatch -> placing call: {dispatch.get('intent')!r}")
                    res = twilio_dispatch.start_call(driver_id or "d1", dispatch.get("intent") or "a load update")
                    await send({"type": "dispatch_call_state", "callState": res.get("state"),
                                "phase": "connecting", "callId": res.get("callId")})
                    if res.get("state") == "error":
                        await send({"type": "dispatch_call_ended",
                                    "reason": res.get("message", "error"), "callId": res.get("callId")})

                await send({"type": "state_change", "state": "listening"})

            elif t == "dispatch_call_start":
                from backend.voice import twilio_dispatch
                res = twilio_dispatch.start_call(driver_id or "d1", data.get("intent") or "a load update")
                await send({"type": "dispatch_call_state", "callState": res.get("state"),
                            "phase": "connecting", "callId": res.get("callId")})
                if res.get("state") == "error":
                    await send({"type": "dispatch_call_ended",
                                "reason": res.get("message", "error"), "callId": res.get("callId")})
            elif t == "dispatch_call_hangup":
                from backend.voice import twilio_dispatch
                cid = data.get("callId")
                if cid:
                    twilio_dispatch.hangup(cid)
            elif t == "end_session":
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        logger.error(f"voice ws error: {e}")
    finally:
        if stt is not None:
            await stt.close()
