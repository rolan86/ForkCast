from pathlib import Path

import pytest


def test_load_domain_reads_manifest(tmp_domains_dir):
    """load_domain should parse manifest.yaml and return a DomainConfig."""
    from forkcast.domains.loader import load_domain

    domain = load_domain("_default", tmp_domains_dir)
    assert domain.name == "_default"
    assert domain.language == "en"
    assert domain.sim_engine == "claude"
    assert "twitter" in domain.platforms


def test_load_domain_resolves_prompt_paths(tmp_domains_dir):
    """Prompt paths should be resolved to absolute file paths."""
    from forkcast.domains.loader import load_domain

    domain = load_domain("_default", tmp_domains_dir)
    assert domain.prompts["ontology"].exists()
    assert domain.prompts["ontology"].name == "ontology.md"


def test_load_domain_not_found(tmp_domains_dir):
    """load_domain should raise if domain directory doesn't exist."""
    from forkcast.domains.loader import DomainNotFoundError, load_domain

    with pytest.raises(DomainNotFoundError):
        load_domain("nonexistent", tmp_domains_dir)


def test_load_domain_falls_back_to_default(tmp_domains_dir):
    """If a domain is missing a prompt file, fall back to _default."""
    from forkcast.domains.loader import load_domain

    # Create a minimal custom domain with no prompts
    custom = tmp_domains_dir / "custom"
    custom.mkdir()
    (custom / "manifest.yaml").write_text(
        "name: custom\n"
        "version: '1.0'\n"
        "description: Custom domain\n"
        "language: fr\n"
        "sim_engine: oasis\n"
        "platforms: [reddit]\n"
    )

    domain = load_domain("custom", tmp_domains_dir)
    assert domain.name == "custom"
    assert domain.language == "fr"
    # Prompts should fall back to _default
    assert domain.prompts["ontology"].exists()
    assert "_default" in str(domain.prompts["ontology"])


def test_list_domains(tmp_domains_dir):
    """list_domains should return all domains in the directory."""
    from forkcast.domains.loader import list_domains

    domains = list_domains(tmp_domains_dir)
    assert len(domains) >= 1
    names = [d.name for d in domains]
    assert "_default" in names


def test_read_prompt_returns_content(tmp_domains_dir):
    """read_prompt should return the file content as a string."""
    from forkcast.domains.loader import load_domain, read_prompt

    domain = load_domain("_default", tmp_domains_dir)
    content = read_prompt(domain, "ontology")
    assert "Default ontology.md" in content
