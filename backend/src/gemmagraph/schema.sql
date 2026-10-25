PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_versions VALUES(1);
CREATE TABLE IF NOT EXISTS resources(
 kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
 PRIMARY KEY(kind,id)
);
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, resource_id TEXT NOT NULL,
 payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
 lease_owner TEXT, lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_active ON jobs(kind,resource_id)
 WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS run_events(
 run_id TEXT NOT NULL, seq INTEGER NOT NULL, source_key TEXT NOT NULL,
 data TEXT NOT NULL, PRIMARY KEY(run_id,seq), UNIQUE(run_id,source_key)
);
CREATE TABLE IF NOT EXISTS idempotency_keys(
 scope TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
 resource_id TEXT NOT NULL, PRIMARY KEY(scope,key)
);
