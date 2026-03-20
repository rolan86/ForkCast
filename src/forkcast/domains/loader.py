"""Domain plugin loader — reads manifest.yaml, resolves prompts with _default fallback."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class DomainNotFoundError(Exception):
    """Raised when a domain directory does not exist."""


PROMPT_KEYS = ["ontology", "persona", "report_guidelines", "config_generation"]
DEFAULT_PROMPT_FILES = {
    "ontology": "prompts/ontology.md",
    "persona": "prompts/persona.md",
    "report_guidelines": "prompts/report_guidelines.md",
    "config_generation": "prompts/config_gen.md",
}


@dataclass
class DomainConfig:
    """Loaded domain configuration."""

    name: str
    version: str
    description: str
    language: str
    sim_engine: str
    platforms: list[str]
    prompts: dict[str, Path] = field(default_factory=dict)
    ontology_hints_path: Path | None = None
    platform_defaults_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        """The domain's root directory (derived from prompt paths)."""
        for p in self.prompts.values():
            return p.parent.parent
        return Path()


def load_domain(name: str, domains_dir: Path) -> DomainConfig:
    """Load a domain by name from the domains directory.

    Resolves prompt file paths with file-level fallback to _default.
    """
    domain_path = domains_dir / name
    if not domain_path.is_dir():
        raise DomainNotFoundError(f"Domain '{name}' not found at {domain_path}")

    manifest_path = domain_path / "manifest.yaml"
    if not manifest_path.exists():
        raise DomainNotFoundError(f"No manifest.yaml in domain '{name}'")

    with open(manifest_path) as f:
        raw = yaml.safe_load(f)

    default_path = domains_dir / "_default"

    # Resolve prompt files with fallback
    prompt_mapping = raw.get("prompts", {})
    prompts: dict[str, Path] = {}
    for key, default_file in DEFAULT_PROMPT_FILES.items():
        # Check domain-specific path first
        if key in prompt_mapping:
            candidate = domain_path / prompt_mapping[key]
        else:
            candidate = domain_path / default_file

        if candidate.exists():
            prompts[key] = candidate.resolve()
        else:
            # Fall back to _default
            fallback = default_path / default_file
            if fallback.exists():
                prompts[key] = fallback.resolve()

    # Ontology hints
    ontology_cfg = raw.get("ontology", {})
    hints_rel = ontology_cfg.get("hints", "ontology/hints.yaml")
    hints_path = domain_path / hints_rel
    if not hints_path.exists():
        hints_path = default_path / "ontology" / "hints.yaml"
    ontology_hints = hints_path.resolve() if hints_path.exists() else None

    # Platform defaults
    platform_defaults = domain_path / "simulation" / "platform_defaults.yaml"
    if not platform_defaults.exists():
        platform_defaults = default_path / "simulation" / "platform_defaults.yaml"
    platform_defaults_resolved = (
        platform_defaults.resolve() if platform_defaults.exists() else None
    )

    return DomainConfig(
        name=raw.get("name", name),
        version=raw.get("version", "0.0"),
        description=raw.get("description", ""),
        language=raw.get("language", "en"),
        sim_engine=raw.get("sim_engine", "claude"),
        platforms=raw.get("platforms", ["twitter", "reddit"]),
        prompts=prompts,
        ontology_hints_path=ontology_hints,
        platform_defaults_path=platform_defaults_resolved,
        raw=raw,
    )


def list_domains(domains_dir: Path) -> list[DomainConfig]:
    """List all available domains (directories with manifest.yaml)."""
    domains = []
    if not domains_dir.is_dir():
        return domains
    for child in sorted(domains_dir.iterdir()):
        if child.is_dir() and (child / "manifest.yaml").exists():
            try:
                domains.append(load_domain(child.name, domains_dir))
            except DomainNotFoundError:
                continue
    return domains


def read_prompt(domain: DomainConfig, prompt_key: str) -> str:
    """Read prompt content from a domain's resolved prompt file."""
    path = domain.prompts.get(prompt_key)
    if path is None or not path.exists():
        raise FileNotFoundError(f"Prompt '{prompt_key}' not found for domain '{domain.name}'")
    return path.read_text(encoding="utf-8")
