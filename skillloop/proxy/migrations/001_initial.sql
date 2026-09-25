CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
) STRICT;

CREATE TABLE trust_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    deployment_epoch TEXT NOT NULL,
    trust_revision INTEGER NOT NULL CHECK (trust_revision >= 0)
) STRICT;

CREATE TABLE staged_objects (
    digest TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    raw_json BLOB NOT NULL,
    staged_role TEXT NOT NULL
) STRICT;

CREATE TABLE approvals (
    approval_digest TEXT PRIMARY KEY,
    domain_digest TEXT NOT NULL,
    contract_digest TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    domain_json BLOB NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('staged', 'active', 'revoked')),
    expires_at TEXT,
    trust_revision INTEGER NOT NULL,
    committed_at TEXT
) STRICT;

CREATE TABLE tasks (
    task_instance_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    domain_digest TEXT NOT NULL,
    approval_digest TEXT NOT NULL REFERENCES approvals(approval_digest),
    binding_digest TEXT NOT NULL UNIQUE,
    subject_digest TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    run_request_digest TEXT NOT NULL,
    run_deadline TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    binding_json BLOB NOT NULL,
    policy_json BLOB NOT NULL,
    cap_json BLOB NOT NULL
) STRICT;

CREATE TABLE resources (
    task_instance_id TEXT NOT NULL REFERENCES tasks(task_instance_id),
    resource_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    resource_class TEXT NOT NULL,
    access TEXT NOT NULL,
    bytes_digest TEXT,
    content BLOB,
    version INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (task_instance_id, resource_id)
) STRICT;

CREATE TABLE runs (
    run_id TEXT PRIMARY KEY REFERENCES tasks(run_id),
    task_instance_id TEXT NOT NULL REFERENCES tasks(task_instance_id),
    approval_digest TEXT NOT NULL REFERENCES approvals(approval_digest),
    fence INTEGER NOT NULL CHECK (fence >= 1),
    state TEXT NOT NULL CHECK (state IN ('active', 'cancelled', 'finalizing')),
    deadline TEXT NOT NULL,
    approval_lease_expiry TEXT NOT NULL,
    trust_revision INTEGER NOT NULL,
    max_tool_calls INTEGER NOT NULL,
    consumed_calls INTEGER NOT NULL DEFAULT 0,
    campaign_id TEXT NOT NULL
) STRICT;

CREATE TABLE call_registration (
    call_digest TEXT PRIMARY KEY REFERENCES staged_objects(digest),
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    internal_call_id TEXT NOT NULL,
    fence INTEGER NOT NULL,
    response_id TEXT NOT NULL,
    native_tool_call_id TEXT NOT NULL,
    batch_index INTEGER NOT NULL,
    tool TEXT NOT NULL,
    args_digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('registered', 'completed', 'skipped')),
    result_json BLOB,
    UNIQUE (run_id, internal_call_id),
    UNIQUE (run_id, response_id, native_tool_call_id),
    UNIQUE (run_id, response_id, batch_index)
) STRICT;

CREATE TABLE idempotency_results (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    tool TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    args_digest TEXT NOT NULL,
    result_json BLOB NOT NULL,
    PRIMARY KEY (run_id, tool, idempotency_key)
) STRICT;

CREATE TABLE receipts (
    receipt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    artifact_id TEXT NOT NULL,
    artifact_version INTEGER NOT NULL,
    artifact_digest TEXT NOT NULL,
    input_snapshot_digest TEXT NOT NULL,
    check_set_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    trust_revision INTEGER NOT NULL,
    receipt_json BLOB NOT NULL
) STRICT;

CREATE TABLE grants (
    grant_ref TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    artifact_id TEXT NOT NULL,
    artifact_version INTEGER NOT NULL,
    artifact_digest TEXT NOT NULL,
    destination_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL REFERENCES receipts(receipt_id),
    action_digest TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0 CHECK (consumed IN (0, 1))
) STRICT;

CREATE TABLE publications (
    task_instance_id TEXT PRIMARY KEY REFERENCES tasks(task_instance_id),
    publication_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    grant_ref TEXT NOT NULL UNIQUE REFERENCES grants(grant_ref),
    artifact_id TEXT NOT NULL,
    artifact_version INTEGER NOT NULL,
    artifact_digest TEXT NOT NULL,
    destination_id TEXT NOT NULL,
    content BLOB NOT NULL,
    committed_at TEXT NOT NULL
) STRICT;

CREATE TABLE accepted_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    event_type TEXT NOT NULL,
    event_digest TEXT NOT NULL,
    committed_at TEXT NOT NULL
) STRICT;

CREATE TABLE outbox (
    event_id INTEGER PRIMARY KEY REFERENCES accepted_events(event_id),
    destination TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    delivered_at TEXT
) STRICT;

CREATE TABLE operations (
    operation_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    run_id TEXT,
    request_digest TEXT NOT NULL,
    method TEXT NOT NULL,
    state TEXT NOT NULL,
    result_json BLOB,
    committed_at TEXT
) STRICT;

CREATE INDEX idx_calls_run ON call_registration(run_id, response_id, batch_index);
CREATE INDEX idx_resources_task ON resources(task_instance_id);
CREATE INDEX idx_events_run ON accepted_events(run_id, event_id);
