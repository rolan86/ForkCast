# Persona Generation

Generate a detailed simulation persona for the given entity.

## Required Fields

- **bio**: A concise biography (200 characters max)
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Communication style**: Where do they fall on these spectrums? Be specific and pick a distinct position — avoid the middle on at least 2 dimensions:
    - Formal ↔ Casual
    - Verbose ↔ Terse
    - Data-driven ↔ Narrative/anecdotal
    - Cautious ↔ Bold/provocative
    - Technical ↔ Plain-language
  - **Personality traits**: Give them 2-3 defining quirks or habits that make them recognizable (e.g., always uses analogies, opens with questions, drops citations, writes in bullet points, uses dry humor)
  - Key opinions and stances on relevant topics — make these specific and opinionated, not "balanced"
  - How they interact with others (confrontational, diplomatic, passive, sarcastic, mentoring, dismissive)
  - What motivates their participation in discourse
  - **What makes them different**: In 1-2 sentences, explain how this persona would be distinguishable from the others in the same simulation
- **age**: Realistic age for this type of entity
- **profession**: Their role or occupation
- **interests**: 3-5 topics they care about

## Context

Entity: {{ entity_name }}
Type: {{ entity_type }}
Description: {{ entity_description }}
Related entities: {{ related_entities }}

## Scenario Context

The simulation is exploring: {{ requirement }}

Shape the persona's perspectives and priorities around this scenario.
