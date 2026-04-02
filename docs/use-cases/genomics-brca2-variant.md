# Use Case: Genomics — BRCA2 Variant Classification (c.7007G>A)

## Overview

This use case demonstrates using ForkCast to simulate how a panel of genetics experts would classify a BRCA2 missense variant with conflicting clinical interpretations, using the ACMG/AMP evidence framework.

**Date tested:** 2026-04-01
**Engine:** Claude (tool-use)
**Platform:** Reddit (longer-form discussions suited to evidence-based argumentation)
**LLM Provider:** Ollama (llama3.1, fully local — zero API cost)
**Result:** Full pipeline working end-to-end (project -> graph -> sim -> run -> report)

## The Scenario

BRCA2 c.7007G>A (p.Arg2336His) is a missense variant in the DNA-binding domain with **conflicting interpretations** in ClinVar:
- **GeneDx** classifies it as **Likely Pathogenic** (PM2, PP3, PM1, PP5)
- **Ambry Genetics** classifies it as **VUS** (PM2, PP3, but BS3_supporting based on 68% residual HR activity)
- **Invitae** classifies it as **Likely Pathogenic** using updated functional thresholds (Findlay et al.)

The core disagreement: does 68% residual homologous recombination activity in a functional assay constitute loss of function? The answer depends on whether you apply the original 40% threshold or updated Findlay-derived thresholds where <80% correlates with clinical pathogenicity.

One seed document was provided:
- **ClinVar submission summary** — Complete variant data including all three submitter classifications, population data (absent from gnomAD), computational predictions (REVEL 0.89, CADD 28.4), protein context (OB1 fold, DNA-binding domain), functional assay results, and clinical case data (11 carriers, 7 with breast cancer including 2 male)

The question: **What is the most defensible ACMG classification for BRCA2 p.Arg2336His, and what additional evidence would resolve the discrepancy?**

## Step-by-Step Workflow

### 1. Create Project

```bash
forkcast project create \
  --name "BRCA2 R2336H Classification" \
  --domain genomics \
  --requirement "Evaluate BRCA2 c.7007G>A (p.Arg2336His) using the ACMG/AMP framework. Determine the most defensible classification given conflicting ClinVar submissions, and identify what evidence would resolve the discrepancy."
```

### 2. Build Knowledge Graph

ForkCast extracts genomic entities — the gene, variant, protein domains, functional assays, clinical submissions, and evidence relationships.

```bash
forkcast project build-graph {project_id}
```

**Result:** Entities included BRCA2, p.Arg2336His, OB1 DNA-binding domain, RAD51 interaction pathway, three ClinVar submitters, functional assay results, gnomAD population data, and ACMG evidence codes.

### 3. Create & Prepare Simulation

The LLM generates 22 agent profiles representing the variant curation ecosystem.

```bash
forkcast sim create {project_id} --platforms reddit
forkcast sim prepare {simulation_id} --provider ollama --model llama3.1
```

**Agents generated (22):**

| Archetype | Count | Role in Simulation |
|-----------|-------|--------------------|
| Clinical Geneticist | 4 | Evaluate clinical significance, patient management implications |
| Bioinformatician | 3 | Analyze computational predictions, conservation scores, structural models |
| Functional Biologist | 3 | Interpret assay results, debate thresholds, assess experimental limitations |
| Genetic Counselor | 3 | Advocate for actionable classification, patient communication needs |
| Population Geneticist | 3 | Assess allele frequency data, population stratification |
| Molecular Pathologist | 3 | Evaluate pathology-level evidence, tissue-specific expression |
| ClinGen Curator | 3 | Apply formal ACMG rule specifications, standardize evidence weighting |

### 4. Run Simulation

```bash
forkcast sim start {simulation_id} --provider ollama --model llama3.1
```

**Results:**
- **87 total actions** across multiple rounds
- **22 agents** actively participating
- Reddit format enabled longer evidence-based posts with ACMG code citations
- Primary debate: functional assay threshold interpretation (40% vs 80% cutoff)

### 5. Generate Report

```bash
forkcast report generate {simulation_id} --provider ollama --model llama3.1
```

## Key Findings from the Report

### Classification Vote: Likely Pathogenic (majority), VUS (minority dissent)

The simulation produced a structured expert panel deliberation:

**Vote distribution: ~15 Likely Pathogenic, ~7 VUS**

**The three key evidence debates:**

1. **The functional threshold controversy (PS3 strength)** — This was the central disagreement, mirroring the real ClinVar discrepancy. Functional biologist agents were split:
   - *Pro-LP camp:* 68% residual HR activity falls below the Findlay-derived 80% threshold. The mESC viability data (72% at day 6) and cisplatin sensitivity (1.4x) provide corroborating evidence of partial loss of function. Applied as PS3_moderate.
   - *Pro-VUS camp:* The Findlay thresholds were derived from BRCA1, not BRCA2. Direct transferability hasn't been validated. The original 40% threshold from Guidugli et al. should apply, making this BS3_supporting. "Extrapolating thresholds across paralogs is methodologically unsound."

