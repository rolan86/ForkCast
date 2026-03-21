"""Tests for chat CLI commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from forkcast.cli.main import app
from forkcast.db.connection import init_db

runner = CliRunner()

# Chat REPL commands are interactive — just test that they register and handle errors
