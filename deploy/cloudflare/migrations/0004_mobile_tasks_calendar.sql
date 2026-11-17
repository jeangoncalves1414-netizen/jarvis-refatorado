CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  completed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS tasks_updated ON tasks(completed, updated_at DESC);

CREATE TABLE IF NOT EXISTS calendar_events (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  start TEXT NOT NULL,
  reminder_minutes INTEGER NOT NULL DEFAULT 0,
  reminder_policy TEXT NOT NULL DEFAULT 'once',
  reminder_at TEXT,
  reminder_status TEXT NOT NULL DEFAULT 'scheduled',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS calendar_events_start ON calendar_events(start);
