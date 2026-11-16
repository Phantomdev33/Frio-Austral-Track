CREATE TABLE IF NOT EXISTS readings (
    event_id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    payload TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'Pendiente' CHECK (state IN ('Pendiente', 'Sincronizado')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    synced_at TEXT
);
CREATE INDEX IF NOT EXISTS readings_pending ON readings(owner, state, created_at);
