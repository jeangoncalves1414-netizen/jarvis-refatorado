-- Dados exclusivamente do painel mobile; nenhum perfil biométrico é armazenado.
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT 'Nova conversa',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  activity TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS messages_session_created
  ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS preferences (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS habits (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  days_of_week TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS habit_completions (
  habit_id TEXT NOT NULL,
  date_key TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  PRIMARY KEY (habit_id, date_key),
  FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memory_facts (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  session_id TEXT NOT NULL DEFAULT '',
  origin TEXT NOT NULL DEFAULT 'mobile',
  kind TEXT NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY,
  message TEXT NOT NULL,
  target_time TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  completed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

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
