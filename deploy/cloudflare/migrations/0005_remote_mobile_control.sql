CREATE TABLE IF NOT EXISTS remote_devices (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  platform TEXT NOT NULL,
  paired_code TEXT,
  paired_code_expires_at INTEGER,
  last_seen_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS remote_controllers (
  id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS remote_commands (
  id TEXT PRIMARY KEY,
  target_id TEXT NOT NULL,
  command TEXT NOT NULL,
  payload TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  result TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS remote_commands_target ON remote_commands(target_id, status, created_at);
