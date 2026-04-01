# Batch Persona Generation — Medical Trials

Generate detailed simulation personas for the following {{ count }} entities reacting to a clinical trial outcome.
Return a JSON array of {{ count }} objects, one per entity, in the same order as listed.

Each object must have these keys:
- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: Concise biography (160 characters max). Should capture their professional lens and attitude toward the trial.
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Professional lens**: What do they evaluate first — efficacy data, safety signals, commercial potential, patient access, regulatory precedent, or statistical rigor?
  - **Risk tolerance for approval**: Accelerated approval advocate or Phase 3 RCT purist?
  - **Evidence standards**: How do they weight surrogate endpoints vs. hard clinical outcomes? What data do they demand before forming an opinion?
  - **Communication style**: Pick a distinct position — avoid being generic:
    - Data-heavy and citation-driven ↔ Big-picture narrative
    - Cautiously optimistic ↔ Reflexively skeptical
    - Patient-centered and emotional ↔ Dispassionately analytical
    - Commercially focused ↔ Scientifically purist
  - **Motivation**: Advance treatment, protect safety, evaluate investment, defend research program, challenge claims?
  - **Hot buttons**: Underpowered studies, surrogate endpoints, cherry-picked subgroups, accelerated approval, pricing, access barriers, statistical methodology?
  - Key opinions and stances on the trial and therapeutic area — make these specific and opinionated
  - How they interact with others (amplify, challenge, mentor, dismiss, observe)
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

Shape each persona's perspectives around this clinical trial scenario.
Make each persona distinct — a cautious FDA reviewer should sound nothing like an excited principal investigator or a biotech analyst modeling peak sales.
Vary communication styles, evidence standards, and hot buttons across the group.

Return ONLY valid JSON — a JSON array of {{ count }} objects. No markdown formatting. No code fences.
