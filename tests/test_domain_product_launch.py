"""Tests for the product-launch domain plugin."""

import yaml
from pathlib import Path

import pytest

from forkcast.domains.loader import load_domain, read_prompt, PROMPT_KEYS


DOMAINS_DIR = Path(__file__).resolve().parent.parent / "domains"


@pytest.fixture
def domain():
    return load_domain("product-launch", DOMAINS_DIR)


class TestManifestAndHints:
    def test_domain_loads_successfully(self, domain):
        assert domain.name == "product-launch"
        assert domain.version == "1.0"
        assert domain.sim_engine == "claude"

    def test_platforms_include_twitter(self, domain):
        assert "twitter" in domain.platforms

    def test_all_prompt_keys_resolved(self, domain):
        for key in PROMPT_KEYS:
            assert key in domain.prompts, f"Missing prompt key: {key}"
            assert domain.prompts[key].exists(), f"Prompt file missing: {domain.prompts[key]}"

    def test_ontology_hints_exist(self, domain):
        assert domain.ontology_hints_path is not None
        assert domain.ontology_hints_path.exists()

    def test_hints_yaml_structure(self, domain):
        with open(domain.ontology_hints_path) as f:
            hints = yaml.safe_load(f)
        assert hints["max_entity_types"] == 10
        assert "Person" in hints["required_fallbacks"]
        assert "Organization" in hints["required_fallbacks"]
        suggested_names = [t["name"] for t in hints["suggested_types"]]
        for expected in ["Buyer", "Competitor", "Investor", "Analyst",
                         "EarlyAdopter", "Partner", "MediaReviewer"]:
            assert expected in suggested_names, f"Missing suggested type: {expected}"


class TestOntologyPrompt:
    def test_ontology_prompt_not_placeholder(self, domain):
        content = read_prompt(domain, "ontology")
        assert content.strip() != "# TODO"
        assert len(content) > 100

    def test_ontology_prompt_mentions_product_launch_entities(self, domain):
        content = read_prompt(domain, "ontology")
        for term in ["buyer", "competitor", "investor", "product"]:
            assert term.lower() in content.lower(), f"Ontology prompt should mention '{term}'"

    def test_ontology_prompt_has_no_jinja_variables(self, domain):
        content = read_prompt(domain, "ontology")
        assert "{{" not in content, "Ontology prompt should be plain text, not Jinja2"


class TestPersonaPrompt:
    def test_persona_prompt_not_placeholder(self, domain):
        content = read_prompt(domain, "persona")
        assert content.strip() != "# TODO"
        assert len(content) > 200

    def test_persona_prompt_has_required_template_variables(self, domain):
        content = read_prompt(domain, "persona")
        for var in ["entity_name", "entity_type", "entity_description",
                     "related_entities", "requirement"]:
            assert var in content, f"Persona prompt should contain template variable '{var}'"

    def test_persona_prompt_mentions_product_launch_dimensions(self, domain):
        content = read_prompt(domain, "persona")
        content_lower = content.lower()
        for concept in ["market position", "risk tolerance", "pricing"]:
            assert concept in content_lower, f"Persona prompt should mention '{concept}'"
