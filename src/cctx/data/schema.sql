-- Living Context System Schema
-- Version: 1.0.0
-- Created: 2025-12-15

-- ADRs (Architecture Decision Records)
CREATE TABLE IF NOT EXISTS adrs (
    id TEXT PRIMARY KEY,                    -- e.g., "ADR-001"
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted', 'deprecated', 'superseded')),
    created_at TEXT NOT NULL,               -- ISO 8601 timestamp
    updated_at TEXT NOT NULL,               -- ISO 8601 timestamp
    context TEXT,                           -- context/background for the decision
    decision TEXT,                          -- the decision made
    consequences TEXT,                      -- consequences of the decision
    file_path TEXT NOT NULL UNIQUE          -- relative path from project root
);

-- ADR-to-System relationships
CREATE TABLE IF NOT EXISTS adr_systems (
    adr_id TEXT NOT NULL,
    system_path TEXT NOT NULL,              -- e.g., "src/systems/audio"
    PRIMARY KEY (adr_id, system_path),
    FOREIGN KEY (adr_id) REFERENCES adrs(id) ON DELETE CASCADE
);

-- ADR tags for categorization
CREATE TABLE IF NOT EXISTS adr_tags (
    adr_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (adr_id, tag),
    FOREIGN KEY (adr_id) REFERENCES adrs(id) ON DELETE CASCADE
);

-- Systems registry
CREATE TABLE IF NOT EXISTS systems (
    path TEXT PRIMARY KEY,                  -- e.g., "src/systems/audio"
    name TEXT NOT NULL,                     -- e.g., "Audio System"
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- System dependency graph
CREATE TABLE IF NOT EXISTS system_dependencies (
    system_path TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    PRIMARY KEY (system_path, depends_on),
    FOREIGN KEY (system_path) REFERENCES systems(path) ON DELETE CASCADE,
    FOREIGN KEY (depends_on) REFERENCES systems(path) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_adrs_status ON adrs(status);
CREATE INDEX IF NOT EXISTS idx_adr_systems_system ON adr_systems(system_path);
CREATE INDEX IF NOT EXISTS idx_adr_tags_tag ON adr_tags(tag);
CREATE INDEX IF NOT EXISTS idx_system_deps_depends ON system_dependencies(depends_on);
