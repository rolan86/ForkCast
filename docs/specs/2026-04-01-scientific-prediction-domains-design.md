# Scientific Prediction Domains Design

> Date: 2026-04-01
> Branch: `feature/scientific-prediction-domains`
> Approach: Pure Prompt Domains (no code changes)

## Overview

Three new independent domain plugins for ForkCast, each applying collective intelligence simulation to scientific and financial prediction:

1. **prediction-markets** — Asset price direction forecasting
2. **medical-trials** — Drug/trial outcome prediction
3. **genomics** — Variant pathogenicity classification

All three use ForkCast's existing domain plugin system with zero code changes. Each domain is a directory with `manifest.yaml`, customized prompts, and ontology hints. Entity types in `hints.yaml` serve as persona archetypes — the entity extractor finds instances of these types in seed documents (e.g., "Goldman Sachs" as an `InstitutionalInvestor`), then the persona generator turns each extracted entity into a simulation agent. This is the same pattern used by `product-launch`.

Future enhancements (recorded in roadmap as Phases 8a/8b):
- **8a:** Custom report post-processing to extract structured data (consensus scores, vote tallies) into JSON
- **8b:** Domain-specific research tools (e.g., `query_clinvar`, `fetch_market_data`)

---

## Domain 1: prediction-markets

### Purpose

Simulate diverse market participants debating asset price direction. Produces a consensus forecast with confidence score backed by full narrative breakdown of bull vs bear arguments.

### Seed Documents

Mixed inputs: earnings reports, SEC filings, analyst notes, news articles, research reports, social media/forum posts about the asset.

**Example seed document for testing:** An earnings report for a public company (e.g., Tesla Q1 2026 10-Q) combined with 2-3 recent analyst notes and news articles about the company's competitive position.

### Manifest (manifest.yaml)

```yaml
name: prediction-markets
version: "1.0"
description: >
  Asset price direction forecasting. Simulates how technical analysts,
  macro strategists, fundamental analysts, quant traders, retail traders,
  institutional investors, and contrarians debate price direction on a
  financial Twitter-like platform.
language: en
sim_engine: claude
platforms:
  - twitter
prompts:
  ontology: prompts/ontology.md
  persona: prompts/persona.md
  persona_batch: prompts/persona_batch.md
  report_guidelines: prompts/report_guidelines.md
  config_generation: prompts/config_gen.md
  agent_system: prompts/agent_system.md
ontology:
  hints: ontology/hints.yaml
  max_entity_types: 10
  required_fallbacks:
    - Person
    - Organization
```

### Entity Types (ontology/hints.yaml)

| Type | Description |
|------|-------------|
| TechnicalAnalyst | Chart/pattern-based trader, references support/resistance levels |
| MacroStrategist | Macro-economic and geopolitical lens |
| FundamentalAnalyst | Valuation, earnings, balance sheet focus |
| QuantTrader | Algorithmic/data-driven perspective |
| RetailTrader | Individual investor, sentiment and momentum driven |
| InstitutionalInvestor | Fund manager, risk-adjusted, long-term horizon |
| Contrarian | Deliberately opposes consensus, stress-tests majority view |

### Ontology Extraction (prompts/ontology.md)

Guide the LLM to extract entity types relevant to financial markets from seed documents. Focus on identifying:
- Named individuals, firms, and institutions that could be market participants
- Their market role (analyst, trader, fund, media) based on context
- Relationships like "covers", "competes with", "invests in", "reports on"

### Persona Generation (prompts/persona.md and persona_batch.md)

Each persona should include:
- **Trading style:** Time horizon (intraday / swing / position / long-term), risk tolerance
- **Market lens:** What data they prioritize (charts, fundamentals, macro, sentiment)
- **Conviction pattern:** How strongly they commit to views, how easily they update
- **Communication style:** Finance Twitter tone (data-heavy, hot-take, thread-writer, meme-trader)
- **Bio:** 160-char tagline that sounds like a real FinTwit bio

`persona.md` generates one persona at a time (fallback). `persona_batch.md` generates all personas in a single LLM call (preferred path). Both produce the same `AgentProfile` JSON schema.

### Agent Behavior (prompts/agent_system.md)

Each persona type receives specific behavioral guidance:

- **TechnicalAnalysts** reference chart patterns, support/resistance levels, moving averages, volume indicators
- **MacroStrategists** connect asset moves to interest rates, geopolitics, currency flows, central bank policy
- **FundamentalAnalysts** cite earnings multiples, revenue growth, competitive moats, balance sheet health
- **QuantTraders** reference statistical models, correlations, momentum signals, mean reversion
- **RetailTraders** react to momentum, social media sentiment, FOMO/fear dynamics
- **InstitutionalInvestors** weigh risk-adjusted returns, portfolio allocation, regulatory considerations
- **Contrarians** actively challenge the emerging consensus, probe for groupthink, cite historical analogues where consensus was wrong

