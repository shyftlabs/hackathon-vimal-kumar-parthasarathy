# AgentShyft Hackathon — Reference Guide

> **IMPORTANT: Every agent/session MUST read this file before making changes.**
> Single source of truth for competition rules, goals, judging, and our strategy.

## The Event
- **AgentShyft Hackathon** — hosted by **ShyftLabs** (Toronto Tech Week).
- **Date:** Friday, **May 29, 2026**, 9:30 AM – 5:00 PM + Happy Hour.
- **Venue:** 100 Yonge St #1501, Toronto, ON.
- **Theme:** Build with **Agentic AI** — not talk about it. Build it live, on the ShyftLabs **Continuum** framework.

## Schedule (event day)
| Time | Activity |
|------|----------|
| 9:30 AM | Arrival |
| 10:00–11:00 AM | **Continuum demo** (learn the framework / get access) |
| 11:00 AM–4:00 PM | **Build time** (5 hours) |
| 1:30 PM | Lunch (30 min) |
| 4:00–5:00 PM | **Presentations** — 3-minute live demo per team |
| 5:00 PM+ | Happy Hour |

## Prizes ($6,000 pool) — **WE ARE TARGETING 1st**
| Place | Amount |
|-------|--------|
| **1st** | **$3,000** |
| 2nd | $2,000 |
| 3rd | $1,000 |

Strong concepts may also unlock follow-on **funding opportunities**.

## Rules (non-negotiable)
- **Build on Continuum** (ShyftLabs' agent framework) — it must be genuinely central.
- **Create everything from scratch on the day** — no pre-built projects.
- Team size: **1–3 members**.
- Deliver a **3-minute live demo** to the judges.

## What Judges Want
1. **A product built entirely on the day.**
2. **A real problem with a clear solution.**
3. **A sharp, compelling 3-minute pitch.**
4. (Theme) **Genuine agentic AI** — autonomous, multi-step, tool-using agents on Continuum.

## Our Idea (submitted & accepted)
> **FleetShield AI** — the intelligence layer that transforms raw fleet telematics into **money saved, lives protected, and a planet preserved** — with two AI assistants, autonomous mission agents, and **real phone calls to dispatch**.

This concept previously **won a Geotab hackathon**. For AgentShyft we rebuild it from scratch on **Continuum**, with self-contained **mock telematics** (no Geotab) and Continuum as the agent brain.

## The Problem (lead the pitch with this)
Commercial trucking moves **$940B** in freight/year and bleeds money to a hidden crisis:
- **500,000+** large-truck crashes/year (FMCSA), avg **$91,000**/incident.
- Insurers can't see behavioral improvement → fleets **overpay 18–32%** on premiums.
- **87%** annual driver turnover (ATA); each replacement costs **$35,000+**.
- Driver life expectancy **61 years** (16 below average); 25% report chronic loneliness.
- **444M metric tons CO₂/year** from trucking, with billions in avoidable fuel waste.

The data to prevent all of this already exists in telematics — but managers drown in raw data with no way to turn it into decisions, dollars, or impact.

## Our Solution
FleetShield AI turns telematics into three things managers need:
1. **Money saved** — quantified insurance reductions, accident-prevention, and fuel savings in exact dollars.
2. **Lives protected** — predictive safety that flags at-risk drivers/corridors *before* incidents; proactive wellness + HOS.
3. **Planet preserved** — driving behavior → CO₂ metrics, EV-transition readiness, decarbonization actions.

**For managers:** not dashboards — an **AI workforce**. **Tasha** (a Continuum agent) answers fleet questions with rich visual cards, and **Autonomous Mission Agents** take an assignment ("run a coaching sweep"), execute a multi-step analysis across the fleet, and deliver a report — analyst work in minutes.

**For drivers:** a **voice-first AI companion** that coaches instead of surveils, and when a driver needs dispatch, places a **real phone call** to a human dispatcher and handles the conversation.

## Impact Numbers (target — calibrated into the mock data)
| Metric | Value |
|--------|-------|
| Potential annual fleet savings | **$521,600** |
| CO₂ reduction (sustainability recs) | **992 tons/year** |
| Insurance premium reduction | **18–32%** |
| Identified savings (safety+retention+fuel) | **$147,000** |
| Analyst work replaced by Mission Agents | **15–20 hrs/week** |
| Drivers coached by AI, not surveilled | **30** |

## Why We Win on Continuum
- **Tasha = a Continuum `BaseAgent`** with 15 MCP tools, streaming rich cards + a spoken summary.
- **Autonomous missions = Continuum-orchestrated**, multi-step, deployed by the agent and streamed live.
- **Real outbound Twilio call** driven by a Continuum dispatcher agent — the showstopper.
- Built-in **multi-LLM routing, memory, and Langfuse observability** demonstrate the platform's depth.

## Recommended 3-Minute Demo Flow
1. **Problem (20s):** the $940B crisis hiding in telematics.
2. **Tasha (45s):** ask "who's our riskiest driver and what's it costing us?" → rich cards + spoken answer.
3. **Mission Agent (45s):** "deploy the Coaching Agent" → watch it work live → executive report with dollar impact.
4. **Driver portal + voice (30s):** driver talks to Tasha hands-free.
5. **Real phone call (30s):** driver taps "call dispatch" → a **real phone rings** → agent handles it → transcript relayed.
6. **Close (10s):** the numbers — $521,600 saved, 992 tons CO₂, built entirely on Continuum.

## Pitfalls to Avoid
- Over-polishing UI at the expense of a working demo.
- Letting Continuum feel bolted-on — make the agent + missions genuinely central.
- No backup plan for the live phone call (have a recorded fallback).
- Reciting data the cards already show — keep the spoken pitch tight.
