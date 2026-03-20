import json
from pathlib import Path


def test_build_graph_from_extraction():
    """Should create a NetworkX graph from extraction results."""
    from forkcast.graph.graph_store import build_graph

    entities = [
        {"name": "Alice", "type": "Person", "description": "A researcher", "attributes": {}},
        {"name": "TechCorp", "type": "Company", "description": "Tech company", "attributes": {}},
    ]
    relationships = [
        {"source": "Alice", "target": "TechCorp", "type": "WORKS_AT", "fact": "Alice works there"},
    ]

    G = build_graph(entities, relationships)
    assert G.number_of_nodes() == 2
    assert G.number_of_edges() == 1
    assert G.nodes["Alice"]["type"] == "Person"
    assert G.edges[("Alice", "TechCorp")]["type"] == "WORKS_AT"


def test_build_graph_handles_missing_nodes():
    """Relationships referencing unknown entities should still create edges."""
    from forkcast.graph.graph_store import build_graph

    entities = [{"name": "Alice", "type": "Person", "description": "A person", "attributes": {}}]
    relationships = [
        {"source": "Alice", "target": "Bob", "type": "KNOWS", "fact": "They know each other"},
    ]

    G = build_graph(entities, relationships)
    assert G.number_of_nodes() == 2
    assert G.has_edge("Alice", "Bob")


def test_save_and_load_graph(tmp_path):
    """Should serialize graph to JSON and reload it identically."""
    from forkcast.graph.graph_store import build_graph, load_graph, save_graph

    entities = [
        {"name": "Alice", "type": "Person", "description": "Researcher", "attributes": {"field": "AI"}},
        {"name": "Bob", "type": "Person", "description": "Engineer", "attributes": {}},
    ]
    relationships = [
        {"source": "Alice", "target": "Bob", "type": "COLLABORATES", "fact": "They work together"},
    ]

    G = build_graph(entities, relationships)
    path = tmp_path / "graph.json"
    save_graph(G, path)

    assert path.exists()
    G2 = load_graph(path)
    assert G2.number_of_nodes() == G.number_of_nodes()
    assert G2.number_of_edges() == G.number_of_edges()
    assert G2.nodes["Alice"]["type"] == "Person"


def test_save_graph_creates_valid_json(tmp_path):
    """The saved file should be valid JSON."""
    from forkcast.graph.graph_store import build_graph, save_graph

    G = build_graph(
        [{"name": "X", "type": "T", "description": "D", "attributes": {}}],
        [],
    )
    path = tmp_path / "graph.json"
    save_graph(G, path)

    data = json.loads(path.read_text())
    assert "nodes" in data
    assert "edges" in data


def test_register_graph_in_db(tmp_db_path):
    """register_graph should insert a row into the graphs table."""
    from forkcast.db.connection import get_db, init_db
    from forkcast.graph.graph_store import register_graph

    init_db(tmp_db_path)
    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('proj_001', '_default', 'Test', 'created', 'Q?', datetime('now'))"
        )

    graph_id = register_graph(tmp_db_path, "proj_001", node_count=5, edge_count=3, file_path="/tmp/graph.json")

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT * FROM graphs WHERE id = ?", (graph_id,)).fetchone()

    assert row is not None
    assert row["project_id"] == "proj_001"
    assert row["node_count"] == 5
    assert row["edge_count"] == 3
    assert row["status"] == "complete"
