# Use Case: Prediction Markets — Tesla Q2 2026 Forecast

## Overview

This use case demonstrates using ForkCast to simulate how diverse financial market participants would interpret Tesla's Q1 2026 earnings data and forecast the stock's Q2 direction.

**Date tested:** 2026-04-01
**Engine:** Claude (tool-use)
**Platform:** Twitter
**LLM Provider:** Ollama (llama3.1, fully local — zero API cost)
**Result:** Full pipeline working end-to-end (project -> graph -> sim -> run -> report)

## The Scenario

Tesla has just released its Q1 2026 10-Q showing mixed signals: revenue beat expectations at $28.4B (+12% YoY), but automotive gross margins compressed to 16.8% due to aggressive price cuts. Energy storage revenue surged 89% to $2.1B. The stock sits at $178.50, down 23% from its January high.

Two seed documents were provided:
- **Tesla Q1 2026 10-Q summary** — Financial data, segment breakdowns, management guidance
- **FinTwit market commentary** — 8 diverse commentator perspectives ranging from bullish (CathieWoodFan: "Energy storage is the next AWS") to bearish (PermaBearPete: "Classic margin death spiral")

The question: **What is the likely direction and magnitude of Tesla stock price movement over Q2 2026?**

## Step-by-Step Workflow

### 1. Create Project

Upload the financial documents as seed data with a market prediction requirement.

```bash
forkcast project create \
  --name "Tesla Q2 2026 Forecast" \
  --domain prediction-markets \
  --requirement "Based on Tesla Q1 2026 earnings and current market conditions, predict the likely direction and magnitude of TSLA stock price movement over Q2 2026."
```

### 2. Build Knowledge Graph

ForkCast extracts financial entities — companies, metrics, market indicators, analysts, and their relationships.

```bash
forkcast project build-graph {project_id}
```

**Result:** Entities extracted including Tesla, key financial metrics (gross margin, revenue segments), market participants, and thematic relationships (price war dynamics, energy storage growth narrative).

### 3. Create & Prepare Simulation

Create a simulation. The LLM generates 37 diverse agent profiles from graph entities, each representing a distinct market archetype.

```bash
forkcast sim create {project_id} --platforms twitter
forkcast sim prepare {simulation_id} --provider ollama --model llama3.1
```

**Agents generated (37):**

The domain's entity types drove persona generation across 7 archetypes:

| Archetype | Count | Example Agents |
|-----------|-------|----------------|
| Technical Analyst | 5 | Chart pattern readers, momentum traders |
| Macro Strategist | 5 | Fed policy watchers, cycle analysts |
| Fundamental Analyst | 6 | DCF modelers, earnings quality specialists |
| Quant Trader | 5 | Algo-driven, volatility surface traders |
| Retail Trader | 6 | Reddit-influenced, meme-aware individual investors |
| Institutional Investor | 5 | Fund managers, pension allocators |
| Contrarian | 5 | Counter-consensus thinkers, short sellers |

### 4. Run Simulation

```bash
forkcast sim start {simulation_id} --provider ollama --model llama3.1
```

**Results:**
- **154 total actions** across multiple rounds
- **37 agents** actively participating
- Mix of posts, replies, reposts, and follows
- Debate clusters formed around margin compression vs. energy storage narratives

### 5. Generate Report

```bash
forkcast report generate {simulation_id} --provider ollama --model llama3.1
```

**Report output:** Structured analysis including consensus scoring, narrative mapping, and directional prediction.

## Key Findings from the Report

### Consensus Direction: Moderately Bearish (near-term), Cautiously Bullish (medium-term)

**The simulation surfaced three competing narratives:**

1. **Margin Death Spiral (bearish camp)** — Fundamental analysts and contrarians focused on automotive gross margin compression from 18.2% to 16.8%. Price cuts weren't driving sufficient volume growth. "You can't cut your way to profitability" was the dominant bear thesis.

2. **Energy Storage Inflection (bullish camp)** — Macro strategists and some institutional investors highlighted the 89% energy storage revenue surge. At $2.1B/quarter, this segment alone could justify significant valuation support. Comparisons to AWS's early contribution to Amazon were frequent.

3. **Technical Range-Bound (neutral camp)** — Technical analysts noted the stock was approaching a key support level at $165 with overhead resistance at $195. The 200-day moving average was declining, suggesting a period of consolidation rather than directional movement.

**Emergent dynamics:**
- Retail traders initially posted bullish memes but shifted toward caution after engaging with fundamental analysis threads
- Institutional investors were the most measured, focusing on relative valuation vs. traditional auto peers
- Contrarians provided the most original analysis, questioning whether energy storage margins would hold at scale

### What the Simulation Revealed About Prediction Markets

1. **Narrative clustering** — Agents naturally formed into 3 camps without being directed to. The simulation revealed which narratives have gravitational pull.
2. **Sentiment contagion** — Retail traders were influenced by the most active posters rather than the most rigorous analysis, mirroring real market dynamics.
3. **Information asymmetry** — Fundamental analysts who dug into segment-level data produced different conclusions than those who focused on headline numbers.

## Domain-Specific Features

The prediction-markets domain uses specialized prompt templates:
- **Persona template** — Each agent has a defined investment style, risk tolerance, time horizon, and preferred analytical framework
- **Agent system prompt** — Agents are instructed to react to financial data authentically, post market opinions, and engage with conflicting views
- **Report guidelines** — The analyst produces a consensus score, identifies dominant narratives, and maps the bull/bear/neutral distribution

## Limitations

1. **Local model quality** — Running on llama3.1 via Ollama produced functional but less nuanced analysis than Claude would. Some agent posts were generic. Production use should target Claude for higher-quality agent reasoning.
2. **No real-time data** — The simulation works from seed documents only. Real prediction markets would benefit from live data feeds (price action, options flow, news).
3. **Single platform** — Twitter-style short-form posting captures sentiment but misses longer-form analysis that platforms like Substack or seeking Alpha would surface.
4. **Synthetic consensus** — The consensus score reflects simulated agent opinions, not actual market positioning. It's a directional signal, not a price target.

## Future Enhancements

- **Post-processing framework** — Extract structured predictions (direction, magnitude, confidence) from simulation output for quantitative scoring
- **Domain-specific research tools** — Add tools for options chain analysis, technical indicator calculation, and earnings surprise scoring
- **Multi-timeframe agents** — Allow agents to have different investment horizons (day trader vs. long-term holder)
