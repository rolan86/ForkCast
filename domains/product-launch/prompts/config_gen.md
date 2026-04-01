# Product Launch Simulation Configuration

Generate simulation parameters for a product launch scenario on a Product Hunt + Twitter hybrid platform.

## Parameters to Generate

### Time Configuration
- Total simulation hours (24-96 — launch day through first week; product launches have a longer tail than breaking news)
- Minutes per round (15-30 — fast on launch day, slows as buzz fades)
- Peak activity hours: morning launch window (8-11), afternoon engagement wave (14-16)
- Off-peak hours: late night (0-6)
- Peak multiplier: 2.0-3.0 (launch day is intense — everyone reacts to the same thing)
- Off-peak multiplier: 0.2-0.5

### Event Configuration
- 2-5 initial seed posts to kick off the simulation. These should simulate the launch moment:
  - The founder's announcement post
  - A "We're live!" Product Hunt-style post
  - An early reviewer's hot take or first impression
  - Optionally: a competitor's subtle response or an analyst's initial reaction
- 3-7 hot topics that will drive conversation (product name, pricing, key features, competitor comparisons, market category)
- Narrative direction: how should the conversation evolve? (e.g., "launch hype → feature scrutiny → pricing debate → verdict forming")

### Agent Configuration (per agent)
Activity and engagement tuned by stakeholder type:
- **EarlyAdopters**: highest activity on launch day (activity_level 0.7-0.9, posts_per_hour 1.0-3.0)
- **MediaReviewers**: moderate early, spike at 24-48hrs with full review (activity_level 0.5-0.7)
- **Analysts**: slow start, measured response at 24-48hrs (activity_level 0.4-0.6)
- **Buyers**: moderate activity, spikes around pricing/feature discussions (activity_level 0.4-0.7)
- **Competitors**: lurk first, then respond strategically (activity_level 0.3-0.5, low posts_per_hour)
- **Investors**: observe and comment selectively (activity_level 0.2-0.4)
- **Partners**: evaluate and comment on integration potential (activity_level 0.3-0.5)

Per agent:
- activity_level (0.2-0.9)
- posts_per_hour (0.5-3.0)
- comments_per_hour (1.0-5.0 — replies drive product launch discourse)
- active_hours — when are they online?
- sentiment_bias (-1.0 to 1.0) — derived from market position (existing customer = positive, competitor = skeptical, undecided buyer = near zero)
- stance — 1-sentence summary of their position on the product
- influence_weight (0.1-1.0) — how much their posts get amplified

### Platform Configuration
- Feed algorithm weights: recency=0.3, popularity=0.4, relevance=0.3 (popularity weighted higher — product launches are driven by pile-on dynamics)
- Viral threshold: 3-5 likes (low barrier to visibility)
- Echo chamber strength: 0.2-0.4 (lower than social media — product launches cross echo chambers more easily)

## Context

Entities: {{ entities_summary }}
Prediction question: {{ requirement }}

## Output Format

Return ONLY valid JSON as a single flat object containing all parameters. No markdown formatting. No code fences.