2. **Clinical case data weight (PP1/PS4)** — ClinGen curators noted 11 carriers with 7 cancers (including 2 male breast cancers, which are strongly BRCA2-associated). The LOD score of 0.9 is below the PP1_strong threshold (>3.0) but the 2 male breast cancer cases add qualitative weight. Population geneticist agents emphasized that absence from all gnomAD populations (0/251,346 alleles) is strongly informative for a missense variant in a well-studied gene.

3. **Computational evidence convergence (PP3)** — Bioinformatician agents achieved near-consensus: REVEL 0.89, CADD 28.4, AlphaMissense 0.92, and extreme conservation (GERP++ 5.81, PhyloP 9.12) all point the same direction. Six independent predictors agreeing provides high confidence in PP3. The ClinGen BRCA2 expert panel specification requires REVEL >= 0.7, which is clearly met.

**The decisive argument:**
ClinGen curator agents synthesized the evidence into a formal ACMG classification:
- PM2 (absent from controls) — Met
- PP3 (computational evidence) — Met (REVEL 0.89, exceeds ClinGen threshold of 0.7)
- PM1 (critical functional domain) — Met (OB1 fold, R2336 within 3.2A of ssDNA)
- PS3_moderate (functional evidence using updated thresholds) — Contested but majority accepted
- PP1_supporting (co-segregation, LOD 0.9) — Met at supporting level

Combining PM2 + PP3 + PM1 + PS3_moderate = **Likely Pathogenic** under standard ACMG point-based combination rules.

The VUS minority position held that without PS3, the remaining evidence (PM2 + PP3 + PM1 + PP1_supporting) only reaches VUS — and PS3 depends on the contested threshold extrapolation.

### What Evidence Would Resolve the Discrepancy?

The panel identified three data types that would be definitive:

1. **BRCA2-specific saturation genome editing data** — A Findlay-equivalent study for BRCA2 would establish gene-specific functional thresholds and eliminate the paralog extrapolation concern. Several labs are conducting this work.
2. **Additional segregation data** — More families with this variant would increase the LOD score. Current LOD 0.9 from one family is suggestive but not sufficient for PP1_strong.
3. **Structural biochemistry** — Purified R2336H protein binding assays measuring actual ssDNA affinity would directly test the structural prediction that the salt bridge disruption impairs DNA binding.

### What the Simulation Revealed About Variant Classification

1. **Expert disagreement is principled, not random** — The VUS vs LP split maps directly to a methodological question (threshold extrapolation across paralogs), not to different readings of the same data. The simulation made this structure visible.
2. **Evidence hierarchies matter** — The same variant with the same data gets different classifications depending on whether you weight functional assays (favoring VUS) or clinical observations + computational convergence (favoring LP).
3. **Genetic counselor perspective is distinct** — Counselor agents consistently pushed for actionable classifications, noting that a VUS for a BRCA2 variant in a patient with breast cancer creates clinical uncertainty that affects screening decisions. This "what do we tell the patient?" framing influenced some curators toward LP.
4. **Male breast cancer cases are disproportionately informative** — Multiple agents flagged that 2/11 carriers having male breast cancer (base rate ~1% of all breast cancers, but strongly BRCA2-associated) provides informal but persuasive evidence that this variant is functional.

## Domain-Specific Features

The genomics domain uses specialized prompt templates:
- **Persona template** — Each agent has defined expertise areas, ACMG proficiency level, and evidence evaluation philosophy
- **Agent system prompt** — Agents cite specific ACMG evidence codes (PS3, PM2, PP3, etc.) and argue for evidence strengths using the 4-tier system (supporting/moderate/strong/very strong)
- **Report guidelines** — The analyst produces a classification vote tally, maps evidence code assignments, and identifies resolution pathways
- **Reddit platform** — Longer-form posting enables the detailed evidence arguments that variant classification requires

## Limitations

1. **No database access** — Real variant classification requires querying ClinVar, gnomAD, UniProt, and PDB in real-time. The simulation works from a single seed document that pre-summarizes this data.
2. **ACMG nuance** — The full ACMG/AMP framework has complex combination rules, strength modifications, and gene-specific specifications. The simulation captures the deliberative process but doesn't mechanically apply the Bayesian point system.
3. **Local model depth** — Ollama/llama3.1 agents produced functional evidence arguments but occasionally mixed up evidence code semantics (e.g., confusing PP3 and PM5). Claude would provide more precise ACMG reasoning.
4. **Single variant** — This case study covers one variant. A production genomics workflow would process batches of variants from a clinical sequencing panel.

## Future Enhancements

- **Post-processing framework** — Extract structured classifications (5-tier ACMG class, per-code evidence assignments, confidence intervals) from simulation output
- **Domain-specific research tools** — Add tools for ClinVar API queries, gnomAD allele frequency lookup, protein structure visualization, and ACMG point calculation
- **Variant batch mode** — Process multiple variants from a VCF file, with per-variant expert panel simulations
- **Gene-specific rule integration** — Load ClinGen expert panel specifications (e.g., BRCA2-specific PP3 thresholds) as additional domain context
