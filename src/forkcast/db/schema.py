"""Database schema definitions and migrations."""

SCHEMA_VERSION = 1

TABLES_V1 = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    ontology_json TEXT,
    requirement TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS project_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    text_content TEXT,
    size INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS graphs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'created',
    node_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0,
    file_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS simulations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    graph_id TEXT REFERENCES graphs(id),
    status TEXT NOT NULL DEFAULT 'created',
    engine_type TEXT NOT NULL DEFAULT 'oasis',
    platforms TEXT NOT NULL DEFAULT '["twitter","reddit"]',
    config_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS simulation_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    agent_name TEXT,
    action_type TEXT NOT NULL,
    content TEXT,
    platform TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'created',
    outline_json TEXT,
    content_markdown TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    tool_calls_json TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    stage TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_graphs_project ON graphs(project_id);
CREATE INDEX IF NOT EXISTS idx_simulations_project ON simulations(project_id);
CREATE INDEX IF NOT EXISTS idx_actions_simulation ON simulation_actions(simulation_id);
CREATE INDEX IF NOT EXISTS idx_actions_round ON simulation_actions(simulation_id, round);
CREATE INDEX IF NOT EXISTS idx_reports_simulation ON reports(simulation_id);
CREATE INDEX IF NOT EXISTS idx_chat_report ON chat_history(report_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id);
"""
