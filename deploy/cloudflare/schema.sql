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