All agents should:
- State their position clearly (bullish/bearish/neutral) with a time horizon
- Reference specific data points from the seed documents
- Engage with and challenge other agents' arguments
- Update their view if compelling counter-evidence is presented

### Report Output (prompts/report_guidelines.md)

Two-section report:

**Section 1 — Consensus Forecast:**
- Directional call (bullish / bearish / neutral) with confidence percentage
- Top 3 bull arguments with supporting evidence
- Top 3 bear arguments with supporting evidence
- Key catalysts and their expected timelines
- Price-relevant factors that were most debated

**Section 2 — Debate Breakdown:**
- Per-persona-type position summary (1-2 sentences each)
- Strongest points of agreement across persona types
- Sharpest disagreements and what drove them
- What evidence or events would change the minority's mind
- Quotes from the most compelling bull and bear arguments

### Simulation Config (prompts/config_gen.md)

- Shorter simulations (12-48 hours simulated time) reflecting fast-moving market discourse
- Higher activity during market hours (9:30am-4pm ET as peak)
- Seed posts should include specific price theses and data-driven observations

---

## Domain 2: medical-trials

### Purpose

Simulate a diverse panel of medical/biotech stakeholders debating a drug or clinical trial's likelihood of success. Produces a probability forecast plus a simulated advisory panel vote with per-persona rationale.

### Seed Documents

Mixed inputs: published trial results, ClinicalTrials.gov entries, journal papers, meta-analyses, FDA briefing documents, advisory committee transcripts, biotech analyst reports, investor presentations, conference abstracts.

**Example seed document for testing:** A Phase 3 trial results publication for a novel oncology drug, combined with the FDA briefing document and a biotech analyst note discussing commercial potential.

### Manifest (manifest.yaml)

```yaml
name: medical-trials
version: "1.0"
description: >
  Drug and clinical trial outcome prediction. Simulates how clinical
  researchers, FDA reviewers, biotech analysts, clinicians, patient
  advocates, biostatisticians, and competitor scientists debate a
  trial's likelihood of success.
language: en
sim_engine: claude
platforms:
  - twitter
prompts:
  ontology: prompts/ontology.md
  persona: prompts/persona.md
  persona_batch: prompts/persona_batch.md
  report_guidelines: prompts/report_guidelines.md
  config_generation: prompts/config_gen.md
  agent_system: prompts/agent_system.md
ontology:
  hints: ontology/hints.yaml
  max_entity_types: 10
  required_fallbacks:
    - Person
    - Organization
```

### Entity Types (ontology/hints.yaml)

| Type | Description |
|------|-------------|
| ClinicalResearcher | Principal investigator or trial scientist, deep domain knowledge |
| FDAReviewer | Regulatory perspective, safety-first, precedent-aware |
| BiotechAnalyst | Commercial viability, market sizing, competitive landscape |
| Clinician | Practicing physician, grounds arguments in patient outcomes |
| PatientAdvocate | Represents patient community, access and tolerability focus |
| Biostatistician | Trial design rigor, statistical methodology, endpoint analysis |
| CompetitorScientist | Researcher at rival company, critical lens on methodology |

### Ontology Extraction (prompts/ontology.md)

Guide the LLM to extract entity types relevant to clinical trials from seed documents. Focus on identifying:
- Named researchers, institutions, pharmaceutical companies, regulatory bodies
- Their role relative to the trial (investigator, sponsor, regulator, competitor)
- Relationships like "sponsors", "reviews", "competes with", "advocates for"

### Persona Generation (prompts/persona.md and persona_batch.md)

Each persona should include:
- **Professional lens:** What they prioritize (efficacy data, safety, commercial viability, patient access)
- **Risk tolerance:** How much ambiguity they accept before recommending approval/rejection
- **Evidence standards:** What quality of evidence they require (RCT-only vs pragmatic data)
- **Communication style:** MedTwitter tone (data-heavy, patient-centered, regulatory-cautious, commercially-minded)
- **Bio:** 160-char tagline that sounds like a real medical professional's Twitter bio

`persona.md` generates one persona at a time (fallback). `persona_batch.md` generates all personas in a single LLM call (preferred path).

### Agent Behavior (prompts/agent_system.md)

Each persona type receives specific behavioral guidance:

