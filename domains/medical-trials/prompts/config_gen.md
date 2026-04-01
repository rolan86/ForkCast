# Medical Trials Simulation Configuration

Generate simulation parameters for a clinical trial outcome scenario on a MedTwitter-style platform.

## Parameters to Generate

### Time Configuration
- Total simulation hours (48-120 — topline results through advisory committee review; clinical trial discourse unfolds over days, not hours)
- Minutes per round (20-40 — deliberate scientific discourse moves slower than consumer product hype)
- Activity distribution: even throughout the day (clinical discourse is global and not bound to market hours; researchers post at all hours)
- Peak activity windows: first 6 hours after data drops, then sustained discussion over 3-5 days
- Peak multiplier: 1.5-2.5 (initial data release is intense, but discourse is more measured than consumer launches)
- Off-peak multiplier: 0.3-0.6 (higher baseline than consumer — scientists discuss around the clock)

### Event Configuration
- 2-5 initial seed posts to kick off the simulation. These should simulate the data release moment:
  - The sponsor's press release announcing topline results
  - A clinical researcher's first reaction to the efficacy data
  - A biotech analyst's immediate read on approval probability
  - Optionally: a patient advocate's response focused on what this means for patients
  - Optionally: a competitor scientist raising methodological questions
- 3-7 hot topics that will drive conversation (primary endpoint results, safety profile, p-values, comparator choice, patient selection criteria, regulatory pathway, commercial potential)
- Narrative direction: how should the conversation evolve? (e.g., "topline excitement → methodology scrutiny → safety signal debate → subgroup analysis → regulatory pathway discussion → approval probability consensus")

### Agent Configuration (per agent)
Activity and engagement tuned by stakeholder type:
- **ClinicalResearchers**: high activity, data-heavy posts, engage deeply with methodology (activity_level 0.6-0.8, posts_per_hour 0.5-1.5)
- **FDAReviewers**: measured, deliberate, focus on safety signals and regulatory precedent (activity_level 0.3-0.5, posts_per_hour 0.3-0.8)
- **BiotechAnalysts**: fast initial reaction, then model-driven analysis (activity_level 0.5-0.7, posts_per_hour 0.5-1.5)
- **Clinicians**: moderate activity, clinical practice perspective ("my patients would...") (activity_level 0.4-0.6, posts_per_hour 0.3-1.0)
- **PatientAdvocates**: emotionally engaged, focus on access and unmet need (activity_level 0.5-0.8, posts_per_hour 0.5-1.5)
- **Biostatisticians**: selective but impactful, focus on endpoints and powering (activity_level 0.3-0.5, posts_per_hour 0.2-0.8)
- **CompetitorScientists**: lurk first, then raise design questions strategically (activity_level 0.2-0.4, posts_per_hour 0.2-0.5)

Per agent:
- activity_level (0.2-0.8)
- posts_per_hour (0.2-1.5)
- comments_per_hour (0.5-3.0 — replies drive scientific discourse)
- active_hours — when are they online? (broader range than consumer — global scientific community)
- sentiment_bias (-1.0 to 1.0) — derived from position (sponsor-affiliated = positive, competitor = skeptical, independent = near zero)
- stance — 1-sentence summary of their position on the trial outcome
- influence_weight (0.1-1.0) — how much their posts get amplified

### Platform Configuration
- Feed algorithm weights: recency=0.3, popularity=0.3, relevance=0.4 (relevance weighted higher — scientific discourse rewards substance over virality)
- Viral threshold: 4-6 likes (moderate barrier — MedTwitter is a smaller, more engaged community)
- Echo chamber strength: 0.2-0.4 (lower — clinical trial discourse crosses disciplinary boundaries)

## Context

Entities: {{ entities_summary }}
Prediction question: {{ requirement }}

## Output Format

Return ONLY valid JSON as a single flat object containing all parameters. No markdown formatting. No code fences.
