from typer.testing import CliRunner

runner = CliRunner()


def test_project_list_empty(tmp_data_dir, tmp_domains_dir, monkeypatch):
    """forkcast project list should work with no projects."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    from forkcast.cli.main import app

    result = runner.invoke(app, ["project", "list"])
    assert result.exit_code == 0


def test_project_create(tmp_data_dir, tmp_domains_dir, tmp_path, monkeypatch):
    """forkcast project create should create a project from files."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    # Create a test file to upload
    test_file = tmp_path / "doc.txt"
    test_file.write_text("Some document content for testing.")

    from forkcast.cli.main import app

    result = runner.invoke(
        app,
        ["project", "create", str(test_file), "--domain", "_default", "--prompt", "What will happen?"],
    )
    assert result.exit_code == 0
    assert "proj_" in result.stdout


def test_server_start_help(monkeypatch):
    """forkcast server start --help should show options."""
    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.cli.main import app

    result = runner.invoke(app, ["server", "start", "--help"])
    assert result.exit_code == 0
    assert "host" in result.stdout.lower() or "port" in result.stdout.lower()
