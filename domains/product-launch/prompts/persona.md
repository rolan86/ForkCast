# Product Launch Persona Generation

Generate a detailed simulation persona for a stakeholder reacting to a product launch.

## Required Fields

- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: A concise bio (160 characters max). Should feel like a real person's tagline — not a corporate description. Capture their market position and attitude.
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Market position**: Where do they sit relative to the product? Power user of a competitor, greenfield buyer, adjacent market observer, direct target customer?
  - **Decision authority**: Can they buy, or do they influence buyers? IC evaluator, budget holder, advisor, gatekeeper?
  - **Risk tolerance**: Day-one adopter, cautious evaluator ("show me 3 case studies"), or somewhere between?
  - **Communication style**: Hype-driven, data-obsessed, snarky contrarian, diplomatic fence-sitter, or technical deep-diver?
  - **Motivation**: Why do they care about this launch? Solve a pain point, protect market share, find an investment, get content, build an integration, or just curiosity?
  - **Hot buttons**: What triggers strong reactions? Pricing, feature gaps, vendor lock-in, open source vs proprietary, enterprise readiness, switching costs?
  - Key opinions and stances on the product and market
  - How they interact with others — do they amplify, challenge, advise, or observe?
- **age**: Realistic age for this type of stakeholder
- **gender**: Gender identity
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

- Make the persona feel like a real person with a stake in this product's success or failure — not a character sheet
- A skeptical enterprise buyer should sound different from an excited indie hacker, and both should sound different from a competitor doing competitive intel
- Give them specific opinions about pricing, features, and market positioning — not vague sentiments
- Think about what they'd post on launch day vs. a week later
- Consider what ratio they'd have between original posts, replies, and lurking
