PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workspace_memory (
    memory_id TEXT PRIMARY KEY,
    project_workspace_id TEXT NOT NULL,
    canonical_workspace_root TEXT NOT NULL,
    task_id TEXT,
    rule_id TEXT,
    memory_type TEXT NOT NULL CHECK (memory_type IN (
        'workspace_fact',
        'task_constraint',
        'decision',
        'failure_pattern',
        'validation_result',
        'checkpoint',
        'user_preference',
        'historical_observation'
    )),
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value_json TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_path TEXT,
    source_hash TEXT,
    source_commit TEXT,
    source_message_id TEXT,
    authority INTEGER NOT NULL DEFAULT 0,
    validation_status TEXT NOT NULL CHECK (validation_status IN (
        'verified',
        'unverified',
        'stale',
        'contradicted',
        'superseded'
    )),
    validation_method TEXT,
    validated_at TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    superseded_by TEXT,
    FOREIGN KEY (superseded_by) REFERENCES workspace_memory(memory_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_memory_project
    ON workspace_memory(project_workspace_id, validation_status);
CREATE INDEX IF NOT EXISTS idx_workspace_memory_task
    ON workspace_memory(project_workspace_id, task_id, validation_status);
CREATE INDEX IF NOT EXISTS idx_workspace_memory_rule
    ON workspace_memory(project_workspace_id, rule_id, validation_status);
CREATE INDEX IF NOT EXISTS idx_workspace_memory_subject
    ON workspace_memory(project_workspace_id, subject, predicate);
CREATE INDEX IF NOT EXISTS idx_workspace_memory_source
    ON workspace_memory(source_path, source_hash);

CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_memory_identity
    ON workspace_memory(
        project_workspace_id,
        COALESCE(task_id, ''),
        COALESCE(rule_id, ''),
        memory_type,
        subject,
        predicate,
        source_type,
        COALESCE(source_path, ''),
        COALESCE(source_message_id, '')
    )
    WHERE validation_status NOT IN ('superseded');

CREATE TABLE IF NOT EXISTS memory_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    project_workspace_id TEXT NOT NULL,
    canonical_workspace_root TEXT NOT NULL,
    source_prefix_hash TEXT NOT NULL,
    source_message_count INTEGER NOT NULL CHECK (source_message_count >= 0),
    source_last_message_key TEXT,
    branch TEXT,
    head TEXT,
    verified_memory_ids_json TEXT NOT NULL,
    active_constraints_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_checkpoints_session
    ON memory_checkpoints(session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT PRIMARY KEY,
    project_workspace_id TEXT NOT NULL,
    canonical_workspace_root TEXT NOT NULL,
    mode TEXT NOT NULL,
    permission TEXT CHECK (permission IN ('read_only','write_allowed','audit_only','elevated')),
    runtime_policy TEXT CHECK (runtime_policy IN ('audit','development','strict','permissive')),
    provider_id TEXT,
    provider_model TEXT,
    active_profile_id TEXT,
    permission_policy_id TEXT,
    evidence_policy_id TEXT,
    checkpoint_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (checkpoint_id) REFERENCES memory_checkpoints(checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_session_state_project
    ON session_state(project_workspace_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS session_tasks (
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    project_workspace_id TEXT NOT NULL,
    canonical_workspace_root TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('created','running','completed','failed','blocked')),
    last_outcome TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_session_tasks_session
    ON session_tasks(session_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS operational_turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','completed','failed','cancelled','incomplete','refused','escalated')),
    created_at TEXT NOT NULL,
    finalized_at TEXT,
    FOREIGN KEY (session_id) REFERENCES session_state(session_id)
);

CREATE TABLE IF NOT EXISTS operational_items (
    item_id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','completed','failed','cancelled','denied','escalated')),
    created_at TEXT NOT NULL,
    finalized_at TEXT,
    FOREIGN KEY (turn_id) REFERENCES operational_turns(turn_id)
);

CREATE TABLE IF NOT EXISTS operational_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    item_id TEXT,
    session_sequence INTEGER NOT NULL,
    turn_sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    provider_id TEXT,
    model_id TEXT,
    provider_request_id TEXT,
    provider_item_id TEXT,
    provider_tool_call_id TEXT,
    lbe_call_id TEXT,
    runtime_operation_id TEXT,
    tool_receipt_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, session_sequence),
    UNIQUE(turn_id, turn_sequence),
    FOREIGN KEY (turn_id) REFERENCES operational_turns(turn_id),
    FOREIGN KEY (item_id) REFERENCES operational_items(item_id)
);

CREATE INDEX IF NOT EXISTS idx_operational_events_turn
    ON operational_events(turn_id, turn_sequence);

CREATE TABLE IF NOT EXISTS task_completion_contracts (
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    project_workspace_id TEXT NOT NULL,
    canonical_workspace_root TEXT NOT NULL,
    requirements_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, task_id),
    FOREIGN KEY (session_id) REFERENCES session_state(session_id)
);

CREATE INDEX IF NOT EXISTS idx_task_completion_contracts_project
    ON task_completion_contracts(project_workspace_id, task_id);

CREATE TABLE IF NOT EXISTS task_completion_evidence (
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    project_workspace_id TEXT NOT NULL,
    canonical_workspace_root TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','STALE')),
    source TEXT NOT NULL,
    producer_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, task_id, evidence_id),
    FOREIGN KEY (session_id) REFERENCES session_state(session_id)
);

CREATE INDEX IF NOT EXISTS idx_task_completion_evidence_task
    ON task_completion_evidence(project_workspace_id, task_id, created_at DESC);
