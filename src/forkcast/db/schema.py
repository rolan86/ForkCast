"""Database schema definitions and migrations."""

SCHEMA_VERSION = 5

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

TABLES_V2 = """
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
    tool_history_json TEXT,
    content_markdown TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_actions_agent ON simulation_actions(simulation_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_reports_simulation ON reports(simulation_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id);
"""

TABLES_V3 = """
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
    prep_model TEXT,
    run_model TEXT,
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
    tool_history_json TEXT,
    content_markdown TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_actions_agent ON simulation_actions(simulation_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_reports_simulation ON reports(simulation_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id);
"""

TABLES_V4 = """
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
    prep_model TEXT,
    run_model TEXT,
    agent_mode TEXT DEFAULT 'llm',
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
    tool_history_json TEXT,
    content_markdown TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_actions_agent ON simulation_actions(simulation_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_reports_simulation ON reports(simulation_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id);
"""

TABLES_V5 = """
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
    prep_model TEXT,
    run_model TEXT,
    agent_mode TEXT DEFAULT 'llm',
    total_hours REAL DEFAULT NULL,
    minutes_per_round INTEGER DEFAULT NULL,
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
    tool_history_json TEXT,
    content_markdown TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_actions_agent ON simulation_actions(simulation_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_reports_simulation ON reports(simulation_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id);
"""

MIGRATION_V4_TO_V5 = """
ALTER TABLE simulations ADD COLUMN total_hours REAL DEFAULT NULL;
ALTER TABLE simulations ADD COLUMN minutes_per_round INTEGER DEFAULT NULL;
UPDATE meta SET value = '5' WHERE key = 'schema_version';
"""

MIGRATION_V3_TO_V4 = """
ALTER TABLE simulations ADD COLUMN agent_mode TEXT DEFAULT 'llm';
UPDATE meta SET value = '4' WHERE key = 'schema_version';
"""

MIGRATION_V2_TO_V3 = """
ALTER TABLE simulations ADD COLUMN prep_model TEXT;
ALTER TABLE simulations ADD COLUMN run_model TEXT;
UPDATE meta SET value = '3' WHERE key = 'schema_version';
"""

MIGRATION_V1_TO_V2 = """
-- Recreate chat_history without FK constraint, rename report_id → conversation_id
CREATE TABLE chat_history_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    tool_calls_json TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO chat_history_new (id, conversation_id, role, message, tool_calls_json, timestamp)
    SELECT id, report_id, role, message, tool_calls_json, timestamp FROM chat_history;
DROP TABLE chat_history;
ALTER TABLE chat_history_new RENAME TO chat_history;

-- Rename outline_json → tool_history_json in reports
CREATE TABLE reports_new (
    id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'created',
    tool_history_json TEXT,
    content_markdown TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
INSERT INTO reports_new (id, simulation_id, status, tool_history_json, content_markdown, created_at, completed_at)
    SELECT id, simulation_id, status, outline_json, content_markdown, created_at, completed_at FROM reports;
DROP TABLE reports;
ALTER TABLE reports_new RENAME TO reports;

-- Add new indexes
CREATE INDEX IF NOT EXISTS idx_actions_agent ON simulation_actions(simulation_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_reports_simulation ON reports(simulation_id);

-- Update version
UPDATE meta SET value = '2' WHERE key = 'schema_version';
"""
