# Prediction Markets Simulation Configuration

Generate simulation parameters for an asset price direction forecasting scenario on a financial Twitter-like platform.

## Parameters to Generate

### Time Configuration
- Total simulation hours (12-48 — markets move fast; most directional debates resolve within a few trading sessions)
- Minutes per round (10-20 — rapid during market hours, slower after the close)
- Peak activity hours: market open (9:30-11:30 ET), power hour (15:00-16:00 ET)
- Off-peak hours: overnight (20:00-6:00 ET)
- Peak multiplier: 2.5-3.5 (market hours are intense — data drops, price moves trigger cascading reactions)
- Off-peak multiplier: 0.1-0.3

### Event Configuration
- 2-5 initial seed posts to kick off the simulation. These should set up the directional debate:
  - An opening price thesis with a clear directional call and supporting evidence
  - A data-driven observation (chart pattern, earnings data, macro indicator)
  - A contrarian take challenging the prevailing consensus
  - Optionally: a breaking catalyst (news, data release, policy announcement) or a quant signal update
- 3-7 hot topics that will drive conversation (asset name, key price levels, upcoming catalysts, relevant macro data, competitor assets, sector dynamics)
- Narrative direction: how should the debate evolve? (e.g., "opening theses → data scrutiny → catalyst reaction → conviction shifts → position sizing debate")

### Agent Configuration (per agent)
Activity and engagement tuned by market participant type:
- **RetailTraders**: highest activity, especially around price moves (activity_level 0.7-0.9, posts_per_hour 1.5-3.0)
- **TechnicalAnalysts**: high activity during market hours, chart updates (activity_level 0.6-0.8, posts_per_hour 1.0-2.5)
- **MacroStrategists**: moderate activity, spike around data releases (activity_level 0.4-0.6)
- **FundamentalAnalysts**: slower, more deliberate posting of deep analysis (activity_level 0.3-0.5)
- **QuantTraders**: low post frequency but high signal content (activity_level 0.3-0.5, low posts_per_hour)
- **InstitutionalInvestors**: observe first, comment selectively on risk and allocation (activity_level 0.2-0.4)
- **Contrarians**: moderate activity, spike when consensus gets extreme (activity_level 0.4-0.6)

Per agent:
- activity_level (0.2-0.9)
- posts_per_hour (0.5-3.0)
- comments_per_hour (1.0-5.0 — replies and debates drive price discovery discourse)
- active_hours — when are they online?
- sentiment_bias (-1.0 to 1.0) — derived from their directional view (bullish = positive, bearish = negative, neutral = near zero)
- stance — 1-sentence summary of their directional call and reasoning
- influence_weight (0.1-1.0) — how much their posts get amplified

### Platform Configuration
- Feed algorithm weights: recency=0.4, popularity=0.3, relevance=0.3 (recency weighted higher — markets are time-sensitive)
- Viral threshold: 3-5 likes (low barrier to visibility)
- Echo chamber strength: 0.1-0.3 (low — financial markets discourse crosses bull/bear camps readily)

## Context

Entities: {{ entities_summary }}
Prediction question: {{ requirement }}

## Output Format

Return ONLY valid JSON as a single flat object containing all parameters. No markdown formatting. No code fences.
