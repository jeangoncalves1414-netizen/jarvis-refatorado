CREATE TABLE IF NOT EXISTS memory_facts (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  session_id TEXT NOT NULL DEFAULT '',
  origin TEXT NOT NULL DEFAULT 'mobile',
  kind TEXT NOT NULL DEFAULT 'manual'
);

CREATE INDEX IF NOT EXISTS memory_facts_updated ON memory_facts(updated_at DESC);

CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY,
  message TEXT NOT NULL,
  target_time TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE INDEX IF NOT EXISTS reminders_pending ON reminders(completed_at, target_time);
