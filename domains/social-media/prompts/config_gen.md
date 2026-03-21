# Twitter Simulation Configuration

Generate simulation parameters for a Twitter-style social media scenario.

## Parameters to Generate

### Time Configuration
- Total simulation hours (24-72 for a typical Twitter news cycle)
- Minutes per round (15-30 — Twitter moves fast)
- Peak activity hours: morning (7-9), lunch (12-14), evening (18-22)
- Off-peak hours: late night (1-6)
- Peak multiplier: 1.5-2.0 (more activity during peak)
- Off-peak multiplier: 0.3-0.5 (much less activity late night)

### Event Configuration
- 2-4 initial seed tweets to kick off discussion (these are the opening provocations)
- 3-5 hot topics that will drive conversation (trending hashtags, themes)
- Narrative direction: how should the conversation evolve over time? (e.g., "escalating debate", "consensus building", "polarization")

### Agent Configuration (per agent)
- Activity level (0.3-0.9) — how frequently they post/react
- Posts per hour (0.5-3.0 for Twitter — some tweet constantly, others rarely)
- Comments per hour (1.0-5.0 — replies are the lifeblood of Twitter)
- Active hours range — when are they online?
- Sentiment bias (-1.0 to 1.0) — overall stance on the topic
- Stance description — 1-sentence summary of their position
- Influence weight (0.1-1.0) — how much their posts get amplified

### Platform Configuration
- Feed algorithm: recency=0.4, popularity=0.35, relevance=0.25 (Twitter favors recency)
- Viral threshold: 3-5 likes (low barrier to visibility on Twitter)
- Echo chamber strength: 0.3-0.5 (Twitter has moderate echo chambers)

## Context

Entities: {{ entities_summary }}
Prediction question: {{ requirement }}
