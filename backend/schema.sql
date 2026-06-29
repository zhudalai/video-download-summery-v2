-- ============================================================
-- Video Download Summery — SQLite DDL
-- 兼容 SQLite 3.35+ (支持 generated columns / upsert)
-- 共 11 张表 + 索引 + 触发器
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ----------------------------
-- 1. users
-- ----------------------------
CREATE TABLE IF NOT EXISTS users (
    id                  TEXT PRIMARY KEY,
    email               TEXT NOT NULL,
    full_name           TEXT,
    avatar_url          TEXT,
    language            TEXT DEFAULT 'en',
    currency            TEXT DEFAULT 'USD',
    timezone            TEXT DEFAULT 'UTC',
    role                TEXT DEFAULT 'free',
    stripe_customer_id  TEXT,
    stripe_subscription_id TEXT,
    is_active           INTEGER DEFAULT 1,
    created_at          DATETIME DEFAULT (datetime('now')),
    updated_at          DATETIME DEFAULT (datetime('now')),
    last_login_at       DATETIME
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

-- ----------------------------
-- 2. videos
-- ----------------------------
CREATE TABLE IF NOT EXISTS videos (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url                 TEXT NOT NULL,
    platform            TEXT NOT NULL,
    platform_video_id   TEXT NOT NULL,
    title               TEXT,
    description         TEXT,
    duration            INTEGER,
    thumbnail_url       TEXT,
    metadata            TEXT DEFAULT '{}',       -- JSON 文本
    status              TEXT DEFAULT 'pending',
    error_message       TEXT,
    created_at          DATETIME DEFAULT (datetime('now')),
    updated_at          DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos (user_id);
CREATE INDEX IF NOT EXISTS idx_videos_platform ON videos (platform);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_user_platform_video
    ON videos (user_id, platform, platform_video_id);

-- ----------------------------
-- 3. transcripts
-- ----------------------------
CREATE TABLE IF NOT EXISTS transcripts (
    id                    TEXT PRIMARY KEY,
    video_id              TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    language              TEXT DEFAULT 'auto',
    model                 TEXT NOT NULL,
    content               TEXT,
    segments              TEXT DEFAULT '[]',     -- JSON 文本
    word_count            INTEGER DEFAULT 0,
    confidence            REAL,
    processing_time_ms    INTEGER,
    status                TEXT DEFAULT 'pending',
    error_message         TEXT,
    created_at            DATETIME DEFAULT (datetime('now')),
    updated_at            DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts (video_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_status ON transcripts (status);

-- ----------------------------
-- 4. summaries
-- ----------------------------
CREATE TABLE IF NOT EXISTS summaries (
    id                    TEXT PRIMARY KEY,
    video_id              TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    transcript_id         TEXT REFERENCES transcripts(id) ON DELETE SET NULL,
    model                 TEXT NOT NULL,
    prompt_version        TEXT DEFAULT 'v1',
    content               TEXT,
    content_type          TEXT DEFAULT 'markdown',
    language              TEXT DEFAULT 'zh-CN',
    word_count            INTEGER DEFAULT 0,
    tokens_input          INTEGER,
    tokens_output         INTEGER,
    processing_time_ms    INTEGER,
    status                TEXT DEFAULT 'pending',
    error_message         TEXT,
    extra_data            TEXT DEFAULT '{}',     -- JSON 文本
    created_at            DATETIME DEFAULT (datetime('now')),
    updated_at            DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_summaries_video_id ON summaries (video_id);
CREATE INDEX IF NOT EXISTS idx_summaries_transcript_id ON summaries (transcript_id);
CREATE INDEX IF NOT EXISTS idx_summaries_status ON summaries (status);

-- ----------------------------
-- 5. mindmaps
-- ----------------------------
CREATE TABLE IF NOT EXISTS mindmaps (
    id                    TEXT PRIMARY KEY,
    video_id              TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    summary_id            TEXT REFERENCES summaries(id) ON DELETE SET NULL,
    model                 TEXT NOT NULL,
    content               TEXT NOT NULL,          -- JSON 文本
    content_text          TEXT,
    language              TEXT DEFAULT 'zh-CN',
    node_count            INTEGER DEFAULT 0,
    processing_time_ms    INTEGER,
    status                TEXT DEFAULT 'pending',
    error_message         TEXT,
    created_at            DATETIME DEFAULT (datetime('now')),
    updated_at            DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mindmaps_video_id ON mindmaps (video_id);
CREATE INDEX IF NOT EXISTS idx_mindmaps_summary_id ON mindmaps (summary_id);
CREATE INDEX IF NOT EXISTS idx_mindmaps_status ON mindmaps (status);

-- ----------------------------
-- 6. qa_sessions
-- ----------------------------
CREATE TABLE IF NOT EXISTS qa_sessions (
    id                    TEXT PRIMARY KEY,
    user_id               TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id              TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    summary_id            TEXT REFERENCES summaries(id) ON DELETE SET NULL,
    title                 TEXT,
    model                 TEXT NOT NULL,
    language              TEXT DEFAULT 'zh-CN',
    message_count         INTEGER DEFAULT 0,
    total_tokens_input    INTEGER DEFAULT 0,
    total_tokens_output   INTEGER DEFAULT 0,
    status                TEXT DEFAULT 'active',
    created_at            DATETIME DEFAULT (datetime('now')),
    updated_at            DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_qa_sessions_user_id ON qa_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_qa_sessions_video_id ON qa_sessions (video_id);
CREATE INDEX IF NOT EXISTS idx_qa_sessions_status ON qa_sessions (status);

-- ----------------------------
-- 7. qa_messages
-- ----------------------------
CREATE TABLE IF NOT EXISTS qa_messages (
    id                    TEXT PRIMARY KEY,
    session_id            TEXT NOT NULL REFERENCES qa_sessions(id) ON DELETE CASCADE,
    role                  TEXT NOT NULL,
    content               TEXT NOT NULL,
    tokens_input          INTEGER,
    tokens_output         INTEGER,
    latency_ms            INTEGER,
    metadata              TEXT DEFAULT '{}',     -- JSON 文本
    created_at            DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_qa_messages_session_id ON qa_messages (session_id);

-- ----------------------------
-- 8. subscriptions
-- ----------------------------
CREATE TABLE IF NOT EXISTS subscriptions (
    id                        TEXT PRIMARY KEY,
    user_id                   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan                      TEXT NOT NULL,
    status                    TEXT DEFAULT 'active',
    stripe_subscription_id    TEXT UNIQUE,
    stripe_price_id           TEXT,
    current_period_start      DATETIME,
    current_period_end        DATETIME,
    cancel_at_period_end      INTEGER DEFAULT 0,
    quota_daily               INTEGER DEFAULT 10,
    quota_monthly             INTEGER DEFAULT 100,
    used_today                INTEGER DEFAULT 0,
    used_this_month           INTEGER DEFAULT 0,
    reset_date                DATETIME,
    extra_data                TEXT DEFAULT '{}',   -- JSON 文本
    created_at                DATETIME DEFAULT (datetime('now')),
    updated_at                DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_user_id_unique
    ON subscriptions (user_id);

-- ----------------------------
-- 9. usage_logs
-- ----------------------------
CREATE TABLE IF NOT EXISTS usage_logs (
    id                    TEXT PRIMARY KEY,
    user_id               TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action                TEXT NOT NULL,
    resource_type         TEXT,
    resource_id           TEXT,
    model                 TEXT,
    tokens_input          INTEGER DEFAULT 0,
    tokens_output         INTEGER DEFAULT 0,
    cost                  REAL DEFAULT 0.0,
    latency_ms            INTEGER,
    status                TEXT DEFAULT 'success',
    error_message         TEXT,
    metadata              TEXT DEFAULT '{}',     -- JSON 文本
    created_at            DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id ON usage_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_action ON usage_logs (action);
CREATE INDEX IF NOT EXISTS idx_usage_logs_status ON usage_logs (status);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs (created_at);

-- ----------------------------
-- 10. processed_events (幂等性)
-- ----------------------------
CREATE TABLE IF NOT EXISTS processed_events (
    id            TEXT PRIMARY KEY,
    event_type    TEXT NOT NULL,
    event_key     TEXT NOT NULL UNIQUE,
    source        TEXT,
    payload       TEXT,                          -- JSON 文本
    processed_at  DATETIME DEFAULT (datetime('now')),
    expires_at    DATETIME
);

CREATE INDEX IF NOT EXISTS idx_processed_events_event_type ON processed_events (event_type);
CREATE INDEX IF NOT EXISTS idx_processed_events_expires_at ON processed_events (expires_at);

-- ----------------------------
-- 11. audit_logs
-- ----------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id            TEXT PRIMARY KEY,
    user_id       TEXT REFERENCES users(id) ON DELETE SET NULL,
    action        TEXT NOT NULL,
    resource_type TEXT,
    resource_id   TEXT,
    ip_address    TEXT,
    user_agent    TEXT,
    detail        TEXT DEFAULT '{}',             -- JSON 文本
    severity      TEXT DEFAULT 'info',
    created_at    DATETIME DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_severity ON audit_logs (severity);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at);

-- ============================================================
-- 触发器: 自动更新 updated_at
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
    AFTER UPDATE ON users
    FOR EACH ROW
    BEGIN
        UPDATE users SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_videos_updated_at
    AFTER UPDATE ON videos
    FOR EACH ROW
    BEGIN
        UPDATE videos SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_transcripts_updated_at
    AFTER UPDATE ON transcripts
    FOR EACH ROW
    BEGIN
        UPDATE transcripts SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_summaries_updated_at
    AFTER UPDATE ON summaries
    FOR EACH ROW
    BEGIN
        UPDATE summaries SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_mindmaps_updated_at
    AFTER UPDATE ON mindmaps
    FOR EACH ROW
    BEGIN
        UPDATE mindmaps SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_qa_sessions_updated_at
    AFTER UPDATE ON qa_sessions
    FOR EACH ROW
    BEGIN
        UPDATE qa_sessions SET updated_at = datetime('now') WHERE id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_subscriptions_updated_at
    AFTER UPDATE ON subscriptions
    FOR EACH ROW
    BEGIN
        UPDATE subscriptions SET updated_at = datetime('now') WHERE id = OLD.id;
    END;
