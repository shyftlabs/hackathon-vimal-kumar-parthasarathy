# ── FleetShield AI backend (FastAPI + Continuum + MCP) for Railway/Render/Fly/VM ──
# Runs the fleet MCP tool server (internal :8765) and the API (public $PORT) together.
FROM python:3.13-slim

# Build tools (some Continuum deps build from sdist) + curl for the MCP readiness probe.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Continuum is pulled from its public repo so the image is self-contained
# (the local ./continuum-src is git-ignored and not in the build context).
RUN pip install --no-cache-dir "git+https://github.com/shyftlabs/continuum.git"

# App runtime deps (mirror the local venv extras).
RUN pip install --no-cache-dir \
        fastapi "uvicorn[standard]" httpx twilio python-multipart sse-starlette \
        audioop-lts websockets

COPY backend ./backend
COPY scripts/start-prod.sh ./scripts/start-prod.sh
RUN chmod +x ./scripts/start-prod.sh

# Railway/Render inject $PORT; the API binds it. MCP stays internal on 8765.
EXPOSE 3000
CMD ["./scripts/start-prod.sh"]
