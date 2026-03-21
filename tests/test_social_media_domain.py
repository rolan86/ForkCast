"""Tests for the social-media domain plugin."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def social_media_domains_dir(tmp_domains_dir):
    """Copy real social-media domain files into tmp_domains_dir for testing.

    This fixture uses the actual domain files from the repository, not stubs.
    It copies them into the temporary test directory alongside _default.
    """
    import shutil

    real_domains = Path(__file__).resolve().parent.parent / "domains"
    social_media_src = real_domains / "social-media"

    if not social_media_src.exists():
        pytest.skip("social-media domain not yet created")

    dest = tmp_domains_dir / "social-media"
    shutil.copytree(social_media_src, dest)
    return tmp_domains_dir


class TestDomainLoading:
    def test_load_social_media_domain(self, social_media_domains_dir):
        """social-media domain should load from manifest.yaml."""
        from forkcast.domains.loader import load_domain

        domain = load_domain("social-media", social_media_domains_dir)
        assert domain.name == "social-media"
        assert domain.sim_engine == "claude"
        assert "twitter" in domain.platforms

    def test_all_five_prompts_resolve_to_social_media(self, social_media_domains_dir):
        """All 5 prompts should resolve to social-media/ paths, not _default/."""
        from forkcast.domains.loader import load_domain

        domain = load_domain("social-media", social_media_domains_dir)
        for key in ["ontology", "persona", "report_guidelines", "config_generation", "agent_system"]:
            assert key in domain.prompts, f"Missing prompt: {key}"
            path = domain.prompts[key]
            assert path.exists(), f"Prompt file missing: {path}"
            assert "social-media" in str(path), f"Prompt {key} fell back to _default: {path}"

    def test_prompts_have_content(self, social_media_domains_dir):
        """Each prompt file should have meaningful content, not just a placeholder."""
        from forkcast.domains.loader import load_domain, read_prompt

        domain = load_domain("social-media", social_media_domains_dir)
        for key in ["ontology", "persona", "report_guidelines", "config_generation", "agent_system"]:
            content = read_prompt(domain, key)
            assert len(content) > 100, f"Prompt {key} is too short ({len(content)} chars) — likely a placeholder"

    def test_ontology_hints_have_social_media_types(self, social_media_domains_dir):
        """Ontology hints should include social-media-specific entity types."""
        from forkcast.domains.loader import load_domain

        domain = load_domain("social-media", social_media_domains_dir)
        assert domain.ontology_hints_path is not None
        assert domain.ontology_hints_path.exists()

        hints = yaml.safe_load(domain.ontology_hints_path.read_text())
        type_names = [t["name"] for t in hints.get("suggested_types", [])]
        # Should have at least some social-media-specific types
        assert len(type_names) >= 5
        assert "Influencer" in type_names or "Brand" in type_names

    def test_manifest_is_twitter_only(self, social_media_domains_dir):
        """social-media domain should be configured for Twitter only."""
        from forkcast.domains.loader import load_domain

        domain = load_domain("social-media", social_media_domains_dir)
        assert domain.platforms == ["twitter"]


class TestDomainFallback:
    def test_missing_prompt_falls_back_to_default(self, social_media_domains_dir):
        """If a social-media prompt file is deleted, it should fall back to _default."""
        from forkcast.domains.loader import load_domain

        # Delete one prompt from social-media
        persona_path = social_media_domains_dir / "social-media" / "prompts" / "persona.md"
        persona_path.unlink()

        domain = load_domain("social-media", social_media_domains_dir)
        assert "persona" in domain.prompts
        assert "_default" in str(domain.prompts["persona"])


class TestDomainListing:
    def test_social_media_appears_in_list(self, social_media_domains_dir):
        """social-media should appear alongside _default in domain list."""
        from forkcast.domains.loader import list_domains

        domains = list_domains(social_media_domains_dir)
        names = [d.name for d in domains]
        assert "_default" in names
        assert "social-media" in names


def test_persona_template_uses_requirement(tmp_domains_dir):
    """Persona template should render the {{ requirement }} variable."""
    from jinja2 import Template

    persona_path = tmp_domains_dir / "_default" / "prompts" / "persona.md"
    template_text = persona_path.read_text()
    template = Template(template_text)
    rendered = template.render(
        entity_name="TestEntity",
        entity_type="Person",
        entity_description="A test entity",
        related_entities="None",
        requirement="Predict social media reaction to AI regulation",
    )
    assert "Predict social media reaction to AI regulation" in rendered
