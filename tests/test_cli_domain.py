from typer.testing import CliRunner


runner = CliRunner()


def test_domain_list(tmp_domains_dir, monkeypatch):
    """forkcast domain list should show available domains."""
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.cli.main import app

    result = runner.invoke(app, ["domain", "list"])
    assert result.exit_code == 0
    assert "_default" in result.stdout


def test_domain_create(tmp_domains_dir, monkeypatch):
    """forkcast domain create should scaffold a new domain."""
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.cli.main import app

    result = runner.invoke(
        app,
        [
            "domain",
            "create",
            "--name", "test-cli",
            "--description", "CLI test domain",
            "--language", "en",
            "--engine", "oasis",
            "--platform", "twitter",
            "--platform", "reddit",
        ],
    )
    assert result.exit_code == 0
    assert "test-cli" in result.stdout
    assert (tmp_domains_dir / "test-cli" / "manifest.yaml").exists()
