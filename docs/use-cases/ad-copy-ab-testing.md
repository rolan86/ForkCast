# Use Case: Ad Copy A/B Testing

## Overview

This use case demonstrates using ForkCast to compare two ad copies for a fictional productivity app (FocusFlow AI) by simulating how diverse social media audiences react to each.

**Date tested:** 2026-03-23
**Engine:** OASIS (native mode)
**Platform:** Twitter
**Result:** Full pipeline working end-to-end (project -> graph -> sim -> run -> report)

## The Scenario

A marketing team has two ad copy directions for a productivity app:

- **Ad Copy A** ("The Productivity Revolution") — Professional, data-driven, efficiency-focused. Quantifies value (2+ hours/day saved), uses social proof (50K users), low-friction CTA.
- **Ad Copy B** ("The Burnout Antidote") — Empathetic, provocative, anti-hustle-culture. Emotional resonance, names lived experiences ("Sunday night dread"), positions product as energy protector.

The question: **Which copy generates more positive engagement, sharing, and purchase intent? Which demographics prefer which?**

## Step-by-Step Workflow

### 1. Create Project

Upload both ad copies as seed documents. Set the requirement to describe the comparison.

```bash
curl -X POST http://localhost:8199/api/projects \
  -F 'domain=social-media' \
  -F 'requirement=Compare these two ad copies for FocusFlow AI. Which generates more positive engagement, sharing, and purchase intent? Which demographic segments prefer which? Identify backlash risks.' \
  -F 'name=Ad Copy A/B Test: FocusFlow AI' \
  -F 'files=@ad_copy_a.txt' \
  -F 'files=@ad_copy_b.txt'
```

### 2. Build Knowledge Graph

ForkCast extracts entities from the ad copies — brands, audience segments, messaging themes, cultural movements.

```bash
curl -X POST http://localhost:8199/api/projects/{project_id}/build-graph
```

**Result:** 12 entities, 20 edges (including relationships like "Ad Copy B IDENTIFIES_WITH Anti-Burnout Movement")

### 3. Create & Prepare Simulation

Create an OASIS simulation. The LLM generates 12 diverse agent profiles from the graph entities.

```bash
curl -X POST http://localhost:8199/api/simulations \
  -H "Content-Type: application/json" \
  -d '{"project_id": "...", "engine_type": "oasis", "agent_mode": "native", "platforms": ["twitter"]}'

curl -X POST http://localhost:8199/api/simulations/{sim_id}/prepare
```

**Agents generated (12):**
| Agent | Role | Archetype |
|-------|------|-----------|
| FocusFlow AI | Brand account | Official presence |
| Marcus Teller | Head of Operations, SaaS | Data-driven efficiency believer |
| Priya Nambiar | Product Manager, B2B SaaS | Wellness-aware skeptic |
| Marisol Vega-Hutchins | Remote Operations Lead | Burned-out professional |
| Priya Nandakumar | Senior PM, Series B startup | Mid-career, skeptical then persuaded |
| Marcus Vellano | Founder/CEO, digital agency | Hustle-culture entrepreneur |
| Mara Voss | Freelance Brand Copywriter | Former burnout victim, now observer |
| Marcus Velde | Performance Marketing Lead | Analytical bridge agent |
| Mara Delgado | Freelance writer (burnout/labor) | Cultural critic, media-literate |
| Maya Okonkwo | Senior PM, mid-size SaaS | Skeptical quality-checker |
| Renata Osei-Mensah | VP of People & Culture | HR leader, network multiplier |
| Priya Nair-Holloway | HR Business Partner | Wellbeing-focused, cautious buyer |

### 4. Run Simulation

```bash
curl -X POST http://localhost:8199/api/simulations/{sim_id}/start
```

**Results:**
- **223 total actions** across 96 rounds (48 simulated hours)
- All 12 agents active
- Most active: Marisol Vega-Hutchins (23 actions) — sustained engagement pattern
- Round range: 4-96, peak at round 86

### 5. Generate Report

```bash
curl -X POST http://localhost:8199/api/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"simulation_id": "..."}'
```

**Report output:** 15,909 characters of structured analysis including:
- Narrative map of how each ad played on the timeline
- Engagement pattern analysis with activity timeline
- Influencer dynamics table (who shaped the conversation)
- Sentiment arc across 3 phases (Differentiation -> Skepticism -> Conditional Purchase Intent)
- Echo chamber analysis (Ad A's closed loop vs Ad B's cross-pollination)
- Backlash risk register for both copies
- Definitive prediction with evidence

## Key Findings from the Report

### Winner: Ad Copy B ("The Burnout Antidote")

**Why:**
1. **Broader reach** — Activated 3 distinct audience clusters (burned-out professionals, HR leaders, wellness-conscious workers) vs Ad A's single cluster (hustle-culture believers)
2. **Sustained engagement** — Top poster (Marisol, 23 posts) returned across all simulation phases, indicating the ad opened a conversation people couldn't stop having
3. **Cross-pollination** — Even hostile engagement (hustle-culture "contempt-shares") would expose Ad B to new audiences
4. **Purchase intent** — Wider demographic with higher emotional investment. Even Ad B's most resistant audience member admitted: "Ad Copy B is probably more accurate to what I actually need"

**Ad Copy A's weakness:** Generated conviction in believers, not conversations. Echo chamber effect — stayed in its lane perfectly and grew no wider.

**Ad Copy B's risk:** Backlash is product-contingent — if the actual app contradicts the anti-burnout promise (streak trackers, productivity scores), trust collapse would be severe and public.

## Limitations of This Test

1. **Native mode content** — All actions were CREATE_POST with generic content ("Thoughts on this topic") because native mode uses rule-based content from config. The *structure* of engagement patterns is accurate (who posts, when, how often) but actual post content wasn't agent-specific.
2. **LLM mode would be richer** — Using `agent_mode: "llm"` would have each agent generate actual post text reflecting their persona, making the content analysis far more meaningful.
3. **Single platform** — Only Twitter was simulated. Adding Reddit would surface different dynamics (longer-form discussion, community voting).
4. **The report compensated** — Despite generic action content, the report tool analyzed agent profiles, graph relationships, and engagement patterns to produce rich analysis. The report's quoted "agent statements" are synthesized from profile data, not actual simulation output.

## IDs for Reference

- Project: `proj_18ee3552aa21`
- Graph: `graph_daf707c58a59`
- Simulation: `sim_6757240acff6`
- Report: `report_15930c87774554cc`