- **ClinicalResearchers** discuss mechanism of action, preclinical data, prior trial history, patient selection
- **FDAReviewers** focus on safety signals, adverse events, incomplete data, regulatory precedent for similar drugs
- **BiotechAnalysts** evaluate commercial potential, addressable market, pricing strategy, competitive positioning
- **Clinicians** ground arguments in clinical practice ("my patients would benefit/struggle because...")
- **PatientAdvocates** push for access, highlight unmet need, raise tolerability and quality-of-life concerns
- **Biostatisticians** challenge trial methodology, endpoint selection, statistical powering, subgroup analyses
- **CompetitorScientists** highlight design weaknesses, question differentiation from existing treatments

All agents should:
- Reference specific data from the seed documents (effect sizes, p-values, safety data)
- Be willing to disagree with each other based on their professional lens
- Acknowledge uncertainty where the evidence is genuinely ambiguous
- Distinguish between scientific merit and regulatory/commercial viability

### Report Output (prompts/report_guidelines.md)

Two-section report:

**Section 1 — Trial Outcome Probability:**
- Probability of success (meeting primary endpoint / gaining approval) with confidence percentage
- Key efficacy signals and their strength
- Top safety concerns and their severity
- Regulatory pathway assessment (standard review, priority, breakthrough, accelerated)
- Comparison to historical approval rates for similar drug class/indication

**Section 2 — Advisory Panel Simulation:**
- Each persona casts a vote: **Approve** / **Reject** / **Request More Data**
- 2-3 sentence rationale per vote citing specific evidence
- Final vote tally
- Summary of what divided the panel
- What additional data would resolve the key disagreements

### Simulation Config (prompts/config_gen.md)

