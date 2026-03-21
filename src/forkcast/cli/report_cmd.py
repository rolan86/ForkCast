"""CLI commands for report management."""

import json
from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.client import ClaudeClient
from forkcast.report.pipeline import generate_report

report_app = typer.Typer(help="Manage prediction reports", no_args_is_help=True)


@report_app.command("generate")
def report_generate(simulation_id: str):
    """Generate a report for a completed simulation."""
    settings = get_settings()
    client = ClaudeClient(api_key=settings.claude_api_key)

    typer.echo(f"Generating report for simulation {simulation_id}...")

    def on_progress(**kwargs):
        stage = kwargs.get("stage", "")
        if stage == "tool_call":
            tool = kwargs.get("tool", "")
            round_num = kwargs.get("round", 0)
            typer.echo(f"  [Round {round_num}] Calling {tool}...")
        elif stage == "complete":
            report_id = kwargs.get("report_id", "")
            typer.echo(f"  Report complete: {report_id}")

    try:
        result = generate_report(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
        )
        typer.echo(f"\nReport ID: {result.report_id}")
        typer.echo(f"Tool rounds: {result.tool_rounds}")
        typer.echo(f"Tokens: {result.tokens_used}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@report_app.command("list")
def report_list(
    simulation_id: Annotated[str, typer.Option("--simulation", "-s", help="Filter by simulation")] = None,
):
    """List reports."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        if simulation_id:
            rows = conn.execute(
                "SELECT id, simulation_id, status, created_at FROM reports WHERE simulation_id = ? ORDER BY created_at DESC",
                (simulation_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, simulation_id, status, created_at FROM reports ORDER BY created_at DESC"
            ).fetchall()

    if not rows:
        typer.echo("No reports found.")
        return

    for r in rows:
        typer.echo(f"  {r['id']}  sim={r['simulation_id']}  status={r['status']}  {r['created_at'] or ''}")


@report_app.command("show")
def report_show(report_id: str):
    """Show report details."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()

    if report is None:
        typer.echo(f"Report not found: {report_id}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Report: {report['id']}")
    typer.echo(f"Simulation: {report['simulation_id']}")
    typer.echo(f"Status: {report['status']}")
    typer.echo(f"Created: {report['created_at'] or 'N/A'}")
    if report["content_markdown"]:
        typer.echo(f"\n--- Content Preview ---\n{report['content_markdown'][:500]}")


@report_app.command("export")
def report_export(
    report_id: str,
    output: Annotated[str, typer.Option("-o", "--output", help="Output file path")] = None,
):
    """Export report as markdown."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        report = conn.execute("SELECT content_markdown FROM reports WHERE id = ?", (report_id,)).fetchone()

    if report is None:
        typer.echo(f"Report not found: {report_id}", err=True)
        raise typer.Exit(code=1)

    content = report["content_markdown"] or ""

    if output:
        from pathlib import Path
        Path(output).write_text(content, encoding="utf-8")
        typer.echo(f"Exported to {output}")
    else:
        typer.echo(content)
