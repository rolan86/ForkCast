# Simulation Configuration

Generate simulation parameters for the scenario described below.

## Parameters to Generate

### Time Configuration
- Total simulation hours (12-168)
- Minutes per round (15-60)
- Peak activity hours
- Off-peak activity hours
- Activity multipliers for peak/off-peak

### Event Configuration
- 2-5 initial seed posts to kick off discussion
- 3-7 hot topics that will drive conversation
- Narrative direction (how the conversation should evolve)

### Agent Configuration (per agent)
- Activity level (0.0-1.0)
- Posts per hour
- Comments per hour
- Active hours range
- Sentiment bias (-1.0 to 1.0)
- Stance description
- Influence weight

### Platform Configuration
- Feed algorithm weights (recency, popularity, relevance)
- Viral threshold
- Echo chamber strength

## Context

Entities: {{ entities_summary }}
Prediction question: {{ requirement }}