- Moderate simulation length (48-120 hours simulated time) reflecting deliberate scientific discourse
- More evenly distributed activity (scientific debate isn't bound to market hours)
- Seed posts should frame the key efficacy and safety questions from the trial data

---

## Domain 3: genomics

### Purpose

Simulate a ClinGen-style expert panel debating the pathogenicity classification of a genetic variant. Produces an ACMG 5-tier classification vote plus a structured evidence weight map showing which experts contributed what evidence.

### Seed Documents

Genomic database entries: ClinVar submissions, gnomAD allele frequency data, OMIM disease records. May also include case reports or functional study data.

**Example seed document for testing:** A ClinVar entry for a BRCA2 missense variant with conflicting interpretations, combined with gnomAD frequency data and an OMIM entry for the associated hereditary breast cancer syndrome.

### Manifest (manifest.yaml)

```yaml
name: genomics
version: "1.0"
description: >
  Genetic variant pathogenicity classification. Simulates a ClinGen-style
  expert panel where clinical geneticists, bioinformaticians, functional
  biologists, genetic counselors, population geneticists, molecular
  pathologists, and ClinGen curators debate variant classification using
  ACMG/AMP criteria.
language: en
sim_engine: claude
platforms:
  - reddit
prompts:
  ontology: prompts/ontology.md
  persona: prompts/persona.md
  persona_batch: prompts/persona_batch.md
  report_guidelines: prompts/report_guidelines.md
  config_generation: prompts/config_gen.md
  agent_system: prompts/agent_system.md
ontology:
  hints: ontology/hints.yaml
  max_entity_types: 10
  required_fallbacks:
    - Person
    - Organization
```

Note: Reddit platform chosen over Twitter because ACMG evidence code arguments require longer-form discussion that would be artificially constrained by short-form post limits.

### Entity Types (ontology/hints.yaml)

| Type | Description |
|------|-------------|
| ClinicalGeneticist | Patient-facing diagnostic interpretation, phenotype correlation |
| Bioinformatician | Computational analysis, population frequency, in-silico predictors |
| FunctionalBiologist | Wet-lab evidence, protein impact, model organism data |
| GeneticCounselor | Patient communication, clinical actionability, family implications |
| PopulationGeneticist | Allele frequency across ancestries, founder effects, selection pressure |
| MolecularPathologist | Somatic vs germline context, tumor genomics perspective |
| ClinGenCurator | Standards adherence, ACMG/AMP evidence code application |

### Ontology Extraction (prompts/ontology.md)

Guide the LLM to extract entity types relevant to genomics from seed documents. Focus on identifying:
- Named researchers, labs, clinical genetics centers, database contributors
- Their expertise area (computational, functional, clinical, population)
- Relationships like "submitted to ClinVar", "studies gene", "specializes in", "disagrees with"

### Persona Generation (prompts/persona.md and persona_batch.md)

Each persona should include:
- **Expertise area:** Primary evidence type they work with (computational, functional, clinical, population)
- **Classification tendency:** Conservative (leans VUS when uncertain) vs assertive (willing to classify with less evidence)
- **Evidence standards:** What they consider strong vs supporting evidence in their area
- **Communication style:** Scientific forum tone (data-heavy, citation-rich, methodical)
- **Bio:** 160-char tagline that sounds like a real genetics professional's profile

`persona.md` generates one persona at a time (fallback). `persona_batch.md` generates all personas in a single LLM call (preferred path).

### Agent Behavior (prompts/agent_system.md)

Each persona type receives specific behavioral guidance:

- **Bioinformaticians** cite allele frequencies (gnomAD subpopulations), in-silico predictors (CADD, REVEL, SIFT, PolyPhen), conservation scores, splice prediction tools
- **FunctionalBiologists** weigh knockout studies, protein functional assays, model organism phenotypes, structural modeling
- **ClinicalGeneticists** anchor to patient phenotype, family segregation data, penetrance estimates, genotype-phenotype correlations
- **ClinGenCurators** enforce ACMG/AMP evidence codes (PS1-4, PM1-6, PP1-5, BS1-4, BP1-7), flag when codes are misapplied, ensure consistent framework use
- **PopulationGeneticists** analyze frequency data across gnomAD subpopulations, flag founder effects, assess whether frequency is consistent with disease prevalence
- **GeneticCounselors** consider clinical actionability, patient/family implications, whether reclassification would change management
- **MolecularPathologists** distinguish germline vs somatic context, consider tumor mutational burden, assess variant in context of cancer genomics

All agents should:
- Reference specific ACMG/AMP evidence codes when making arguments
- Cite data from the seed documents (allele frequencies, functional scores)
- Distinguish between strong, moderate, and supporting levels of evidence
- Be explicit about uncertainty, especially for VUS-adjacent classifications

### Report Output (prompts/report_guidelines.md)

Two-section report:

**Section 1 — Classification Vote:**
- Each persona votes on the ACMG 5-tier scale: **Pathogenic** / **Likely Pathogenic** / **VUS** / **Likely Benign** / **Benign**
- 2-3 sentence rationale per vote citing specific ACMG/AMP evidence codes applied
- Final consensus classification with vote tally
- Confidence level and what would change the classification

**Section 2 — Evidence Weight Map:**
- Structured breakdown by ACMG evidence category:
  - **Population data** (BS1, PM2): allele frequencies, population-specific considerations
  - **Computational/predictive** (PP3, BP4): in-silico predictor results, conservation
  - **Functional** (PS3, BS3): assay results, model organism data
  - **Segregation** (PP1, BS4): family co-segregation data
  - **De novo** (PS2, PM6): parental testing results
  - **Allelic** (PM3, BP2): cis/trans configuration with known pathogenic variants
  - **Clinical** (PP4, BP5): phenotype specificity, alternative genetic causes
- Which experts contributed to each category
- Strength of evidence per category (strong / moderate / supporting / absent)

### Simulation Config (prompts/config_gen.md)

- Shorter simulations (12-36 hours simulated time) reflecting a focused expert panel review
- Even activity distribution (expert panels don't have peak hours)
- Seed posts should present the variant with available evidence and frame the classification question

---

## Shared Patterns

All three domains share these design decisions:

- **Sim engine:** Claude
- **Fallback:** `_default` for any prompt not overridden
- **All prompts overridden:** Each domain provides all 6 prompts (ontology, persona, persona_batch, config_gen, agent_system, report_guidelines) since these are specialized domains where defaults wouldn't be appropriate
- **Persona batch generation:** All three domains use `persona_batch.md` for efficiency (single LLM call for all profiles)
- **Required fallbacks:** Person and Organization (consistent with existing domains)

**Platform choices:**
- prediction-markets: Twitter (fast-moving financial debate, short-form)
- medical-trials: Twitter (MedTwitter is a well-established discourse format)
- genomics: Reddit (ACMG evidence arguments need longer-form discussion)

## File Inventory

Each domain creates 9 files:

```
domains/{domain}/
├── manifest.yaml
├── prompts/
│   ├── ontology.md
│   ├── persona.md
│   ├── persona_batch.md
│   ├── config_gen.md
│   ├── agent_system.md
│   └── report_guidelines.md
└── ontology/
    └── hints.yaml
```

**Total: 27 new files across 3 domains. Zero code changes.**

## Success Criteria

- Each domain loads correctly via `load_domain()` with no errors
- Entity extraction produces the expected entity types from representative seed documents
- Generated personas reflect domain-specific behavioral guidance
- Simulations produce substantive, in-character debate
- Reports follow the two-section format specified for each domain
- Existing domains and tests are unaffected
