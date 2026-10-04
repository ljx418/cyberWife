-- cyberWife V1 初始 schema（M1 阶段）
-- 按 implementation-contracts.md §2/§3 表
-- 包含全部 13 张表（含 sqlite-vec 虚表 + onboarding_drafts 单线 + profile_history）
-- 幂等：每张表用 IF NOT EXISTS

-- ─────────────────────────────────────────────────────────
-- §2 表 1：consents（FR-02 授权）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS consents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scope TEXT NOT NULL CHECK (scope IN ('portrait','voice','all')),
  policy_version TEXT NOT NULL,
  granted INTEGER NOT NULL CHECK (granted IN (0,1)),
  granted_at TEXT,
  revoked_at TEXT
);

-- ─────────────────────────────────────────────────────────
-- §2 表 2：profiles（FR-06 人设，乐观并发）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY CHECK (id = 1),       -- 单线 profile
  name TEXT NOT NULL,
  user_nickname TEXT NOT NULL,
  persona TEXT NOT NULL DEFAULT '',
  relationship_context TEXT NOT NULL DEFAULT '',
  example_dialogue TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────
-- §2 表 3：profile_history（FR-06 历史留档）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profile_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────
-- §2 表 4：asset_versions + active_assets（FR-04/05）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS asset_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK (kind IN ('portrait','voice')),
  relative_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK (status IN ('uploaded','previewed','active','archived','rejected')),
  filename_or_revision TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_assets (
  kind TEXT PRIMARY KEY CHECK (kind IN ('portrait','voice')),
  asset_id INTEGER NOT NULL REFERENCES asset_versions(id) ON DELETE RESTRICT
);

-- ─────────────────────────────────────────────────────────
-- §2 表 5：sessions + turns（FR-08/13/14）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  recording_policy TEXT NOT NULL CHECK (recording_policy IN ('standard','none')),
  expires_at TEXT                    -- FR-14 = ended_at + 30d UTC
);

CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  user_text TEXT NOT NULL DEFAULT '',
  assistant_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','streaming','completed','cancelled')),
  created_at TEXT NOT NULL,
  UNIQUE(session_id, ordinal)
);

-- ─────────────────────────────────────────────────────────
-- §2 表 6：memories（FR-12 长期记忆；无 expires_at）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  content TEXT NOT NULL,
  confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
  edited INTEGER NOT NULL DEFAULT 0 CHECK (edited IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────
-- §2 表 7：session_transcripts + session_summaries（FR-08/14 转录）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session_transcripts (
  session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
  full_text TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_summaries (
  session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  token_est INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────
-- §2 表 8：memory_fts（FTS5 关键词）
-- ─────────────────────────────────────────────────────────
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
  content,
  content='memories',
  content_rowid='id',
  tokenize='unicode61'
);

-- ─────────────────────────────────────────────────────────
-- §2 表 9：memory_vectors（sqlite-vec 512 维）
-- ─────────────────────────────────────────────────────────
-- 注意：sqlite-vec 在 sqlite3_extensions 加载后才能 CREATE VIRTUAL TABLE
-- M1 阶段在 VectorIndex.ensure_schema() 内部按需创建；若 sqlite-vec 不可用，
-- VectorIndex 回退内存版（仅用于 M1 单元测试）。
-- 这里给出占位 DDL，运行时由 VectorIndex 建表。
CREATE TABLE IF NOT EXISTS memory_vectors_meta (
  memory_id INTEGER PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL DEFAULT 'bge-small-zh-v1.5',
  revision TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────
-- §2 表 10：audit_events（§3 18 项 action）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL CHECK (entity_type IN ('consent','profile','asset','memory','session','retention','health')),
  entity_id_hash TEXT NOT NULL,                -- SHA256(entity_id || session_salt)[:16]
  result TEXT NOT NULL CHECK (result IN ('success','failure','rollback')),
  deleted_row_count INTEGER,
  fts_count_before INTEGER,
  fts_count_after INTEGER,
  vector_count_before INTEGER,
  vector_count_after INTEGER,
  error_code TEXT,
  trace_id TEXT,                                -- ULID 26 字符
  created_at TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────
-- §20 表 11：onboarding_drafts（FR-01 五步草稿，单线）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_drafts (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  consent_granted INTEGER NOT NULL DEFAULT 0 CHECK (consent_granted IN (0,1)),
  step_completed INTEGER NOT NULL DEFAULT 0 CHECK (step_completed >= 0 AND step_completed <= 4),
  asset_consent_at TEXT,
  profile_draft_json TEXT NOT NULL DEFAULT '{}',
  settings_json TEXT NOT NULL DEFAULT '{}',
  device_snapshot_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────
-- schema_migrations（防重复执行）
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));

-- ─────────────────────────────────────────────────────────
-- 索引（按查询热点）
-- ─────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_asset_versions_kind ON asset_versions(kind, created_at DESC);
