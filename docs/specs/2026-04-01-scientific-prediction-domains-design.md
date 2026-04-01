# Scientific Prediction Domains Design

> Date: 2026-04-01
> Branch: `feature/scientific-prediction-domains`
> Approach: Pure Prompt Domains (no code changes)

## Overview

Three new independent domain plugins for ForkCast, each applying collective intelligence simulation to scientific and financial prediction:

1. **prediction-markets** — Asset price direction forecasting
2. **medical-trials** — Drug/trial outcome prediction
3. **genomics** — Variant pathogenicity classification

All three use ForkCast's existing domain plugin system with zero code changes. Each domain is a directory with `manifest.yaml`, customized prompts, and ontology hints.

Future enhancements (recorded in roadmap as Phases 8a/8b):
- **8a:** Custom report post-processing to extract structured data (consensus scores, vote tallies) into JSON
- **8b:** Domain-specific research tools (e.g., `query_clinvar`, `fetch_market_data`)

---

## Domain 1: prediction-markets

### Purpose

Simulate diverse market participants debating asset price direction. Produces a consensus forecast with confidence score backed by full narrative breakdown of bull vs bear arguments.

### Seed Documents

Mixed inputs: earnings reports, SEC filings, analyst notes, news articles, research reports, social media/forum posts about the asset.

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

- **Platform:** Twitter (default) — short-form debate is well-suited to expert disagreement
- **Sim engine:** Claude
- **Fallback:** `_default` for any prompt not overridden
- **All prompts overridden:** Each domain provides all 6 prompts (ontology, persona, persona_batch, config_gen, agent_system, report_guidelines) since these are specialized domains where defaults wouldn't be appropriate
- **Persona batch generation:** All three domains use `persona_batch.md` for efficiency (single LLM call for all profiles)

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
