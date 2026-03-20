"""CLI commands for domain management."""

from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.domains.loader import list_domains
from forkcast.domains.scaffold import DomainExistsError, scaffold_domain

domain_app = typer.Typer(help="Manage domain plugins", no_args_is_help=True)


@domain_app.command("list")
def domain_list():
    """List available domain plugins."""
    settings = get_settings()
    domains = list_domains(settings.domains_dir)

    if not domains:
        typer.echo("No domains found.")
        return

    typer.echo(f"{'Name':<25} {'Language':<10} {'Engine':<10} {'Description'}")
    typer.echo("-" * 80)
    for d in domains:
        typer.echo(f"{d.name:<25} {d.language:<10} {d.sim_engine:<10} {d.description}")


@domain_app.command("create")
def domain_create(
    name: Annotated[str, typer.Option(help="Domain name (directory name)")],
    description: Annotated[str, typer.Option(help="Short description")],
    language: Annotated[str, typer.Option(help="Default language code")] = "en",
    engine: Annotated[str, typer.Option(help="Simulation engine: oasis or claude")] = "claude",
    platform: Annotated[list[str], typer.Option(help="Simulation platform(s)")] = ["twitter", "reddit"],
):
    """Create a new domain plugin with template files."""
    settings = get_settings()
    try:
        path = scaffold_domain(
            name=name,
            description=description,
            language=language,
            sim_engine=engine,
            platforms=platform,
            domains_dir=settings.domains_dir,
        )
        typer.echo(f"Domain '{name}' created at {path}")
    except DomainExistsError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
