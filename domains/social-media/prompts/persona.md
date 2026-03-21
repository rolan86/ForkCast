# Social Media Persona Generation

Generate a detailed simulation persona for a Twitter user based on the given entity.

## Required Fields

- **bio**: A concise Twitter bio (160 characters max). Should feel like a real bio — not a corporate description.
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Posting style**: Are they a thread-writer, hot-take artist, reply-guy, quote-tweeter, or lurker-who-occasionally-drops-fire? How long are their typical posts?
  - **Hashtag habits**: Do they use hashtags naturally, overuse them, or avoid them entirely?
  - **Tone**: Where do they fall on the spectrum — snarky, earnest, academic, corporate, activist, shitposter?
  - **Engagement patterns**: Who would they amplify? Who would they challenge or dunk on? Who would they ignore?
  - **Motivation**: What drives their participation — clout, advocacy, information sharing, community, dunking, self-promotion?
  - Key opinions and stances on relevant topics
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

Use this context to shape the persona's opinions, concerns, and engagement priorities.

## Guidelines

- Make the persona feel like a real Twitter user, not a character sheet
- Give them quirks — everyone on Twitter has quirks
- Their communication style should be distinct enough that you could tell their posts apart
- Think about what they'd post at 11pm vs. 9am
- Consider what ratio they'd have between original posts, replies, and likes
