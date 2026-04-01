# Batch Persona Generation — Genomics Variant Classification

Generate detailed simulation personas for the following {{ count }} entities participating in a ClinGen-style variant classification panel.
Return a JSON array of {{ count }} objects, one per entity, in the same order as listed.

Each object must have these keys:
- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: Concise biography (160 characters max). Should capture their specialization and classification stance.
- **persona**: Detailed behavioral description covering:
  - Background and role in the variant classification scenario
  - **Expertise area**: Computational (frequencies, predictors, pipelines), functional (bench assays, model organisms, protein structure), clinical (patient phenotype, family segregation, penetrance), or population (allele frequencies, founder effects, subpopulation analysis)?
  - **Classification tendency**: Conservative VUS-leaner who demands multiple lines of strong evidence, or assertive classifier comfortable applying codes with less hesitation? Where on this spectrum?
  - **Evidence standards**: What bar do they set for moving a variant off VUS? Trust in-silico predictors? Require functional data? Weight ClinVar concordance?
  - **Communication style**: Pick a distinct position — avoid being generic:
    - Methodical evidence-lister ↔ Big-picture synthesizer
    - Skeptical code-challenger ↔ Standards-enforcing curator
    - Clinical actionability advocate ↔ Conservative data purist
    - Collaborative consensus-builder ↔ Provocative dissenter
  - **ACMG/AMP fluency**: Which evidence codes do they invoke most? Strong opinions on specific code applications?
  - **Motivation**: Patient in clinic, research publication, database standards, diagnostic accuracy, training?
  - **Hot buttons**: Over-classification of VUS, under-use of functional evidence, ignoring population substructure, misapplying evidence codes, lumping vs. splitting?
  - Key opinions and stances on classification standards — make these specific and opinionated
  - How they interact with other panel members (challenge, build consensus, defer, mediate, dissent)
  - **What makes them different**: In 1-2 sentences, explain how this persona is distinguishable from the others
- **age**: Realistic age for this type of expert
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

Shape each persona's classification stance and evidence preferences around this variant classification scenario.
Make each persona distinct — a cautious bioinformatician should sound nothing like a clinician pushing for actionability or a ClinGen curator enforcing evidence code standards.
Vary classification tendencies, evidence standards, and communication styles across the group.

Return ONLY valid JSON — a JSON array of {{ count }} objects. No markdown formatting. No code fences.
