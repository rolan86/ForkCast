from pathlib import Path


def test_scaffold_domain_creates_directory_structure(tmp_domains_dir):
    """scaffold_domain should create the full domain directory."""
    from forkcast.domains.scaffold import scaffold_domain

    result = scaffold_domain(
        name="my-domain",
        description="Test domain for unit testing",
        language="en",
        sim_engine="oasis",
        platforms=["twitter", "reddit"],
        domains_dir=tmp_domains_dir,
    )

    assert result.is_dir()
    assert (result / "manifest.yaml").exists()
    assert (result / "prompts" / "ontology.md").exists()
    assert (result / "prompts" / "persona.md").exists()
    assert (result / "prompts" / "report_guidelines.md").exists()
    assert (result / "prompts" / "config_gen.md").exists()
    assert (result / "ontology" / "hints.yaml").exists()


def test_scaffold_domain_manifest_content(tmp_domains_dir):
    """scaffold_domain manifest should match the input params."""
    import yaml

    from forkcast.domains.scaffold import scaffold_domain

    result = scaffold_domain(
        name="ad-testing",
        description="Ad copy A/B testing",
        language="en",
        sim_engine="claude",
        platforms=["reddit"],
        domains_dir=tmp_domains_dir,
    )

    with open(result / "manifest.yaml") as f:
        manifest = yaml.safe_load(f)

    assert manifest["name"] == "ad-testing"
    assert manifest["description"] == "Ad copy A/B testing"
    assert manifest["sim_engine"] == "claude"
    assert manifest["platforms"] == ["reddit"]


def test_scaffold_domain_refuses_duplicate(tmp_domains_dir):
    """scaffold_domain should refuse to overwrite an existing domain."""
    import pytest

    from forkcast.domains.scaffold import DomainExistsError, scaffold_domain

    scaffold_domain(
        name="unique-domain",
        description="First",
        language="en",
        sim_engine="oasis",
        platforms=["twitter"],
        domains_dir=tmp_domains_dir,
    )

    with pytest.raises(DomainExistsError):
        scaffold_domain(
            name="unique-domain",
            description="Duplicate",
            language="en",
            sim_engine="oasis",
            platforms=["twitter"],
            domains_dir=tmp_domains_dir,
        )


def test_scaffolded_domain_is_loadable(tmp_domains_dir):
    """A scaffolded domain should be loadable by the domain loader."""
    from forkcast.domains.loader import load_domain
    from forkcast.domains.scaffold import scaffold_domain

    scaffold_domain(
        name="loadable",
        description="Should load",
        language="es",
        sim_engine="claude",
        platforms=["twitter", "reddit"],
        domains_dir=tmp_domains_dir,
    )

    domain = load_domain("loadable", tmp_domains_dir)
    assert domain.name == "loadable"
    assert domain.language == "es"
    assert len(domain.prompts) == 5
