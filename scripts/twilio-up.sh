#!/usr/bin/env bash
# Bring the Twilio dispatch call online:
#   1) ensure an ngrok tunnel to :3000 is running
#   2) write its public https URL into .env as PUBLIC_BASE_URL
# Then restart the backend so it picks up the new URL.
set -euo pipefail
cd "$(dirname "$0")/.."

# 1) Start ngrok if its local API isn't already up.
if ! curl -s http://localhost:4040/api/tunnels >/dev/null 2>&1; then
  echo "▶ Starting ngrok http 3000 ..."
  ngrok http 3000 > /tmp/ngrok.log 2>&1 &
  for i in $(seq 1 10); do curl -s http://localhost:4040/api/tunnels >/dev/null 2>&1 && break; sleep 1; done
fi

# 2) Grab the https public URL.
URL=$(curl -s http://localhost:4040/api/tunnels \
  | python3 -c "import sys,json; ts=json.load(sys.stdin)['tunnels']; print(next((t['public_url'] for t in ts if t['public_url'].startswith('https')), ''))")

if [ -z "$URL" ]; then
  echo "✗ Could not get an ngrok https URL. Check /tmp/ngrok.log"; exit 1
fi
echo "✓ Public URL: $URL"

# 3) Write PUBLIC_BASE_URL into .env (create the key if missing).
python3 - "$URL" <<'PY'
import re, sys
url = sys.argv[1]
path = ".env"
s = open(path).read()
if re.search(r'^PUBLIC_BASE_URL=', s, flags=re.M):
    s = re.sub(r'^PUBLIC_BASE_URL=.*$', f'PUBLIC_BASE_URL={url}', s, flags=re.M)
else:
    s += f'\nPUBLIC_BASE_URL={url}\n'
open(path, "w").write(s)
print(f"✓ .env updated: PUBLIC_BASE_URL={url}")
PY

echo ""
echo "▶ Now RESTART the backend so it loads the new URL:"
echo "   stop ./scripts/dev.sh (Ctrl-C) and re-run it, then tap 'Call Dispatch' in the driver portal."
