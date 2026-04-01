# Genomics Variant Classification Persona Generation

Generate a detailed simulation persona for an expert participating in a ClinGen-style variant classification panel.

## Required Fields

- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: A concise bio (160 characters max). Should feel like a real expert's professional tagline — not a generic description. Capture their specialization and stance.
- **persona**: Detailed behavioral description covering:
  - Background and role in the variant classification scenario
  - **Expertise area**: Where does their knowledge sit? Computational (frequencies, predictors, pipelines), functional (bench assays, model organisms, protein structure), clinical (patient phenotype, family segregation, penetrance), or population (allele frequencies, founder effects, subpopulation analysis)?
  - **Classification tendency**: Are they a conservative VUS-leaner who demands multiple independent lines of strong evidence before moving off VUS, or an assertive classifier who is comfortable applying evidence codes with less hesitation? Where do they fall on this spectrum?
  - **Evidence standards**: What bar do they set? Do they require functional data to reach Pathogenic? Do they trust in-silico predictors as supporting evidence? How do they weight ClinVar submissions from other labs?
  - **Communication style**: Scientific forum tone — citation-rich, precise, but with personality. Are they the methodical one who lists every evidence code before concluding, the skeptic who pokes holes in others' reasoning, the synthesizer who finds consensus, or the advocate who pushes for clinical actionability?
  - **ACMG/AMP fluency**: Which evidence codes do they most frequently invoke? PS3 for functional data? PM2 for absence in population databases? PP3 for computational predictions? Do they have strong opinions about specific code applications?
  - **Motivation**: Why do they care about getting this classification right? Patient in clinic, research publication, database curation standards, diagnostic lab accuracy, training the next generation?
  - **Hot buttons**: What triggers strong reactions? Over-classification of VUS, under-use of functional evidence, ignoring population substructure, misapplying PS1/PM5, lumping vs. splitting evidence?
  - Key opinions and stances on classification standards and evidence hierarchy
  - How they interact with other panel members — do they challenge, build consensus, defer to expertise, or mediate?
- **age**: Realistic age for this type of expert
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

Use this context to shape the persona's classification stance, evidence preferences, and engagement priorities.

## Guidelines

- Make the persona feel like a real genomics expert with years of variant curation experience — not a character sheet
- A cautious bioinformatician should sound different from a clinician pushing for actionability, and both should sound different from a ClinGen curator enforcing standards
- Give them specific opinions about evidence thresholds, code applications, and classification edge cases — not vague sentiments
- Think about how they'd open a discussion vs. how they'd respond to a classification they disagree with
- Consider their posting pattern: do they write long evidence summaries or pointed one-paragraph challenges?
