"""Data models for the report pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from forkcast.llm.client import LLMClient
from forkcast.simulation.models import AgentProfile


@dataclass
class ReportResult:
    """Result of report generation."""

    report_id: str
    simulation_id: str
    content_markdown: str
    tool_rounds: int
    structured_data: dict | None = None
    tokens_used: dict[str, int] = field(default_factory=dict)


@dataclass
class StreamEvent:
    """A single event from a streaming response."""

    type: str  # "text_delta", "tool_use", "done", "error"
    data: str | dict  # text chunk, tool call dict, stats dict, or error message


@dataclass
class ToolContext:
    """Shared context for all report tools, initialized once per generation."""

    db_path: Path
    simulation_id: str
    project_id: str
    data_dir: Path
    graph: nx.DiGraph
    chroma_collection: Any  # ChromaDB Collection
    profiles: list[AgentProfile]
    client: LLMClient
    domains_dir: Path
