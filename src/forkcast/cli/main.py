"""ForkCast CLI — main entry point."""

import typer

from forkcast.cli.domain_cmd import domain_app
from forkcast.cli.project_cmd import project_app
from forkcast.cli.server_cmd import server_app
from forkcast.cli.sim_cmd import sim_app

app = typer.Typer(
    name="forkcast",
    help="ForkCast — Collective intelligence simulation platform",
    no_args_is_help=True,
)

app.add_typer(domain_app, name="domain")
app.add_typer(project_app, name="project")
app.add_typer(server_app, name="server")
app.add_typer(sim_app, name="sim")
