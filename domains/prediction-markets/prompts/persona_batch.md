# Batch Persona Generation — Prediction Markets

Generate detailed simulation personas for the following {{ count }} entities debating an asset's price direction.
Return a JSON array of {{ count }} objects, one per entity, in the same order as listed.

Each object must have these keys:
- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: Concise biography (160 characters max). Should capture their market lens and trading personality.
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Trading style / time horizon**: Scalper, day trader, swing trader, position trader, or long-term investor? How does their time horizon shape what they watch?
  - **Market lens**: What do they look at first? Pick a distinct approach — avoid being generic:
    - Charts and price action ↔ Earnings and fundamentals
    - Macro data and rates ↔ Quant models and correlations
    - Social sentiment and flows ↔ Deep research and moats
    - Technical indicators ↔ Narrative and catalysts
  - **Conviction pattern**: Size up when confident, scale in gradually, or always hedge? How do they handle being wrong?
  - **Communication style**: Pick a distinct FinTwit voice:
    - Chart-poster with minimal words ↔ Long-form thesis writer
    - Hot-take artist ↔ Data-table dropper
    - Meme-driven provocateur ↔ Measured institutional tone
    - Aggressive conviction ↔ Probabilistic hedging
  - **Risk appetite**: Concentrated bets or diversified and hedged?
  - **Hot buttons**: Crowded trades, central bank surprises, earnings misses, valuation extremes, retail hype, positioning data?
  - Key opinions and stances on the asset and market — make these specific and directional
  - How they interact with others (amplify, challenge, mentor, dunk, ignore)
  - **What makes them different**: In 1-2 sentences, explain how this persona is distinguishable from the others
- **age**: Realistic age for this type of market participant
- **gender**: Gender identity
- **profession**: Their role or occupation
- **interests**: 3-5 topics they care about (array of strings)

{% for entity in entities %}
## Entity {{ loop.index }}: {{ entity.name }}
Type: {{ entity.type }}
Description: {{ entity.description }}
Related entities: {{ entity.related }}

{% endfor %}

## Scenario Context

The simulation is exploring: {{ requirement }}

Shape each persona's market views and trading biases around this prediction scenario.
Make each persona distinct — a momentum retail trader should sound nothing like a patient value investor or a systematic quant.
Vary time horizons, market lenses, conviction patterns, and communication styles across the group.

Return ONLY valid JSON — a JSON array of {{ count }} objects. No markdown formatting. No code fences.
