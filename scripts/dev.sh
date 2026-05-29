#!/usr/bin/env bash
# Start all FleetShield AI services for local dev:
#   - Redis (Continuum sessions) :6380
#   - Fleet MCP tool server      :8765
#   - Backend API + Tasha        :3000
#   - Next.js frontend           :3001
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# Redis powers Continuum's session-backed conversation history. Start it on 6380
# if not already running (install once with `brew install redis`).
if command -v redis-cli >/dev/null 2>&1 && ! redis-cli -p 6380 ping >/dev/null 2>&1; then
  echo "▶ Redis (sessions)       → localhost:6380"
  redis-server --port 6380 --daemonize yes >/dev/null 2>&1 || echo "  (redis not started — sessions will fall back to in-context history)"
fi

echo "▶ Fleet MCP tool server  → http://localhost:8765/mcp"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m backend.mcp_server.fleet_tools &
MCP_PID=$!

echo "▶ Backend API + Tasha    → http://localhost:3000"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m uvicorn backend.api.server:app --host 0.0.0.0 --port 3000 &
API_PID=$!

echo "▶ Frontend (Next.js)     → http://localhost:3001"
( cd "$ROOT/frontend" && npm run dev ) &
FE_PID=$!

echo "PIDs: MCP=$MCP_PID  API=$API_PID  FE=$FE_PID"
trap 'kill $MCP_PID $API_PID $FE_PID 2>/dev/null || true' EXIT INT TERM
wait
