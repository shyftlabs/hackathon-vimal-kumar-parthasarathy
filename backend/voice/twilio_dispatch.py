"""
Real two-way dispatch phone call via Twilio.

Design: instead of raw Media Streams (μ-law/resampling — fragile to demo live), we
use Twilio's built-in speech <Gather> + <Say>, with a Continuum "driver advocate"
agent driving the conversation. The AI places a REAL outbound call to the human
dispatcher, speaks the driver's request, listens to the dispatcher's spoken reply
(Twilio STT), responds, and wraps up — a genuine two-way conversation. The live
transcript is polled by the driver portal's dispatch overlay.

Runtime requirements: TWILIO_* env vars, a DISPATCHER_NUMBER to call, and a public
HTTPS base URL (PUBLIC_BASE_URL, e.g. an ngrok tunnel) so Twilio can fetch the TwiML
callbacks.
"""

from __future__ import annotations

import os
import uuid

from backend.data.seed_data import get_driver

try:
    from orchestrator import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)

# Per-call conversation state, keyed by an opaque call key (also our callId).
# { key: {callId, callSid, driverId, driverName, intent, transcript:[{role,text}],
#         state, turns, ended} }
_calls: dict[str, dict] = {}

MAX_TURNS = 8


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    return v.strip() if v else None


