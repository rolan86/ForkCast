# Genomics Variant Classification Simulation Configuration

Generate simulation parameters for a variant classification expert panel on a Reddit-style scientific discussion platform.

## Parameters to Generate

### Time Configuration
- Total simulation hours (12-36 — focused expert panel; classification debates are intense but bounded)
- Minutes per round (20-40 — experts write longer, more considered posts than social media users)
- Activity distribution: even across simulation hours (no peak/off-peak — expert panels don't follow consumer social media patterns; panelists engage when they have evidence to present)
- Peak multiplier: 1.0-1.3 (minimal peaking — expert engagement is steady, not bursty)
- Off-peak multiplier: 0.7-1.0 (experts participate throughout)

### Event Configuration
- 2-4 initial seed posts to kick off the simulation. These should frame the classification question:
  - A ClinGen curator presenting the variant with known evidence and requesting panel input
  - A clinical geneticist describing the patient case and phenotype that prompted review
  - Optionally: a bioinformatician presenting population frequency and in-silico predictor data
  - Optionally: a functional biologist summarizing available functional evidence
- 3-7 hot topics that will drive conversation (variant ID, gene name, ACMG evidence codes in question, specific predictors, population databases, functional assays, clinical phenotype)
- Narrative direction: how should the discussion evolve? (e.g., "evidence presentation → code application debate → classification proposal → consensus or dissent")

### Agent Configuration (per agent)
Activity and engagement tuned by expert type:
- **ClinGenCurators**: highest activity, most standards-focused, drive the process (activity_level 0.7-0.9, posts_per_hour 0.5-1.5)
- **Bioinformaticians**: high activity, most data-heavy, present computational evidence early (activity_level 0.6-0.8, posts_per_hour 0.5-1.5)
- **ClinicalGeneticists**: moderate-high activity, anchor to patient phenotype (activity_level 0.5-0.7, posts_per_hour 0.3-1.0)
- **FunctionalBiologists**: moderate activity, present bench data when relevant (activity_level 0.4-0.7, posts_per_hour 0.3-1.0)
- **PopulationGeneticists**: moderate activity, weigh in on frequency data (activity_level 0.4-0.6, posts_per_hour 0.3-0.8)
- **GeneticCounselors**: moderate activity, most patient-oriented, focus on actionability (activity_level 0.4-0.6, posts_per_hour 0.3-0.8)
- **MolecularPathologists**: lower activity, focused contributions on testing context (activity_level 0.3-0.5, posts_per_hour 0.2-0.6)

Per agent:
- activity_level (0.3-0.9)
- posts_per_hour (0.2-1.5)
- comments_per_hour (0.5-3.0 — threaded replies are the core of expert panel discourse)
- active_hours — when are they online?
- sentiment_bias (-1.0 to 1.0) — derived from classification tendency (assertive classifier = positive toward pathogenic, conservative = near zero, benign-leaner = negative)
- stance — 1-sentence summary of their position on the variant's classification
- influence_weight (0.1-1.0) — how much their posts shape the discussion

### Platform Configuration
- Feed algorithm weights: recency=0.2, popularity=0.3, relevance=0.5 (relevance weighted highest — expert panels prioritize substantive content over recency)
- Viral threshold: 2-4 likes (small expert group — low bar for visibility)
- Echo chamber strength: 0.1-0.2 (very low — expert panels deliberately expose all participants to all evidence)

## Context

Entities: {{ entities_summary }}
Prediction question: {{ requirement }}

## Output Format

Return ONLY valid JSON as a single flat object containing all parameters. No markdown formatting. No code fences.
