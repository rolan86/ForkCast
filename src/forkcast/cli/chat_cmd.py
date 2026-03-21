"""CLI commands for interactive chat."""

import sys

import typer

from forkcast.config import get_settings
from forkcast.llm.client import ClaudeClient

chat_app = typer.Typer(help="Chat with report agent or simulation agents", no_args_is_help=True)


@chat_app.command("report")
def chat_report(report_id: str):
    """Interactive chat with the report agent about a generated report."""
    from forkcast.report.chat import report_chat

    settings = get_settings()
    client = ClaudeClient(api_key=settings.claude_api_key)

    typer.echo(f"Chatting with report agent (report {report_id}). Type 'exit' to quit.\n")

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nGoodbye!")
            break

        if not message or message.lower() == "exit":
            typer.echo("Goodbye!")
            break

        sys.stdout.write("Agent: ")
        for event in report_chat(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            report_id=report_id,
            message=message,
            client=client,
            domains_dir=settings.domains_dir,
        ):
            if event.type == "text_delta":
                sys.stdout.write(event.data)
                sys.stdout.flush()
            elif event.type == "error":
                typer.echo(f"\nError: {event.data}", err=True)
        sys.stdout.write("\n\n")


@chat_app.command("agent")
def chat_agent(simulation_id: str, agent_id: int):
    """Interactive chat with a simulation agent in character."""
    from forkcast.report.agent_chat import agent_chat

    settings = get_settings()
    client = ClaudeClient(api_key=settings.claude_api_key)

    typer.echo(f"Chatting with agent {agent_id} from simulation {simulation_id}. Type 'exit' to quit.\n")

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nGoodbye!")
            break

        if not message or message.lower() == "exit":
            typer.echo("Goodbye!")
            break

        sys.stdout.write("Agent: ")
        for event in agent_chat(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            agent_id=agent_id,
            message=message,
            client=client,
            domains_dir=settings.domains_dir,
        ):
            if event.type == "text_delta":
                sys.stdout.write(event.data)
                sys.stdout.flush()
            elif event.type == "error":
                typer.echo(f"\nError: {event.data}", err=True)
        sys.stdout.write("\n\n")
