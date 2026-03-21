# ForkCast

**Collective intelligence simulation platform.** ForkCast models how groups of stakeholders interact — surfacing predictions, testing concepts, and revealing emergent narratives through multi-agent simulation.

## What It Does

Upload seed materials (reports, articles, research), describe what you want to predict or explore, and ForkCast constructs a parallel digital world where AI agents simulate social interactions on Twitter/Reddit-like platforms. The result: prediction reports grounded in the collective dynamics of diverse stakeholder perspectives.

**Use cases:** narrative evolution tracking, ad copy A/B testing, script testing, policy impact simulation, crisis scenario modeling, business concept validation.

## Architecture

- **Domain plugins** — File-based domains (manifest + prompts) make ForkCast adaptable to any prediction vertical
- **Dual simulation engines** — Claude (in-process, tool_use-driven) and OASIS (subprocess, file-based IPC), selectable per domain
- **Knowledge graphs** — NetworkX + ChromaDB for entity extraction and relationship mapping
- **Real-time streaming** — SSE for live simulation progress
- **API-first** — Headless FastAPI backend, CLI interface, UI optional

## Quick Start

```bash
# Install
pip install -e .

# Configure
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

# Run the API server
forkcast server start

# Or use the CLI
forkcast project create --name "My Prediction" --requirement "What will happen to AI regulation in 2027?"
forkcast sim create <project-id>
forkcast sim prepare <sim-id>
forkcast sim start <sim-id>
```

## Tech Stack

Python 3.11+ · FastAPI · SQLite · Anthropic Claude API · NetworkX · ChromaDB · Typer CLI · SSE

## License

[AGPL-3.0](LICENSE) — If you use ForkCast in a network service, you must release your source code under the same license.
