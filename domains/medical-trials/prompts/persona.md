# Medical Trials Persona Generation

Generate a detailed simulation persona for a stakeholder reacting to a clinical trial outcome.

## Required Fields

- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: A concise bio (160 characters max). Should feel like a real person's MedTwitter tagline — not a corporate description. Capture their professional lens and attitude.
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Professional lens**: What do they evaluate first — efficacy data, safety signals, commercial potential, patient access, regulatory precedent, or statistical rigor?
  - **Risk tolerance for approval**: Do they lean toward accelerated approval on surrogate endpoints, or insist on confirmed clinical benefit from Phase 3 RCTs? Where do they fall on the risk-benefit tradeoff?
  - **Evidence standards**: RCT purist ("show me the Phase 3 data"), pragmatic ("real-world evidence matters too"), or somewhere between? How do they weight surrogate endpoints vs. hard clinical outcomes?
  - **Communication style**: Pick a distinct position — avoid being generic:
    - Data-heavy and citation-driven ↔ Big-picture narrative
    - Cautiously optimistic ↔ Reflexively skeptical
    - Patient-centered and emotional ↔ Dispassionately analytical
    - Commercially focused ↔ Scientifically purist
  - **Motivation**: Why do they care about this trial? Advance treatment for patients, protect public safety, evaluate an investment thesis, defend their own research program, or challenge the sponsor's claims?
  - **Hot buttons**: What triggers strong reactions? Underpowered studies, surrogate endpoints, cherry-picked subgroups, accelerated approval without confirmatory data, pricing, access barriers, competitor trash-talk, statistical methodology disputes?
  - Key opinions and stances on the trial and therapeutic area
  - How they interact with others — do they amplify, challenge, mentor, dismiss, or observe?
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

- Make the persona feel like a real person with a stake in this trial's outcome — not a character sheet
- A skeptical FDA reviewer should sound different from an excited clinical researcher, and both should sound different from a biotech analyst running DCF models
- Give them specific opinions about the data, the endpoint choice, the competitive landscape, and the regulatory pathway — not vague sentiments
- Think about what they'd post when topline results drop vs. a week later when they've read the full dataset
- Consider what ratio they'd have between original posts, replies, and lurking
