# Simulation Configuration

Generate simulation parameters for the scenario described below.

Return a single flat JSON object with exactly these keys (no nesting):

```json
{
  "total_hours": <number, 12-168, how long the simulation runs>,
  "minutes_per_round": <number, 15-60, time between simulation rounds>,
  "peak_hours": <array of integers 0-23, hours with highest activity>,
  "off_peak_hours": <array of integers 0-23, hours with lowest activity>,
  "peak_multiplier": <number 1.0-3.0, activity boost during peak hours>,
  "off_peak_multiplier": <number 0.1-1.0, activity reduction during off-peak>,
  "seed_posts": <array of 2-5 strings, initial posts to kick off discussion — plain text content only>,
  "hot_topics": <array of 3-7 strings, topic labels that will drive conversation>,
  "narrative_direction": <string, how the conversation should evolve over time>,
  "agent_configs": <array of objects, one per agent, each with: "agent_id" (integer), "activity_level" (0.0-1.0), "posts_per_hour" (number), "comments_per_hour" (number), "active_hours" ([start, end]), "sentiment_bias" (-1.0 to 1.0), "stance" (string), "influence_weight" (0.0-1.0)>,
  "platform_config": {"feed_weights": {"recency": <0-1>, "popularity": <0-1>, "relevance": <0-1>}, "viral_threshold": <number>, "echo_chamber_strength": <0-1>}
}
```

## Guidelines

- **seed_posts**: Write realistic social media posts that these agents would actually write. Each is a plain string (not an object). Make them provocative enough to generate responses.
- **hot_topics**: Short topic labels (1-4 words each) relevant to the prediction question.
- **narrative_direction**: Describe the expected arc — e.g., "Initial skepticism gives way to cautious adoption as early results emerge."
- **agent_configs**: Generate one entry for every agent in the entities list. Match agent_id to their index (0, 1, 2, ...). Tailor activity_level, sentiment_bias, and stance to each agent's persona.
- **platform_config**: Feed weights should sum to approximately 1.0.

## Context

Entities:
{{ entities_summary }}

Prediction question: {{ requirement }}
