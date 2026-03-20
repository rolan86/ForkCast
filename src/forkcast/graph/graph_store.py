"""NetworkX graph construction, persistence, and querying."""

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from forkcast.db.connection import get_db


def build_graph(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> nx.DiGraph:
    """Build a NetworkX directed graph from entities and relationships."""
    G = nx.DiGraph()

    for entity in entities:
        G.add_node(
            entity["name"],
            type=entity.get("type", "Unknown"),
            description=entity.get("description", ""),
            attributes=entity.get("attributes", {}),
        )

    for rel in relationships:
        source = rel["source"]
        target = rel["target"]
        if source not in G:
            G.add_node(source, type="Unknown", description="", attributes={})
        if target not in G:
            G.add_node(target, type="Unknown", description="", attributes={})

        G.add_edge(
            source,
            target,
            type=rel.get("type", "RELATED"),
            fact=rel.get("fact", ""),
        )

    return G


def save_graph(G: nx.DiGraph, path: Path) -> None:
    """Serialize a NetworkX graph to a JSON file."""
    data = {
        "nodes": [
            {"name": n, **G.nodes[n]}
            for n in G.nodes
        ],
        "edges": [
            {"source": u, "target": v, **G.edges[u, v]}
            for u, v in G.edges
        ],
        "metadata": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_graph(path: Path) -> nx.DiGraph:
    """Load a NetworkX graph from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    G = nx.DiGraph()

    for node in data["nodes"]:
        name = node.pop("name")
        G.add_node(name, **node)

    for edge in data["edges"]:
        source = edge.pop("source")
        target = edge.pop("target")
        G.add_edge(source, target, **edge)

    return G


def register_graph(
    db_path: Path,
    project_id: str,
    node_count: int,
    edge_count: int,
    file_path: str,
) -> str:
    """Register a built graph in the database."""
    graph_id = f"graph_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'complete', ?, ?, ?, ?)",
            (graph_id, project_id, node_count, edge_count, file_path, now),
        )
        conn.execute(
            "UPDATE projects SET status = 'graph_built', updated_at = ? WHERE id = ?",
            (now, project_id),
        )

    return graph_id
