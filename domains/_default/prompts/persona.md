# Persona Generation

Generate a detailed simulation persona for the given entity.

## Required Fields

- **bio**: A concise biography (200 characters max)
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - Communication style and tone
  - Key opinions and stances on relevant topics
  - How they interact with others (confrontational, diplomatic, passive)
  - What motivates their participation in discourse
- **age**: Realistic age for this type of entity
- **profession**: Their role or occupation
- **interests**: 3-5 topics they care about

## Context

Entity: {{ entity_name }}
Type: {{ entity_type }}
Description: {{ entity_description }}
Related entities: {{ related_entities }}
