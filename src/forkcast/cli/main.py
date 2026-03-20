"""ForkCast CLI — main entry point."""

import typer

from forkcast.cli.domain_cmd import domain_app

app = typer.Typer(
    name="forkcast",
    help="ForkCast — Collective intelligence simulation platform",
    no_args_is_help=True,
)

app.add_typer(domain_app, name="domain")
