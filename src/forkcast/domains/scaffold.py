"""Generate new domain plugin directories from parameters."""

from pathlib import Path

import yaml


class DomainExistsError(Exception):
    """Raised when attempting to create a domain that already exists."""


_PROMPT_TEMPLATES = {
    "ontology.md": (
        "# Ontology Generation\n\n"
        "You are an expert at extracting structured knowledge from text.\n"
        "Given a document and a prediction question, identify the key entity types\n"
        "and relationship types that are relevant to the domain.\n\n"
        "## Instructions\n\n"
        "- Identify entity types that represent real-world actors or concepts\n"
        "- Define relationship types that capture meaningful connections\n"
        "- Ensure entity types can participate in social interactions\n"
    ),
    "persona.md": (
        "# Persona Generation\n\n"
        "Generate a detailed persona for a simulation agent based on the entity\n"
        "extracted from the knowledge graph.\n\n"
        "## Required Fields\n\n"
        "- Bio (200 characters max)\n"
        "- Detailed persona (behavioral patterns, stance, communication style)\n"
        "- Demographics (age, profession, interests)\n"
    ),
    "report_guidelines.md": (
        "# Report Guidelines\n\n"
        "You are analyzing the results of a multi-agent simulation.\n"
        "Generate a comprehensive prediction report based on the emergent behaviors\n"
        "observed during the simulation.\n\n"
        "## Approach\n\n"
        "- Analyze patterns in agent interactions\n"
        "- Identify key narratives and sentiment shifts\n"
        "- Draw conclusions grounded in simulation data\n"
    ),
    "config_gen.md": (
        "# Simulation Configuration\n\n"
        "Generate simulation parameters based on the entities, domain context,\n"
        "and prediction requirements.\n\n"
        "## Parameters to Generate\n\n"
        "- Time configuration (duration, rounds, peak hours)\n"
        "- Event configuration (initial posts, topics)\n"
        "- Agent behavior configuration (activity levels, stances)\n"
        "- Platform configuration (feed algorithm weights)\n"
    ),
}

_HINTS_TEMPLATE = (
    "# Ontology Hints\n"
    "# Domain-specific guidance for entity extraction\n\n"
    "max_entity_types: 10\n"
    "required_fallbacks:\n"
    "  - Person\n"
    "  - Organization\n"
    "\n"
    "# Add domain-specific entity type suggestions below:\n"
    "# suggested_types:\n"
    "#   - name: Analyst\n"
    "#     description: Financial or market analyst\n"
)


def scaffold_domain(
    name: str,
    description: str,
    language: str,
    sim_engine: str,
    platforms: list[str],
    domains_dir: Path,
) -> Path:
    """Create a new domain plugin directory with template files.

    Returns the path to the created domain directory.
    Raises DomainExistsError if the domain already exists.
    """
    domain_path = domains_dir / name
    if domain_path.exists():
        raise DomainExistsError(f"Domain '{name}' already exists at {domain_path}")

    # Create directory structure
    domain_path.mkdir(parents=True)
    (domain_path / "prompts").mkdir()
    (domain_path / "ontology").mkdir()

    # Write manifest
    manifest = {
        "name": name,
        "version": "1.0",
        "description": description,
        "language": language,
        "sim_engine": sim_engine,
        "platforms": platforms,
        "prompts": {
            "ontology": "prompts/ontology.md",
            "persona": "prompts/persona.md",
            "report_guidelines": "prompts/report_guidelines.md",
            "config_generation": "prompts/config_gen.md",
        },
        "ontology": {
            "hints": "ontology/hints.yaml",
            "max_entity_types": 10,
            "required_fallbacks": ["Person", "Organization"],
        },
    }
    with open(domain_path / "manifest.yaml", "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    # Write prompt templates
    for filename, content in _PROMPT_TEMPLATES.items():
        (domain_path / "prompts" / filename).write_text(content, encoding="utf-8")

    # Write ontology hints
    (domain_path / "ontology" / "hints.yaml").write_text(_HINTS_TEMPLATE, encoding="utf-8")

    return domain_path