def is_configured() -> bool:
    return bool(_env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN") and _env("TWILIO_NUMBER"))


def validate_request(path_with_query: str, params: dict, signature: str | None) -> bool:
    """Verify a Twilio webhook via X-Twilio-Signature (HMAC over the public URL + params).

    Gated by TWILIO_VALIDATE_SIGNATURE (default off, so a fresh ngrok URL doesn't
    break the live demo). Enable in production once PUBLIC_BASE_URL is stable.
    """
    if os.environ.get("TWILIO_VALIDATE_SIGNATURE", "false").lower() != "true":
        return True
    token = _env("TWILIO_AUTH_TOKEN")
    public = _env("PUBLIC_BASE_URL")
    if not (token and public):
        return False
    try:
        from twilio.request_validator import RequestValidator
        full_url = public.rstrip("/") + path_with_query
        return RequestValidator(token).validate(full_url, params, signature or "")
    except Exception:  # noqa: BLE001
        return False


def _twilio_client():
    from twilio.rest import Client
    return Client(_env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN"))


def get_call(call_id: str) -> dict | None:
    return _calls.get(call_id)


def call_status(driver_id: str, call_id: str) -> dict:
    c = _calls.get(call_id)
    if not c:
        return {"callId": call_id, "state": "not_found", "transcript": []}
    return {
        "callId": call_id,
        "state": c["state"],
        "transcript": c["transcript"],
        "summary": c.get("summary"),
    }


def start_call(driver_id: str, intent: str) -> dict:
    """Place the outbound call. Returns {mode, callId, state, ...}."""
    driver = get_driver(driver_id)
    driver_name = driver.name if driver else "the driver"
    dispatcher = _env("DISPATCHER_NUMBER")
    public = _env("PUBLIC_BASE_URL")

    if not is_configured():
        return {"mode": "unconfigured", "state": "error",
                "message": "Twilio is not configured (set TWILIO_* in .env)."}
    if not dispatcher:
        return {"mode": "unconfigured", "state": "error",
                "message": "No DISPATCHER_NUMBER set to call."}
    if not public:
        return {"mode": "needs_public_url", "state": "error",
                "message": "Set PUBLIC_BASE_URL (e.g. an ngrok https URL) so Twilio can reach the TwiML callbacks."}

    key = f"call-{uuid.uuid4().hex[:10]}"
    _calls[key] = {
        "callId": key, "callSid": None, "driverId": driver_id, "driverName": driver_name,
        "intent": intent or "a load update", "transcript": [], "state": "connecting",
        "turns": 0, "ended": False, "summary": None,
    }
    try:
        client = _twilio_client()
        call = client.calls.create(
            to=dispatcher,
            from_=_env("TWILIO_NUMBER"),
            url=f"{public}/twilio/voice?key={key}",
            method="POST",
            status_callback=f"{public}/twilio/status?key={key}",
            status_callback_event=["completed", "no-answer", "busy", "failed"],
            status_callback_method="POST",
        )
        _calls[key]["callSid"] = call.sid
        logger.info(f"Dispatch call placed: {call.sid} -> {dispatcher} (driver {driver_id})")
        return {"mode": "twilio", "callId": key, "callSid": call.sid, "state": "connecting"}
    except Exception as e:  # noqa: BLE001
        logger.error(f"Twilio call failed: {e}")
        _calls[key]["state"] = "error"
        return {"mode": "twilio", "callId": key, "state": "error", "message": str(e)}


def hangup(call_id: str) -> None:
    c = _calls.get(call_id)
    if not c or not c.get("callSid"):
        return
    try:
        _twilio_client().calls(c["callSid"]).update(status="completed")
    except Exception:
        pass
    c["state"] = "complete"
    c["ended"] = True


def mark_status(call_id: str, twilio_status: str) -> None:
    c = _calls.get(call_id)
    if not c:
        return
    if twilio_status in ("completed", "no-answer", "busy", "failed"):
        c["state"] = "complete" if twilio_status == "completed" else "error"
        c["ended"] = True


# ─── Driver-advocate conversation (Continuum LLM) ─────────────

_ADVOCATE_SYS = (
    "You are Tasha, an AI assistant placing a REAL phone call to a human freight dispatcher "
    "ON BEHALF OF a truck driver. Speak naturally and briefly, like a real phone call — one or "
    "two sentences per turn. You are polite, professional, and efficient. Your goal is to relay "
    "the driver's request and get the dispatcher's decision/answer. Do NOT mention you are an AI "
    "unless asked. When the matter is resolved (the dispatcher has acknowledged or answered), "
    "thank them and end with the token [END_CALL] on its own at the very end of your message."
)


async def _advocate_line(call: dict, opening: bool) -> str:
    from orchestrator.core.container import get_container
    from orchestrator.llm.config import LLMConfig

    model = os.environ.get("DEFAULT_LLM_MODEL", "claude-sonnet-4-5")
    if opening:
        user = (f"You are calling the dispatcher now. Open the call: greet them, say you're calling on "
                f"behalf of driver {call['driverName']}, and relay this request: \"{call['intent']}\". "
                f"Keep it to 2 short sentences and end by asking for their help/decision.")
        messages = [{"role": "system", "content": _ADVOCATE_SYS}, {"role": "user", "content": user}]
    else:
        convo = "\n".join(f"{m['role']}: {m['text']}" for m in call["transcript"])
        messages = [
            {"role": "system", "content": _ADVOCATE_SYS},
            {"role": "user", "content": (
                f"Driver: {call['driverName']}. Original request: \"{call['intent']}\".\n\n"
                f"Call so far:\n{convo}\n\nGive your next spoken line (1-2 sentences). "
                f"If the dispatcher has resolved or answered the request, wrap up and append [END_CALL].")},
        ]
    try:
        llm = get_container().llm_client
        resp = await llm.chat(messages=messages, config=LLMConfig(model=model, max_tokens=160), auto_session=False)
        return (resp.content or "").strip() if resp else ""
    except Exception as e:  # noqa: BLE001
        logger.warning(f"advocate LLM failed: {e}")
        return ("Thanks for taking the call — I'll have the driver follow up directly. [END_CALL]"
                if not opening else
                f"Hi, this is an assistant calling on behalf of driver {call['driverName']} about {call['intent']}. Can you help?")


def _twiml_say_gather(call_id: str, text: str) -> str:
    from twilio.twiml.voice_response import VoiceResponse

    public = _env("PUBLIC_BASE_URL")
    vr = VoiceResponse()
    ended = "[END_CALL]" in text
    spoken = text.replace("[END_CALL]", "").strip()
    vr.say(spoken, voice="Polly.Joanna")
    if ended:
        vr.hangup()
    else:
        vr.gather(
            input="speech", speech_timeout="auto", action=f"{public}/twilio/gather?key={call_id}",
            method="POST", speech_model="experimental_conversations",
        )
        # If no speech captured, re-prompt once then hang up.
        vr.say("I didn't catch that. I'll have the driver follow up. Thank you.", voice="Polly.Joanna")
        vr.hangup()
    return str(vr)


async def opening_twiml(call_id: str) -> str:
    c = _calls.get(call_id)
    if not c:
        from twilio.twiml.voice_response import VoiceResponse
        vr = VoiceResponse()
        vr.say("Sorry, this call could not be set up.", voice="Polly.Joanna")
        vr.hangup()
        return str(vr)
    c["state"] = "on_call"
    line = await _advocate_line(c, opening=True)
    c["transcript"].append({"role": "ava", "text": line.replace("[END_CALL]", "").strip()})
    return _twiml_say_gather(call_id, line)


async def gather_twiml(call_id: str, speech_result: str) -> str:
    c = _calls.get(call_id)
    if not c:
        from twilio.twiml.voice_response import VoiceResponse
        vr = VoiceResponse()
        vr.hangup()
        return str(vr)

    if speech_result:
        c["transcript"].append({"role": "dispatcher", "text": speech_result})
    c["turns"] += 1

    if c["turns"] >= MAX_TURNS:
        c["state"] = "complete"
        c["ended"] = True
        from twilio.twiml.voice_response import VoiceResponse
        vr = VoiceResponse()
        vr.say("Thank you, that's all I needed. Have a great day.", voice="Polly.Joanna")
        vr.hangup()
        c["transcript"].append({"role": "ava", "text": "Thank you, that's all I needed. Have a great day."})
        return str(vr)

    line = await _advocate_line(c, opening=False)
    c["transcript"].append({"role": "ava", "text": line.replace("[END_CALL]", "").strip()})
    if "[END_CALL]" in line:
        c["state"] = "complete"
        c["ended"] = True
    return _twiml_say_gather(call_id, line)
