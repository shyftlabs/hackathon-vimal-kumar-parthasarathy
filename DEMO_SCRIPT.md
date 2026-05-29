# FleetShield AI — 3-Minute Demo Script (AgentShyft)

> Goal: prove a real problem + a sharp solution **built on Continuum**, in 3 minutes.
> Headline numbers (live in the app): **$523,470/yr saved · 936 t CO₂/yr · 18–32% premium cut · 7 burnout drivers flagged**.

## Pre-flight checklist (do this BEFORE you present)
1. Start everything: `./scripts/dev.sh` (MCP :8765, backend :3000, frontend :3001). Confirm http://localhost:3001/operator loads.
2. Sanity check Tasha: open `/operator/assistant`, ask "fleet overview" — cards + voice should work.
3. For the phone call: `ngrok http 3000` → set `PUBLIC_BASE_URL=<https url>` in `.env` → restart backend. Have your phone (the dispatcher) in hand, ringer ON.
4. Pre-load tabs: `/operator` (dashboard), `/operator/assistant`, `/driver-portal` (logged in as **405 / 7234** = Marcus Rivera).
5. Backup: have this script + a screen recording of the phone call in case the venue network blocks Twilio.

---

## The Script

### 0:00 — Problem (20s)  [slide or dashboard]
> "Trucking moves nine hundred forty billion dollars of freight a year — and bleeds money to a crisis hiding in plain sight: half a million crashes, eighty-seven percent driver turnover, insurers who can't see safety improvements so fleets overpay up to a third on premiums. The telematics data to fix this already exists. Nobody has time to turn it into decisions. **FleetShield AI does — and it's built entirely on Continuum.**"

### 0:20 — Tasha, the Continuum agent (40s)  [/operator/assistant]
- Type/say: **"Who's our riskiest driver and what's it costing us?"**
- Tasha speaks + renders the driver-risk card.
> "This is Tasha — a Continuum agent with fourteen tools over our live fleet data. She found Marcus Rivera, critical risk, twenty-five thousand dollars a year. Notice she's not just chatting — she pulled the real numbers and is offering to put an agent to work."

### 1:00 — Autonomous Mission Agent (45s)  [same screen]
- Say: **"Yes, deploy the Coaching Agent."**
- Watch live progress → findings → the executive report stream in.
> "That's an autonomous mission — a Continuum workflow running a multi-step analysis across the whole fleet: scanning risk, building per-driver coaching plans, cross-referencing trends, and writing an executive summary. Analyst work in thirty seconds. And it just pushed coaching tasks to those drivers' phones."

### 1:45 — Driver portal + the real phone call (60s)  [/driver-portal as Marcus]
- Show Marcus's home/score, then tap **"Call Dispatch"** with an issue (e.g. "running 2 hours late on load 4471").
- **Your phone rings.** Answer it. Tasha (the AI) speaks on the driver's behalf; you reply as the dispatcher; she confirms and wraps up.
> "When a driver needs dispatch, they don't text and drive — Tasha places a **real phone call** and handles it. That's my phone ringing. The AI is negotiating the delivery window with me, a human dispatcher, right now — and relaying the result back to the driver."

### 2:45 — Close (15s)  [/operator/roi]
> "Five hundred twenty-three thousand dollars saved a year, nine hundred thirty-six tons of CO₂, lives protected — an AI workforce for fleet safety, built start to finish on Continuum. Thank you."

---

## If something breaks (graceful fallbacks)
- **Phone call fails** (network/Twilio): show the recorded call clip; the on-screen transcript still tells the story.
- **Voice/mic issue:** use the text box — Tasha still answers with cards + the spoken summary plays back.
- **Mission slow:** keep narrating the live progress; it's the "watch the agent work" moment — slowness reads as depth.

## One-liners to have ready
- "Why Continuum?" → "The agent, the fourteen tools, the multi-step missions, multi-model routing, and observability are all Continuum primitives — we didn't build an agent framework, we built a product on one."
- "Is the data real?" → "It's a realistic mock fleet — 25 vehicles, 30 drivers, 90 days of telematics — so the demo is deterministic and the numbers are reproducible."
- "What's next?" → "Plug into a real telematics feed; the scoring engines and agent stay identical."
