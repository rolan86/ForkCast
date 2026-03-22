"""CLI commands for evaluation."""

import json
from pathlib import Path
from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.eval.runner import run_evaluation
from forkcast.eval.scorecard import load_scorecard, compare_scorecards

eval_app = typer.Typer(help="Evaluate pipeline output quality", no_args_is_help=True)


@eval_app.command("run")
def eval_run(
    project_id: str,
    simulation_id: Annotated[str | None, typer.Option("--simulation-id", help="Simulation ID (default: latest)")] = None,
    report_id: Annotated[str | None, typer.Option("--report-id", help="Report ID (default: latest)")] = None,
    gates_only: Annotated[bool, typer.Option("--gates-only", help="Skip LLM quality judgments")] = False,
):
    """Run evaluation on a completed simulation and report."""
    settings = get_settings()

    # Find latest simulation if not specified
    if simulation_id is None:
        with get_db(settings.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM simulations WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if row is None:
            typer.echo(f"Error: No simulations found for project {project_id}", err=True)
            raise typer.Exit(code=1)
        simulation_id = row["id"]

    # Build LLM client if needed
    client = None
    if not gates_only:
        try:
            from forkcast.llm.client import ClaudeClient
            client = ClaudeClient(api_key=settings.anthropic_api_key)
        except Exception as exc:
            typer.echo(f"Warning: Could not create LLM client ({exc}), running gates only", err=True)
            gates_only = True

    scorecard = run_evaluation(
        db_path=settings.db_path,
        data_dir=settings.data_dir,
        project_id=project_id,
        simulation_id=simulation_id,
        report_id=report_id,
        client=client,
        skip_judgments=gates_only,
    )

    # Display scorecard
    _print_scorecard(scorecard)


@eval_app.command("compare")
def eval_compare(
    eval_file_1: Annotated[Path, typer.Argument(help="Path to first eval JSON")],
    eval_file_2: Annotated[Path, typer.Argument(help="Path to second eval JSON")],
):
    """Compare two evaluation scorecards."""
    sc1 = load_scorecard(eval_file_1)
    sc2 = load_scorecard(eval_file_2)
    diff = compare_scorecards(sc1, sc2)

    typer.echo(f"=== Eval Comparison ===\n")
    typer.echo(f"Gates: {diff['gates_before']} → {diff['gates_after']}")
    typer.echo(f"Quality avg: {diff['quality_avg_before']} → {diff['quality_avg_after']}")
    typer.echo()

    for key, change in diff["quality_changes"].items():
        delta = change["delta"]
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
        typer.echo(f"  {key}: {change['before']} → {change['after']} ({arrow}{abs(delta)})")


def _print_scorecard(scorecard: dict) -> None:
    """Pretty-print a scorecard to terminal."""
    summary = scorecard["summary"]

    typer.echo(f"\n=== ForkCast Evaluation ===")
    typer.echo(f"Project: {scorecard['project_id']} | Simulation: {scorecard['simulation_id']}\n")

    # Gates
    gates = scorecard["gates"]
    typer.echo(f"GATES ({summary['gates_passed']}/{summary['gates_total']} passed)")
    for name, result in gates.items():
        status = "PASS" if result.get("passed") else "FAIL"
        value = result.get("value", "")
        threshold = result.get("threshold", "")
        detail = f": {value}" + (f" (>= {threshold})" if threshold else "")
        typer.echo(f"  [{status}] {name}{detail}")

    # Quality
    quality = scorecard.get("quality", {})
    if quality:
        typer.echo(f"\nQUALITY (Layer 2)")
        weakest = summary.get("weakest")
        for name, result in quality.items():
            score = result.get("score", 0)
            justification = result.get("justification", "")[:60]
            marker = " ← WEAKEST" if name == weakest else ""
            typer.echo(f"  {name}: {score}/5 — \"{justification}\"{marker}")

    typer.echo(f"\nOVERALL: {summary['gates_passed']}/{summary['gates_total']} gates | avg quality {summary['quality_avg']}/5")
    if summary.get("weakest"):
        typer.echo(f"WEAKEST: {summary['weakest']}")
    typer.echo(f"Eval ID: {scorecard['eval_id']}")
