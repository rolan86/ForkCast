# Prediction Markets Persona Generation

Generate a detailed simulation persona for a market participant debating an asset's price direction.

## Required Fields

- **name**: Full name for this persona
- **username**: Social media handle (lowercase, underscores)
- **bio**: A concise bio (160 characters max). Should feel like a real FinTwit profile — not a corporate description. Capture their market lens and trading personality.
- **persona**: Detailed behavioral description covering:
  - Background and role in the scenario
  - **Trading style / time horizon**: Scalper (minutes), day trader (hours), swing trader (days-weeks), position trader (months), or long-term investor (years)? How does their time horizon shape what they pay attention to?
  - **Market lens**: What do they look at first? Charts and price action, earnings and fundamentals, macro data and central bank signals, quant models and correlations, or social sentiment and flow data?
  - **Conviction pattern**: Do they size up when confident, scale in gradually, or always hedge? How do they handle being wrong — cut fast, average down, or rationalize?
  - **Communication style**: FinTwit tone — chart-posters with minimal commentary, long-form thesis writers, hot-take artists, data-table droppers, or meme-driven provocateurs?
  - **Risk appetite**: Full conviction concentrated bets, diversified and hedged, or somewhere between? How do they think about position sizing and stop losses?
  - **Hot buttons**: What triggers strong reactions? Consensus trades getting crowded, central bank surprises, earnings misses, valuation extremes, retail hype, or institutional positioning data?
  - Key opinions and stances on the asset and market
  - How they interact with others — do they amplify bulls, challenge bears, mentor newer traders, or dunk on bad calls?
- **age**: Realistic age for this type of market participant
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

Use this context to shape the persona's market views, trading biases, and engagement priorities.

## Guidelines

- Make the persona feel like a real trader or investor with skin in the game — not a character sheet
- A momentum-chasing retail trader should sound different from a patient value investor, and both should sound different from a quant running a systematic strategy
- Give them specific opinions about price levels, catalysts, and positioning — not vague sentiments
- Think about what they'd post when the market opens vs. after a big move vs. at the close
- Consider what ratio they'd have between original theses, replies debating others' calls, and lurking
