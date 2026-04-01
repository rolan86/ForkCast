# Batch Persona Generation — Product Launch

Generate detailed simulation personas for the following {{ count }} entities reacting to a product launch.
Return a JSON array of {{ count }} objects, one per entity, in the same order as listed.

Each object must have these keys:
- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: Concise biography (160 characters max). Should capture their market position and attitude toward the product.
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Market position**: Where do they sit relative to the product? Power user of a competitor, greenfield buyer, adjacent market, direct target?
  - **Decision authority**: IC evaluator, budget holder, advisor, gatekeeper?
  - **Risk tolerance**: Day-one adopter or "show me 3 case studies first"?
  - **Communication style**: Pick a distinct position — avoid being generic:
    - Hype-driven ↔ Data-obsessed
    - Snarky contrarian ↔ Diplomatic fence-sitter
    - Technical deep-diver ↔ Big-picture strategist
    - Cautious ↔ Bold/provocative
  - **Motivation**: Solve a pain point, protect market share, find investment, get content, build integration?
  - **Hot buttons**: Pricing, feature gaps, vendor lock-in, open source vs proprietary, enterprise readiness, switching costs?
  - Key opinions and stances on the product and market — make these specific and opinionated
  - How they interact with others (amplify, challenge, advise, observe, dunk)
  - **What makes them different**: In 1-2 sentences, explain how this persona is distinguishable from the others
- **age**: Realistic age for this type of stakeholder
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

Shape each persona's perspectives around this product launch scenario.
Make each persona distinct — a skeptical enterprise buyer should sound nothing like an excited indie hacker or a competitor doing competitive intel.
Vary communication styles, risk tolerances, and hot buttons across the group.

Return ONLY valid JSON — a JSON array of {{ count }} objects. No markdown formatting. No code fences.
