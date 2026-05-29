#!/usr/bin/env bash
# Production start: fleet MCP server (internal :8765) + API on the platform's $PORT.
set -e
PORT="${PORT:-3000}"

echo "▶ Fleet MCP tool server (internal :8765) ..."
python -m backend.mcp_server.fleet_tools &
MCP_PID=$!

# Wait (best-effort) for the MCP server to accept connections before serving the API,
# so the agent's first request doesn't race the tool server. (curl on /mcp -> 406 = up.)
for _ in $(seq 1 30); do
  curl -s -o /dev/null "http://localhost:8765/mcp" && break || sleep 0.5
done

echo "▶ FleetShield API on :$PORT ..."
# exec so uvicorn is PID 1's child and receives signals; if it dies, the container restarts.
trap 'kill $MCP_PID 2>/dev/null || true' EXIT INT TERM
exec python -m uvicorn backend.api.server:app --host 0.0.0.0 --port "$PORT"
