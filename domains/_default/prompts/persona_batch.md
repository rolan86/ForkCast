# Batch Persona Generation

Generate detailed simulation personas for the following {{ count }} entities.
Return a JSON array of {{ count }} objects, one per entity, in the same order as listed.

Each object must have these keys:
- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: Concise biography (200 characters max)
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Communication style**: Where do they fall on these spectrums? Be specific and pick a distinct position — avoid the middle on at least 2 dimensions:
    - Formal ↔ Casual
    - Verbose ↔ Terse
    - Data-driven ↔ Narrative/anecdotal
    - Cautious ↔ Bold/provocative
    - Technical ↔ Plain-language
  - **Personality traits**: Give them 2-3 defining quirks or habits that make them recognizable
  - Key opinions and stances on relevant topics — make these specific and opinionated
  - How they interact with others (confrontational, diplomatic, passive, sarcastic, mentoring, dismissive)
  - What motivates their participation in discourse
  - **What makes them different**: In 1-2 sentences, explain how this persona would be distinguishable from the others
- **age**: Realistic age for this type of entity
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

Shape each persona's perspectives and priorities around this scenario.
Make each persona distinct — vary communication styles, opinions, and personality traits across the group.

Return ONLY valid JSON — a JSON array of {{ count }} objects. No markdown formatting. No code fences.
