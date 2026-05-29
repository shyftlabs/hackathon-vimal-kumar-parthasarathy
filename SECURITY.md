# Security Posture — FleetShield AI

This is a hackathon build, engineered to a production-minded standard. This
document states what is hardened, the deliberate demo-time trade-offs, and the
roadmap to full production hardening.

## Secrets management
- **No secrets in source.** All credentials (Anthropic, Smallest AI, Twilio) live only in `.env`, which is **git-ignored** (`.gitignore` excludes `.env`, `.env.*`). Verified: `grep` finds zero hardcoded keys in `backend/` or `frontend/src/`.
- Secrets are loaded via `python-dotenv` at process start and read through environment variables — never logged, never returned in responses.
- `.env.example`-style guidance is in the README; the real `.env` is never committed.

## Transport & CORS
- **CORS is restricted** to the known frontend origins (`http://localhost:3001` by default), configurable via `ALLOWED_ORIGINS`. Not a wildcard.
- The Next.js frontend proxies `/api/*` to the backend **server-side** (`next.config.ts` rewrites), so browser→backend CORS is minimally exercised in practice.
- Production: terminate TLS at a reverse proxy / the platform edge; set `ALLOWED_ORIGINS` to the deployed domain.

## Telephony (Twilio) webhook security
- The public TwiML callbacks (`/twilio/voice`, `/twilio/gather`, `/twilio/status`) support **Twilio request-signature validation** (`X-Twilio-Signature`, HMAC over the public URL + params via `RequestValidator`).
- It is **gated by `TWILIO_VALIDATE_SIGNATURE`** (default off) so a freshly-rotated ngrok URL never breaks a live demo. **Enable it in production** once `PUBLIC_BASE_URL` is stable. Unsigned requests are rejected with `403 <Reject/>`.

## Input handling & injection
- **No SQL** (data is in-memory, deterministic mock) → no SQL injection surface.
- **No shell/`os.system`/`eval`** on user input → no command injection.
- **Tools are read-only analytics, with two bounded exceptions.** 13 of the agent's 15 tools only *read* fleet data and compute scores; `deployMission` only launches read-only analysis. The sole side-effecting tool is `callDispatch`, which places an outbound call **only to the pre-configured `DISPATCHER_NUMBER`** (never an attacker-supplied number) with bounded turns — so even a successful prompt injection cannot exfiltrate data, mutate records, run code, or dial an arbitrary destination. The **blast radius is limited to read-only fleet insights plus a call to the one trusted dispatcher line.**
- **TTS input is capped** (`_MAX_TTS_CHARS`) to bound abuse/cost; mission turns are bounded (`MAX_TURNS`); the agent has `max_turns` limits.
- Route inputs are validated (unknown driver/mission ids → `404`; bad driver PIN → `401`).

## LLM / agent safety
- Model access is via Continuum's gateway to the provider; the agent is scoped to fleet tools only.
- Session history is isolated per `conversationId` (Redis key-prefixed); no cross-tenant bleed for distinct conversation ids.
- Long-term memory (mem0) is **disabled** by default; when enabled it supports PII pre-store filtering and per-user scope isolation (`AgentMemoryScope.USER`).

## Frontend rendering
- The assistant renders the model's **own markdown** to HTML (`dangerouslySetInnerHTML`) and strips `<voice>` tags. The content is the model's output (not third-party user HTML), and the renderer emits a constrained tag set. Production hardening: run the output through a sanitizer (e.g. DOMPurify) for defense-in-depth against model-emitted HTML.

## Error handling
- Client-facing errors are **generic** ("temporarily unavailable"); exception detail is logged **server-side only**, never returned to the client.

## Dependencies
- `pip-audit` is clean except one **transitive** advisory: `mem0ai 1.0.11` (`CVE-2026-7597`). mem0 is Continuum's optional long-term-memory dependency and is **not in our runtime path** (memory is disabled — `MEMORY_ENABLED=false`), and it is **version-pinned by the framework** (`<2.0.0`). It will be picked up via Continuum's next release rather than force-upgrading against the framework's pin. Not exploitable in this configuration.

## Production hardening roadmap
1. **AuthN/AuthZ** on operator + driver routes (the demo is open for judging); add JWT/session auth + role checks; driver login is PIN-demo-only today.
2. **Rate limiting** (per-IP / per-token) on the agent, TTS, and dispatch endpoints.
3. **Enable** `TWILIO_VALIDATE_SIGNATURE=true` with a stable public URL.
4. **TLS everywhere**; secrets from a managed secret store with rotation.
5. **Output sanitization** for model-rendered HTML.
6. Continuum-native **Langfuse** tracing + audit logging for full observability.
7. Upgrade `mem0ai` when enabling long-term memory + the framework allows it.

## Responsible use
FleetShield AI is a defensive, safety-improving application: it coaches drivers, prevents incidents, and reduces emissions. It contains no offensive capabilities.
