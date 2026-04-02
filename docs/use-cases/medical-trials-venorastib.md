# Use Case: Medical Trials — Venorastib FDA Approval Prediction

## Overview

This use case demonstrates using ForkCast to simulate how clinical, regulatory, and financial stakeholders would evaluate a Phase 3 oncology trial and predict the likelihood of FDA approval.

**Date tested:** 2026-04-01
**Engine:** Claude (tool-use)
**Platform:** Twitter
**LLM Provider:** Ollama (llama3.1, fully local — zero API cost)
**Result:** Full pipeline working end-to-end (project -> graph -> sim -> run -> report)

## The Scenario

Venorastib (VEN-401), a novel CDK4/6 inhibitor developed by fictional Axelion Therapeutics, has completed its Phase 3 APEX-1 trial in HR+/HER2- metastatic breast cancer. The trial met its primary endpoint (median PFS 18.2 months vs 12.7 months for palbociclib, HR 0.62, p<0.001), but a concerning hepatotoxicity signal emerged: 8.4% Grade 3-4 ALT elevations vs 2.1% with palbociclib.

Two seed documents were provided:
- **Phase 3 trial publication** (NEJM-style) — Full trial results including efficacy, safety, subgroup analyses, and quality-of-life data
- **Equity research note** (Barclays-style) — Buy-side analysis covering commercial model, competitive landscape, FDA precedent, and probability-weighted revenue scenarios

The question: **Will the FDA approve Venorastib, and if so, with what label restrictions?**

## Step-by-Step Workflow

### 1. Create Project

```bash
forkcast project create \
  --name "Venorastib FDA Approval Prediction" \
  --domain medical-trials \
  --requirement "Based on Phase 3 APEX-1 trial data, predict whether Venorastib will receive FDA approval and what label restrictions or post-marketing requirements are likely."
```

### 2. Build Knowledge Graph

ForkCast extracts clinical entities — the drug, comparators, endpoints, safety signals, regulatory bodies, and their relationships.

```bash
forkcast project build-graph {project_id}
```

**Result:** Entities included Venorastib, palbociclib (comparator), APEX-1 trial, key efficacy endpoints, hepatotoxicity signal, FDA ODAC, Axelion Therapeutics, and competing CDK4/6 inhibitors.

### 3. Create & Prepare Simulation

The LLM generates 24 agent profiles representing the clinical and regulatory ecosystem.

```bash
forkcast sim create {project_id} --platforms twitter
forkcast sim prepare {simulation_id} --provider ollama --model llama3.1
```

**Agents generated (24):**

| Archetype | Count | Role in Simulation |
|-----------|-------|--------------------|
| Clinical Researcher | 4 | Evaluate trial design, statistical rigor, clinical significance |
| FDA Reviewer | 3 | Assess benefit-risk, label language, post-marketing requirements |
| Biotech Analyst | 4 | Model commercial value, compare to precedent approvals |
| Clinician | 4 | Ground-truth clinical utility from treating physician perspective |
| Patient Advocate | 3 | Represent patient access, tolerability, quality of life |
| Biostatistician | 3 | Scrutinize statistical methods, subgroup validity, multiplicity |
| Competitor Scientist | 3 | Contextualize against pipeline drugs and competitive landscape |

### 4. Run Simulation

```bash
forkcast sim start {simulation_id} --provider ollama --model llama3.1
```

**Results:**
- **92 total actions** across multiple rounds
- **24 agents** actively participating
- Key debate emerged around the hepatotoxicity signal: is 8.4% Grade 3-4 ALT manageable with monitoring, or is it a label-limiting safety concern?

### 5. Generate Report

```bash
forkcast report generate {simulation_id} --provider ollama --model llama3.1
```

## Key Findings from the Report

### Prediction: FDA Approval Likely, With Risk Mitigation Requirements

The simulation produced a nuanced consensus across the 7 stakeholder archetypes:

**Approval probability: ~75-80% (advisory panel vote: likely 8-4 in favor)**

**Three key debate threads emerged:**

1. **Efficacy is clear, safety is the question** — No agent disputed the PFS benefit (HR 0.62). The debate centered entirely on the hepatotoxicity signal. Clinical researchers noted the 8.4% Grade 3-4 ALT rate is higher than palbociclib but lower than some approved oncology drugs (e.g., idelalisib at ~14%). FDA reviewer agents indicated this would likely require a REMS (Risk Evaluation and Mitigation Strategy) rather than block approval.

2. **Label restrictions will shape commercial value** — Biotech analysts identified three scenarios:
   - *Best case:* Broad label with liver monitoring requirement (~$2.4B peak sales)
   - *Base case:* Second-line restriction after palbociclib failure + REMS (~$1.6B peak sales)
   - *Worst case:* Complete response letter requesting additional safety data (~delay 12-18 months)

3. **Patient advocates shifted the conversation** — Patient advocate agents emphasized that HR+/HER2- metastatic breast cancer patients have limited options after CDK4/6 inhibitor failure. The unmet medical need argument strengthened the approval case, with one agent thread noting: "Patients living with this disease would accept monthly liver monitoring for a 44% reduction in progression risk."

**Emergent dynamics:**
- Clinician agents were the swing vote — initially cautious about hepatotoxicity monitoring burden, they were persuaded by the subgroup data showing the benefit held across age groups and prior treatment lines
- Competitor scientist agents provided the most skeptical analysis, questioning whether the PFS benefit would translate to overall survival
- Biostatistician agents flagged that the subgroup analyses were not pre-specified, moderating confidence in some of the efficacy claims

### What the Simulation Revealed About Trial Evaluation

1. **Stakeholder perspective matters enormously** — The same data point (8.4% ALT elevation) was interpreted as "manageable" by clinicians, "concerning" by regulators, and "commercially impactful" by analysts. The simulation surfaced these framing differences.
2. **Safety narratives have outsized influence** — Even though efficacy was clearly positive, the safety signal dominated the conversation. This mirrors real FDA advisory committees where safety concerns drive the most heated debate.
3. **Patient voice changes calculus** — When patient advocates entered the conversation, the framing shifted from "is this safe enough?" to "does the benefit justify the monitoring burden?" — a subtle but important reframe.

## Domain-Specific Features

The medical-trials domain uses specialized prompt templates:
- **Persona template** — Each agent has clinical expertise areas, regulatory philosophy, and evidence evaluation style
- **Agent system prompt** — Agents evaluate trial data through their professional lens, citing specific endpoints and safety data
- **Report guidelines** — The analyst produces an approval probability estimate, identifies key risk factors, and maps the stakeholder consensus

## Limitations

1. **Simplified regulatory process** — Real FDA review involves pre-NDA meetings, rolling submissions, and detailed statistical review. The simulation captures sentiment, not process.
2. **No real comparator data** — The simulation works from two seed documents. Real regulatory prediction would require the full clinical study report, FDA briefing documents, and advisory committee transcripts from precedent drugs.
3. **Local model limitations** — Ollama/llama3.1 produced functional agent reasoning but lacked the depth of domain expertise that Claude would bring to clinical data interpretation.
4. **Twitter format mismatch** — Medical/regulatory discussions are naturally longer-form. Future iterations should use the Reddit platform for this domain.

## Future Enhancements

- **Post-processing framework** — Extract structured predictions (approval probability, label restrictions, timeline) from simulation output
- **Domain-specific research tools** — Add tools for FDA precedent lookup, adverse event comparison across drug classes, and clinical significance calculators
- **Advisory committee simulation mode** — Structured voting rounds that mirror ODAC committee deliberations
