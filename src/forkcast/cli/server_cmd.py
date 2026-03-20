"""CLI command to start the ForkCast API server."""

from typing import Annotated

import typer

server_app = typer.Typer(help="Server management")


@server_app.command("start")
def server_start(
    host: Annotated[str, typer.Option(help="Bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 5001,
    reload: Annotated[bool, typer.Option(help="Enable auto-reload")] = False,
):
    """Start the ForkCast API server."""
    import uvicorn

    typer.echo(f"Starting ForkCast server on {host}:{port}")
    uvicorn.run(
        "forkcast.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
