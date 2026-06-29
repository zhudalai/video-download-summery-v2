# 数据库设计规范

> 项目：Video Download Summery（视频下载与 AI 总结平台）
> 版本：v1.0
> 日期：2026-06-25
> 维护者：高级开发者

---

## 目录

1. [概述与背景](#1-概述与背景)
2. [SQLite → PostgreSQL 迁移路径](#2-sqlite--postgresql-迁移路径)
3. [表结构设计（完整 DDL）](#3-表结构设计完整-ddl)
4. [索引策略](#4-索引策略)
5. [数据保留与清理策略](#5-数据保留与清理策略)
6. [备份策略](#6-备份策略)
7. [性能优化](#7-性能优化)
8. [数据一致性](#8-数据一致性)
9. [验证清单（Checklist）](#9-验证清单checklist)

---

## 1. 概述与背景

### 1.1 产品形态

- **前端**：Web SPA（Vue 3 + Vite 7）
- **数据库**：SQLite（MVP）→ PostgreSQL（生产，用户过 1k 迁移）
- **AI 模型**：OpenRouter 统一网关，按语言路由（中文 → DeepSeek，英文 → Claude/GPT）
- **版权策略**：下载 + 总结完整功能，**不持久化视频文件**
- **时间线**：1-2 个月 MVP
- **V1 语言**：英语 + 中文（简体）+ 日语
- **认证**：Supabase Auth（云端版），用户数据存在业务数据库
- **支付**：Stripe Checkout + Webhook
- **错误码体系**：统一错误响应格式

### 1.2 设计原则

1. **MVP 友好**：SQLite 零配置起步，schema 兼容 PostgreSQL
2. **迁移无痛**：使用 Alembic 管理 schema 版本，pgloader 做全量迁移
3. **合规优先**：Stripe 收据保留 7 年，审计日志 1 年
4. **性能兜底**：慢查询阈值 500ms，关键路径加索引
5. **安全默认**：用户删除级联清理，API Key 加密存储

### 1.3 技术栈

| 组件 | MVP | 生产 |
|------|-----|------|
| 数据库 | SQLite 3（WAL 模式） | PostgreSQL 15+ |
| ORM | SQLAlchemy 2.0（async） | SQLAlchemy 2.0（asyncpg） |
| 迁移 | Alembic | Alembic |
| 连接池 | 内置 | asyncpg + SQLAlchemy pool |
| 缓存 | 无 | Redis（可选） |
| 备份 | 手动 pg_dump 到 S3/R2 | Railway/Fly.io 自动备份 |

---

## 2. SQLite → PostgreSQL 迁移路径

### 2.1 MVP 阶段 SQLite 配置

```python
# config/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/app.db"  # 默认 SQLite
)

# SQLite 优化配置
SQLITE_PRAGMAS = {
    "journal_mode": "WAL",        # 写前日志，提升并发读
    "synchronous": "NORMAL",      # WAL 模式下 NORMAL 足够安全
    "cache_size": -64000,         # 64MB 缓存
    "foreign_keys": "ON",         # 强制外键约束
    "busy_timeout": 5000,         # 5 秒超时
    "temp_store": "MEMORY",       # 临时表放内存
    "mmap_size": 268435456,       # 256MB 内存映射
}

def get_engine():
    if DATABASE_URL.startswith("sqlite"):
        engine = create_async_engine(
            DATABASE_URL,
            connect_args={"pragmas": SQLITE_PRAGMAS},
            echo=False,
        )
    else:
        engine = create_async_engine(
            DATABASE_URL,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    return engine
```

```sql
-- SQLite 初始化脚本（启动时执行）
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

### 2.2 迁移触发条件

满足**任一**条件即触发迁移：

| 条件 | 阈值 | 监控方式 |
|------|------|----------|
| 注册用户数 | > 1,000 | `SELECT COUNT(*) FROM users` |
| 日活跃用户 | > 200 持续 3 天 | 审计日志统计 |
| 并发连接数 | > 50 | 应用层连接池监控 |
| 单表行数 | > 500,000 | `SELECT COUNT(*) FROM <表>` |
| SQLite 文件大小 | > 2 GB | `ls -lh app.db` |
| 查询延迟 P95 | > 300ms 持续 1 小时 | APM 监控 |

**迁移决策流程**：

```
触发条件满足
    ↓
评估迁移窗口（建议 UTC 02:00-06:00 低峰期）
    ↓
通知用户（提前 7 天公告，预计 30 分钟只读维护）
    ↓
执行迁移（见 2.3）
    ↓
验证数据完整性（见 2.5）
    ↓
切换连接字符串
    ↓
保留 SQLite 备份 30 天
```

### 2.3 迁移步骤

#### 方案 A：pgloader（推荐，全量迁移）

```bash
# 安装 pgloader
brew install pgloader  # macOS
# 或
apt-get install pgloader  # Ubuntu

# 创建迁移配置文件 migrate.load
```

```lisp
;; migrate.load
LOAD DATABASE
    FROM sqlite:///path/to/app.db
    INTO postgresql://user:pass@host:5432/videosummary

WITH include drop, create tables, create indexes, reset sequences,
     workers = 8, concurrency = 4,
     multiple readers per thread, rows per range = 50000

CAST
    type datetime to timestamptz drop default drop not null using zero-dates-to-null,
    type date to date drop default drop not null using zero-dates-to-null,
    type integer to bigint,
    type real to double precision

SET work_mem to '256MB',
    maintenance_work_mem to '1GB',
    search_path to 'public,pg_catalog';

-- 迁移后验证
ALTER SCHEMA 'public' OWNER TO videosummary;
```

```bash
# 执行迁移
pgloader migrate.load 2>&1 | tee migration.log

# 验证行数
psql -c "
SELECT 'users' as tbl, COUNT(*) FROM users
UNION ALL
SELECT 'videos', COUNT(*) FROM videos
UNION ALL
SELECT 'summaries', COUNT(*) FROM summaries;
"
```

#### 方案 B：Alembic（增量迁移，适合零停机）

```python
# alembic/env.py
# 配置双数据源
def run_migrations_online():
    """支持 SQLite → PostgreSQL 在线迁移."""
    connectable = current_app.config["SQLALCHEMY_DATABASE_URI"]
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,       # 检测类型变化
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
```

```bash
# 1. 初始化 Alembic
alembic init migrations

# 2. 生成初始 migration
alembic revision --autogenerate -m "initial_schema"

# 3. 在 PostgreSQL 上创建 schema
alembic upgrade head

# 4. 使用 SQLAlchemy 双写脚本同步历史数据
python scripts/sync_sqlite_to_pg.py --batch-size 1000
```

```python
# scripts/sync_sqlite_to_pg.py
"""SQLite → PostgreSQL 历史数据同步脚本."""
import asyncio
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

SQLITE_PATH = "./data/app.db"
PG_URL = "postgresql+asyncpg://user:pass@host:5432/videosummary"

TABLES = [
    "users", "videos", "transcripts", "summaries",
    "mindmaps", "qa_sessions", "subscriptions",
    "audit_logs", "processed_events",
]

async def sync_table(table: str, batch_size: int = 1000):
    """逐表分批同步."""
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_engine = create_async_engine(PG_URL, pool_size=5)
    AsyncSessionLocal = sessionmaker(pg_engine, class_=AsyncSession)

    offset = 0
    while True:
        rows = sqlite_conn.execute(
            f"SELECT * FROM {table} LIMIT ? OFFSET ?",
            (batch_size, offset)
        ).fetchall()

        if not rows:
            break

        async with AsyncSessionLocal() as session:
            for row in rows:
                await session.execute(
                    f"INSERT INTO {table} VALUES ({','.join(['?'] * len(row))}) "
                    f"ON CONFLICT DO NOTHING",
                    list(row),
                )
            await session.commit()

        offset += batch_size
        print(f"  {table}: synced {offset} rows")

    sqlite_conn.close()
    await pg_engine.dispose()

async def main():
    for table in TABLES:
        print(f"Syncing {table}...")
        await sync_table(table)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2.4 迁移后验证

```sql
-- 1. 行数对比
SELECT 'users' as tbl, COUNT(*) as pg_count FROM users;
-- 对比 SQLite: SELECT COUNT(*) FROM users;

-- 2. 主键连续性检查
SELECT MAX(id) FROM users;
SELECT COUNT(*) FROM users;
-- 差值应 < 10%（有删除属正常）

-- 3. 外键完整性
SELECT COUNT(*) FROM videos v
LEFT JOIN users u ON v.user_id = u.id
WHERE u.id IS NULL AND v.user_id IS NOT NULL;
-- 应返回 0

-- 4. JSON 字段合法性
SELECT COUNT(*) FROM summaries
WHERE jsonb_typeof(content) IS NULL;
-- 应返回 0

-- 5. 时间戳范围合理性
SELECT MIN(created_at), MAX(created_at) FROM videos;
-- 不应有未来时间或 1970 年数据
```

### 2.5 回滚方案

```bash
# 回滚触发条件：
# - 数据完整性检查失败
# - 应用错误率 > 5% 持续 10 分钟
# - 查询延迟 P95 > 2s 持续 30 分钟

# 步骤 1：切换回 SQLite（修改环境变量）
export DATABASE_URL="sqlite+aiosqlite:///./data/app.db"

# 步骤 2：重启应用
docker restart app  # 或 systemd restart

# 步骤 3：验证
curl -f http://localhost:8000/health

# 步骤 4：保留 PostgreSQL 快照供事后分析
pg_dump -Fc videosummary > /backups/postgres_failed_migration.dump

# 注意：SQLite → PostgreSQL 单向写入期间的数据会丢失
# 因此迁移窗口内应设为"只读维护"模式
```

**回滚时间目标**：
- 切换连接字符串：< 1 分钟
- 应用重启：< 2 分钟
- 总 RTO（恢复时间目标）：< 5 分钟
- RPO（恢复点目标）：迁移窗口内的写入数据（建议维护模式避免）

---

## 3. 表结构设计（完整 DDL）

### 3.1 类型定义与约定

```sql
-- 自定义类型（PostgreSQL）
CREATE TYPE user_role AS ENUM ('free', 'pro', 'admin');
CREATE TYPE video_status AS ENUM (
    'pending', 'downloading', 'processing', 'completed', 'failed'
);
CREATE TYPE subscription_status AS ENUM (
    'incomplete', 'active', 'past_due', 'canceled', 'unpaid'
);
CREATE TYPE billing_plan AS ENUM ('free', 'pro_monthly', 'pro_yearly');

-- 通用约定：
-- 1. 主键：id BIGINT GENERATED ALWAYS AS IDENTITY
-- 2. 时间戳：TIMESTAMPTZ（带时区），默认 NOW()
-- 3. JSON 字段：JSONB（PostgreSQL）/ TEXT（SQLite 用 JSON 函数）
-- 4. 软删除：deleted_at TIMESTAMPTZ NULL
-- 5. 状态：ENUM 或 VARCHAR + CHECK
```

### 3.2 users（用户表）

```sql
CREATE TABLE users (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Supabase Auth 关联
    external_id         UUID NOT NULL UNIQUE,  -- auth.users.id

    -- 基本信息
    email               VARCHAR(320) NOT NULL,
    display_name        VARCHAR(100),
    avatar_url          VARCHAR(500),
    role                user_role NOT NULL DEFAULT 'free',

    -- 偏好设置（JSON 灵活扩展）
    preferences         JSONB NOT NULL DEFAULT '{
        "language": "zh-CN",
        "theme": "system",
        "summary_detail": "standard",
        "auto_generate_mindmap": true,
        "notifications": {"email": true, "push": false}
    }'::jsonb,

    -- 使用量追踪
    total_videos        INTEGER NOT NULL DEFAULT 0,
    total_summary_tokens BIGINT NOT NULL DEFAULT 0,
    monthly_quota_used  INTEGER NOT NULL DEFAULT 0,
    monthly_quota_limit INTEGER NOT NULL DEFAULT 10,  -- free tier

    -- 时间戳
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,  -- 软删除

    -- 约束
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_quota_positive CHECK (monthly_quota_used >= 0)
);

-- 索引
CREATE INDEX idx_users_external_id ON users(external_id);
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_created_at ON users(created_at DESC);
CREATE INDEX idx_users_preferences ON users USING GIN (preferences);

-- 注释
COMMENT ON TABLE users IS '用户表，与 Supabase auth.users 通过 external_id 关联';
COMMENT ON COLUMN users.external_id IS 'Supabase auth.users.id，UUID 格式';
COMMENT ON COLUMN users.preferences IS '用户偏好：语言、主题、总结风格等';
```

### 3.3 videos（视频表）

```sql
CREATE TABLE videos (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT NOT NULL,

    -- 视频来源
    url                 VARCHAR(2000) NOT NULL,
    platform            VARCHAR(50) NOT NULL,  -- youtube, bilibili, etc.
    platform_video_id  VARCHAR(200),           -- 平台原始视频 ID
    title               VARCHAR(500) NOT NULL,
    description         TEXT,
    duration            INTEGER,               -- 秒
    thumbnail_url       VARCHAR(500),

    -- 处理状态
    status              video_status NOT NULL DEFAULT 'pending',
    error_message       TEXT,
    retry_count         SMALLINT NOT NULL DEFAULT 0,

    -- 元数据（灵活扩展）
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- metadata 示例：
    -- {
    --   "resolution": "1080p",
    --   "fps": 30,
    --   "file_size": 104857600,
    --   "upload_date": "2025-01-15",
    --   "channel": "TechChannel",
    --   "tags": ["AI", "tutorial"],
    --   "language_detected": "zh"
    -- }

    -- 时间戳
    processed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,

    -- 外键
    CONSTRAINT fk_videos_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- 约束
    CONSTRAINT chk_duration_positive CHECK (duration IS NULL OR duration > 0),
    CONSTRAINT chk_retry_max CHECK (retry_count <= 5),
    CONSTRAINT uq_user_platform_video UNIQUE (user_id, platform, platform_video_id)
);

-- 索引
CREATE INDEX idx_videos_user_created ON videos(user_id, created_at DESC);
CREATE INDEX idx_videos_status ON videos(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_videos_platform ON videos(platform, platform_video_id);
CREATE INDEX idx_videos_metadata ON videos USING GIN (metadata);
CREATE INDEX idx_videos_created_at ON videos(created_at DESC);

-- 部分索引：待处理的视频快速查询
CREATE INDEX idx_videos_pending ON videos(status, created_at)
    WHERE status IN ('pending', 'downloading', 'processing');

COMMENT ON TABLE videos IS '视频表，不存储视频文件本身，仅存元信息';
COMMENT ON COLUMN videos.url IS '视频原始 URL，不持久化文件';
COMMENT ON COLUMN videos.metadata IS '平台相关元数据，JSON 灵活扩展';
```

### 3.4 transcripts（转录文本表）

```sql
CREATE TABLE transcripts (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    video_id            BIGINT NOT NULL,

    -- 转录信息
    language            VARCHAR(10) NOT NULL,  -- ISO 639-1: en, zh, ja
    content             TEXT NOT NULL,          -- 完整转录文本
    segments            JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- segments 示例：
    -- [
    --   {"start": 0.5, "end": 3.2, "text": "大家好，今天..."},
    --   {"start": 3.2, "end": 7.8, "text": "我们来讲..."}
    -- ]
    duration            INTEGER,               -- 音频时长（秒）
    word_count          INTEGER,

    -- 转录引擎信息
    provider            VARCHAR(50) DEFAULT 'openai-whisper',
    model_version       VARCHAR(50),

    -- 时间戳
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键
    CONSTRAINT fk_transcripts_video
        FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,

    -- 约束
    CONSTRAINT uq_video_language UNIQUE (video_id, language),
    CONSTRAINT chk_language_code CHECK (language ~* '^[a-z]{2}(-[A-Z]{2})?$')
);

-- 索引
CREATE INDEX idx_transcripts_video_lang ON transcripts(video_id, language);
CREATE INDEX idx_transcripts_language ON transcripts(language);
CREATE INDEX idx_transcripts_segments ON transcripts USING GIN (segments);

-- 全文搜索索引（PostgreSQL 高级特性）
CREATE INDEX idx_transcripts_content_search ON transcripts
    USING GIN (to_tsvector('simple', content));

COMMENT ON TABLE transcripts IS '视频转录文本，按语言分行存储';
COMMENT ON COLUMN transcripts.segments IS '分段 JSON，含起止时间戳';
```

### 3.5 summaries（AI 总结表）

```sql
CREATE TABLE summaries (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    video_id            BIGINT NOT NULL,

    -- 总结内容
    language            VARCHAR(10) NOT NULL,
    content             TEXT NOT NULL,
    version             SMALLINT NOT NULL DEFAULT 1,
    prompt_version      VARCHAR(20) NOT NULL DEFAULT 'v1',

    -- AI 模型信息
    model               VARCHAR(100),  -- deepseek-chat, claude-sonnet-4-5, etc.
    provider            VARCHAR(50) DEFAULT 'openrouter',
    token_count         INTEGER,
    completion_tokens   INTEGER,
    prompt_tokens       INTEGER,

    -- 质量评分（用户反馈）
    rating              SMALLINT,      -- 1-5
    feedback            TEXT,

    -- 时间戳
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键
    CONSTRAINT fk_summaries_video
        FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,

    -- 约束
    CONSTRAINT uq_summary_version UNIQUE (video_id, language, version),
    CONSTRAINT chk_rating_range CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    CONSTRAINT chk_token_positive CHECK (token_count IS NULL OR token_count > 0)
);

-- 索引
CREATE INDEX idx_summaries_video_lang ON summaries(video_id, language);
CREATE INDEX idx_summaries_video_version ON summaries(video_id, version DESC);
CREATE INDEX idx_summaries_model ON summaries(model);
CREATE INDEX idx_summaries_generated ON summaries(generated_at DESC);

-- 部分索引：最新版本的总结
CREATE INDEX idx_summaries_latest ON summaries(video_id, language, version DESC);

COMMENT ON TABLE summaries IS 'AI 总结表，支持多版本和多语言';
COMMENT ON COLUMN summaries.version IS '同一视频同一语言的总结版本号';
COMMENT ON COLUMN summaries.prompt_version IS '提示词版本，用于 A/B 测试';
```

### 3.6 mindmaps（思维导图表）

```sql
CREATE TABLE mindmaps (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    summary_id          BIGINT NOT NULL,

    -- 图形数据
    svg_data            TEXT,           -- SVG 源码
    png_data            BYTEA,          -- PNG 二进制（预览用）
    width               INTEGER,
    height              INTEGER,

    -- 生成参数
    style               VARCHAR(50) DEFAULT 'default',
    layout_algorithm    VARCHAR(50) DEFAULT 'force-directed',

    -- 时间戳
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键
    CONSTRAINT fk_mindmaps_summary
        FOREIGN KEY (summary_id) REFERENCES summaries(id) ON DELETE CASCADE,

    -- 约束
    CONSTRAINT chk_positive_dimensions CHECK (
        (width IS NULL OR width > 0) AND (height IS NULL OR height > 0)
    )
);

-- 索引
CREATE INDEX idx_mindmaps_summary ON mindmaps(summary_id);
CREATE INDEX idx_mindmaps_generated ON mindmaps(generated_at DESC);

COMMENT ON TABLE mindmaps IS '思维导图表，一个总结可有多张不同风格的导图';
```

### 3.7 qa_sessions（问答会话表）

```sql
CREATE TABLE qa_sessions (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT NOT NULL,
    video_id            BIGINT NOT NULL,

    -- 会话内容
    messages            JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- messages 示例：
    -- [
    --   {"role": "user", "content": "这段视频讲了什么？", "timestamp": "2026-06-25T10:00:00Z"},
    --   {"role": "assistant", "content": "这段视频主要讲解了...", "timestamp": "2026-06-25T10:00:05Z",
    --    "usage": {"input_tokens": 150, "output_tokens": 300}}
    -- ]

    -- 会话元数据
    title               VARCHAR(200),          -- 自动生成或用户编辑
    total_tokens        INTEGER DEFAULT 0,
    message_count       INTEGER DEFAULT 0,
    is_pinned           BOOLEAN NOT NULL DEFAULT FALSE,

    -- 时间戳
    last_message_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键
    CONSTRAINT fk_qa_sessions_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_qa_sessions_video
        FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_qa_sessions_user ON qa_sessions(user_id, last_message_at DESC);
CREATE INDEX idx_qa_sessions_video ON qa_sessions(video_id);
CREATE INDEX idx_qa_sessions_messages ON qa_sessions USING GIN (messages);
CREATE INDEX idx_qa_sessions_pinned ON qa_sessions(user_id, is_pinned)
    WHERE is_pinned = TRUE;

COMMENT ON TABLE qa_sessions IS '视频问答会话，messages 存储完整对话历史';
```

### 3.8 subscriptions（订阅表）

```sql
CREATE TABLE subscriptions (
    id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id                     BIGINT NOT NULL,

    -- Stripe 关联
    stripe_customer_id          VARCHAR(255) UNIQUE,
    stripe_subscription_id      VARCHAR(255) UNIQUE,
    stripe_price_id             VARCHAR(255),

    -- 订阅信息
    plan                        billing_plan NOT NULL DEFAULT 'free',
    status                      subscription_status NOT NULL DEFAULT 'incomplete',
    quantity                    SMALLINT NOT NULL DEFAULT 1,

    -- 计费周期
    current_period_start        TIMESTAMPTZ,
    current_period_end          TIMESTAMPTZ,
    trial_start                 TIMESTAMPTZ,
    trial_end                   TIMESTAMPTZ,
    canceled_at                 TIMESTAMPTZ,
    cancel_at_period_end        BOOLEAN NOT NULL DEFAULT FALSE,
    ended_at                    TIMESTAMPTZ,

    -- 支付信息
    default_payment_method      VARCHAR(255),
    latest_invoice_id           VARCHAR(255),

    -- 时间戳
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键
    CONSTRAINT fk_subscriptions_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- 约束
    CONSTRAINT chk_period_order CHECK (
        current_period_start IS NULL OR current_period_end IS NULL
        OR current_period_start < current_period_end
    ),
    CONSTRAINT uq_user_subscription UNIQUE (user_id, stripe_subscription_id)
);

-- 索引
CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_stripe_customer ON subscriptions(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX idx_subscriptions_stripe_sub ON subscriptions(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_period_end ON subscriptions(current_period_end)
    WHERE status = 'active';

-- 部分索引：即将过期的订阅（用于提醒）
CREATE INDEX idx_subscriptions_expiring ON subscriptions(current_period_end)
    WHERE status = 'active' AND current_period_end IS NOT NULL;

COMMENT ON TABLE subscriptions IS '订阅表，与 Stripe 通过 customer_id 和 subscription_id 关联';
```

### 3.9 audit_logs（审计日志表）

```sql
CREATE TABLE audit_logs (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT,  -- NULL 表示系统操作或匿名

    -- 操作信息
    action              VARCHAR(100) NOT NULL,  -- user.login, video.create, etc.
    resource_type       VARCHAR(50),             -- video, summary, subscription
    resource_id         BIGINT,

    -- 请求上下文
    ip_address          INET,
    user_agent          VARCHAR(500),
    request_id          VARCHAR(100),  -- 关联请求 ID

    -- 详情
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- 示例：
    -- {
    --   "method": "POST",
    --   "path": "/api/videos",
    --   "status_code": 201,
    --   "duration_ms": 245,
    --   "changes": {"before": {...}, "after": {...}}
    -- }

    -- 时间戳
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键（用户删除后日志保留，设 NULL）
    CONSTRAINT fk_audit_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 索引
CREATE INDEX idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action, created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_metadata ON audit_logs USING GIN (metadata);

-- 分区策略（生产环境建议按月分区）
-- CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs
--     FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

COMMENT ON TABLE audit_logs IS '审计日志表，用户删除后设 NULL 保留日志';
COMMENT ON COLUMN audit_logs.user_id IS 'NULL 表示系统操作或已删除用户';
```

### 3.10 processed_events（已处理事件表）

```sql
CREATE TABLE processed_events (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Stripe 事件
    event_id            VARCHAR(255) NOT NULL UNIQUE,  -- evt_xxx
    event_type          VARCHAR(100) NOT NULL,         // checkout.session.completed
    event_data          JSONB NOT NULL,                -- 完整事件数据

    -- 处理状态
    processed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_by        VARCHAR(100),                  -- worker 标识
    retry_count         SMALLINT NOT NULL DEFAULT 0,
    error_message       TEXT,

    -- 时间戳
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_processed_events_type ON processed_events(event_type);
CREATE INDEX idx_processed_events_created ON processed_events(created_at DESC);

COMMENT ON TABLE processed_events IS '已处理的 Stripe Webhook 事件，用于幂等性保证';
```

### 3.11 api_keys（API Key 表，V2 预留）

```sql
CREATE TABLE api_keys (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT NOT NULL,

    -- Key 信息
    key_prefix          VARCHAR(8) NOT NULL,           -- 前 8 位，用于展示
    key_hash            VARCHAR(255) NOT NULL UNIQUE,  -- SHA-256 哈希
    name                VARCHAR(100) NOT NULL,

    -- 权限
    scopes              VARCHAR(50)[] NOT NULL DEFAULT ARRAY['read'],
    rate_limit          INTEGER NOT NULL DEFAULT 60,   -- 每分钟

    -- 有效期
    last_used_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    revoked_at          TIMESTAMPTZ,

    -- 时间戳
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键
    CONSTRAINT fk_api_keys_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- 约束
    CONSTRAINT chk_scopes_valid CHECK (
        scopes <@ ARRAY['read', 'write', 'admin']
    ),
    CONSTRAINT chk_rate_limit_positive CHECK (rate_limit > 0)
);

-- 索引
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

COMMENT ON TABLE api_keys IS 'API Key 表，V2 功能预留';
```

### 3.12 ER 关系图

```
users (1) ──── (N) videos
  │                    │
  │                    └── (N) transcripts
  │                    │        │
  │                    │        └── (N) summaries
  │                    │                 │
  │                    │                 └── (N) mindmaps
  │                    │
  │                    └── (N) qa_sessions
  │
  ├── (1) subscriptions
  ├── (N) audit_logs
  └── (N) api_keys

processed_events ──── 独立表（无外键）
```

---

## 4. 索引策略

### 4.1 主键、外键、唯一索引

已在 DDL 中定义，总结如下：

| 类型 | 表 | 字段 | 说明 |
|------|-----|------|------|
| 主键 | 所有表 | `id` | BIGINT GENERATED ALWAYS AS IDENTITY |
| 唯一 | users | `external_id` | Supabase auth 关联 |
| 唯一 | users | `email` | 部分索引，排除已删除 |
| 唯一 | videos | `(user_id, platform, platform_video_id)` | 防止重复下载 |
| 唯一 | transcripts | `(video_id, language)` | 每视频每语言一条 |
| 唯一 | summaries | `(video_id, language, version)` | 版本唯一 |
| 唯一 | subscriptions | `(user_id, stripe_subscription_id)` | 用户订阅唯一 |
| 唯一 | processed_events | `event_id` | 幂等保证 |
| 唯一 | api_keys | `key_hash` | Key 哈希唯一 |
| 外键 | videos.user_id | → users.id | ON DELETE CASCADE |
| 外键 | transcripts.video_id | → videos.id | ON DELETE CASCADE |
| 外键 | summaries.video_id | → videos.id | ON DELETE CASCADE |
| 外键 | mindmaps.summary_id | → summaries.id | ON DELETE CASCADE |
| 外键 | qa_sessions.user_id | → users.id | ON DELETE CASCADE |
| 外键 | qa_sessions.video_id | → videos.id | ON DELETE CASCADE |
| 外键 | subscriptions.user_id | → users.id | ON DELETE CASCADE |
| 外键 | audit_logs.user_id | → users.id | ON DELETE SET NULL |
| 外键 | api_keys.user_id | → users.id | ON DELETE CASCADE |

### 4.2 查询频繁的索引

```sql
-- 用户视频列表（最常见查询）
CREATE INDEX idx_videos_user_created ON videos(user_id, created_at DESC);

-- 视频总结查询
CREATE INDEX idx_summaries_video_lang ON summaries(video_id, language);

-- 用户问答历史
CREATE INDEX idx_qa_sessions_user ON qa_sessions(user_id, last_message_at DESC);

-- 订阅状态查询
CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);

-- 审计日志查询
CREATE INDEX idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC);
```

### 4.3 GIN 索引（JSON 字段）

```sql
-- users.preferences
CREATE INDEX idx_users_preferences ON users USING GIN (preferences);

-- videos.metadata
CREATE INDEX idx_videos_metadata ON videos USING GIN (metadata);

-- transcripts.segments
CREATE INDEX idx_transcripts_segments ON transcripts USING GIN (segments);

-- qa_sessions.messages
CREATE INDEX idx_qa_sessions_messages ON qa_sessions USING GIN (messages);

-- audit_logs.metadata
CREATE INDEX idx_audit_logs_metadata ON audit_logs USING GIN (metadata);

-- processed_events.event_data
CREATE INDEX idx_processed_events_data ON processed_events USING GIN (event_data);
```

### 4.4 部分索引（Partial Index）

```sql
-- 活跃用户（排除已删除）
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;

-- 待处理视频
CREATE INDEX idx_videos_pending ON videos(status, created_at)
    WHERE status IN ('pending', 'downloading', 'processing');

-- 活跃订阅
CREATE INDEX idx_subscriptions_active ON subscriptions(user_id)
    WHERE status = 'active';

-- 即将过期订阅（7 天内）
CREATE INDEX idx_subscriptions_expiring ON subscriptions(current_period_end)
    WHERE status = 'active'
      AND current_period_end IS NOT NULL
      AND current_period_end < NOW() + INTERVAL '7 days';

-- 未撤销的 API Key
CREATE INDEX idx_api_keys_active ON api_keys(user_id)
    WHERE revoked_at IS NULL;

-- 置顶会话
CREATE INDEX idx_qa_sessions_pinned ON qa_sessions(user_id, last_message_at DESC)
    WHERE is_pinned = TRUE;
```

### 4.5 全文搜索索引

```sql
-- 视频标题搜索
CREATE INDEX idx_videos_title_search ON videos
    USING GIN (to_tsvector('simple', title));

-- 转录内容搜索
CREATE INDEX idx_transcripts_content_search ON transcripts
    USING GIN (to_tsvector('simple', content));

-- 总结内容搜索
CREATE INDEX idx_summaries_content_search ON summaries
    USING GIN (to_tsvector('simple', content));
```

---

## 5. 数据保留与清理策略

### 5.1 保留策略总览

| 数据类型 | 保留期限 | 触发方式 | 清理方法 |
|----------|----------|----------|----------|
| AI 总结 | 30 天 | 创建时间 | cron job |
| 视频元信息 | 账号存续期 | 用户删除 | 级联删除 |
| 转录文本 | 30 天 | 创建时间 | cron job |
| 问答会话 | 90 天 | 最后消息时间 | cron job |
| 思维导图 | 30 天 | 创建时间 | cron job |
| 审计日志 | 1 年 | 创建时间 | cron job |
| Stripe 收据 | 7 年 | 创建时间 | 不清理（合规） |
| 已处理事件 | 90 天 | 处理时间 | cron job |
| 临时文件 | 请求结束 | 请求完成 | 立即删除 |
| 软删除用户 | 30 天 | 删除时间 | 硬删除 |

### 5.2 清理 SQL 实现

```sql
-- 1. AI 总结清理（30 天）
DELETE FROM summaries
WHERE created_at < NOW() - INTERVAL '30 days';

-- 2. 转录文本清理（30 天）
DELETE FROM transcripts
WHERE created_at < NOW() - INTERVAL '30 days';

-- 3. 思维导图清理（30 天，随总结级联）
DELETE FROM mindmaps
WHERE created_at < NOW() - INTERVAL '30 days';

-- 4. 问答会话清理（90 天）
DELETE FROM qa_sessions
WHERE last_message_at < NOW() - INTERVAL '90 days';

-- 5. 审计日志清理（1 年）
DELETE FROM audit_logs
WHERE created_at < NOW() - INTERVAL '1 year';

-- 6. 已处理事件清理（90 天）
DELETE FROM processed_events
WHERE processed_at < NOW() - INTERVAL '90 days';

-- 7. 软删除用户硬删除（30 天后）
DELETE FROM users
WHERE deleted_at IS NOT NULL
  AND deleted_at < NOW() - INTERVAL '30 days';
```

### 5.3 Cron Job 实现

```python
# tasks/cleanup.py
"""数据清理定时任务."""
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CLEANUP_RULES = {
    "summaries": {"column": "created_at", "days": 30},
    "transcripts": {"column": "created_at", "days": 30},
    "mindmaps": {"column": "created_at", "days": 30},
    "qa_sessions": {"column": "last_message_at", "days": 90},
    "audit_logs": {"column": "created_at", "days": 365},
    "processed_events": {"column": "processed_at", "days": 90},
    "soft_deleted_users": {"column": "deleted_at", "days": 30, "hard_delete": True},
}

async def cleanup_expired_data(session: AsyncSession):
    """执行数据清理."""
    for table, rule in CLEANUP_RULES.items():
        cutoff = datetime.utcnow() - timedelta(days=rule["days"])

        if rule.get("hard_delete"):
            # 硬删除用户（已软删除超过保留期）
            query = text(f"""
                DELETE FROM {table}
                WHERE {rule['column']} IS NOT NULL
                  AND {rule['column']} < :cutoff
            """)
        else:
            query = text(f"""
                DELETE FROM {table}
                WHERE {rule['column']} < :cutoff
            """)

        result = await session.execute(query, {"cutoff": cutoff})
        print(f"Cleaned {result.rowcount} rows from {table}")

    await session.commit()
```

```bash
# Crontab 配置（每天凌晨 3 点执行）
0 3 * * * cd /app && /d/ProgramData/anaconda3/python.exe -m tasks.cleanup >> /var/log/cleanup.log 2>&1
```

### 5.4 临时文件清理

```python
# utils/temp_storage.py
"""临时文件管理，请求结束立即删除."""
import tempfile
import os
from contextlib import contextmanager
from pathlib import Path

TEMP_DIR = Path(tempfile.gettempdir()) / "video_summary"
TEMP_DIR.mkdir(exist_ok=True)

@contextmanager
def temp_file(suffix: str = "", prefix: str = "vs_"):
    """临时文件上下文管理器，自动清理."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=TEMP_DIR)
    os.close(fd)
    try:
        yield Path(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass  # 已删除则忽略

@contextmanager
def temp_dir(prefix: str = "vs_"):
    """临时目录上下文管理器."""
    path = tempfile.mkdtemp(prefix=prefix, dir=TEMP_DIR)
    try:
        yield Path(path)
    finally:
        import shutil
        shutil.rmtree(path, ignore_errors=True)

# FastAPI 中间件：请求结束时清理
@app.middleware("http")
async def cleanup_temp_files(request: Request, call_next):
    response = await call_next(request)
    # 请求结束后清理该请求的临时文件
    request_id = request.state.request_id
    for f in TEMP_DIR.glob(f"*_{request_id}*"):
        f.unlink(missing_ok=True)
    return response
```

---

## 6. 备份策略

### 6.1 SQLite 备份（MVP 阶段）

```bash
#!/bin/bash
# scripts/backup_sqlite.sh

set -euo pipefail

BACKUP_DIR="/backups/sqlite"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="./data/app.db"
BACKUP_FILE="$BACKUP_DIR/app_$DATE.db"
S3_BUCKET="s3://your-bucket/db-backups/"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# SQLite 在线备份（使用 .backup 命令，避免锁）
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# 压缩
gzip "$BACKUP_FILE"

# 上传到 S3/R2
aws s3 cp "$BACKUP_FILE.gz" "$S3_BUCKET" --storage-class STANDARD_IA

# 清理本地 7 天前的备份
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

```bash
# Crontab：每天凌晨 2 点备份
0 2 * * * /app/scripts/backup_sqlite.sh >> /var/log/db_backup.log 2>&1
```

### 6.2 PostgreSQL 备份（生产环境）

```bash
#!/bin/bash
# scripts/backup_postgres.sh

set -euo pipefail

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="videosummary"
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_$DATE.dump"
S3_BUCKET="s3://your-bucket/db-backups/"

mkdir -p "$BACKUP_DIR"

# pg_dump 自定义格式（支持选择性恢复）
pg_dump -Fc -Z9 -v \
    --no-owner \
    --no-privileges \
    --exclude-table='audit_logs_*' \
    "$DB_NAME" > "$BACKUP_FILE"

# 单独备份审计日志（分区表）
pg_dump -Fc -Z9 -v \
    --table='audit_logs' \
    "$DB_NAME" > "${BACKUP_DIR}/${DB_NAME}_audit_${DATE}.dump"

# 上传到 S3/R2
aws s3 cp "$BACKUP_FILE" "$S3_BUCKET" --storage-class STANDARD_IA

# 清理本地 3 天前的备份
find "$BACKUP_DIR" -name "*.dump" -mtime +3 -delete

echo "Backup completed: $BACKUP_FILE"
```

### 6.3 云托管备份方案

| 平台 | 备份方式 | 保留期 | 费用 |
|------|----------|--------|------|
| Railway | 自动每日备份 | 30 天 | 包含在套餐内 |
| Fly.io | 自动快照 | 7 天 | 包含在套餐内 |
| Supabase | 自动 PITR | 7 天（免费）/ 30 天（付费） | $0.08/GB |
| AWS RDS | 自动备份 + 快照 | 35 天 | $0.095/GB/月 |

### 6.4 恢复演练

```bash
#!/bin/bash
# scripts/restore_drill.sh
# 每季度执行一次恢复演练

set -euo pipefail

BACKUP_FILE="$1"
TEST_DB="videosummary_restore_test"

echo "=== 恢复演练开始 ==="
echo "备份文件: $BACKUP_FILE"

# 创建测试数据库
dropdb --if-exists "$TEST_DB"
createdb "$TEST_DB"

# 恢复
pg_restore -d "$TEST_DB" --no-owner --no-privileges "$BACKUP_FILE"

# 验证
psql -d "$TEST_DB" -c "
    SELECT 'users' as tbl, COUNT(*) FROM users
    UNION ALL SELECT 'videos', COUNT(*) FROM videos
    UNION ALL SELECT 'summaries', COUNT(*) FROM summaries;
"

# 清理
dropdb "$TEST_DB"

echo "=== 恢复演练完成 ==="
```

```bash
# 季度恢复演练（添加到 crontab）
# 每季度第一个月 1 号凌晨 4 点
0 4 1 1,4,7,10 * /app/scripts/restore_drill.sh /backups/postgres/latest.dump
```

### 6.5 备份监控

```python
# tasks/backup_monitor.py
"""备份状态监控与告警."""
import boto3
from datetime import datetime, timedelta

def check_backup_freshness():
    """检查最新备份是否超过 24 小时."""
    s3 = boto3.client('s3')
    bucket = 'your-bucket'
    prefix = 'db-backups/'

    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if 'Contents' not in response:
        send_alert("No backups found!")
        return False

    latest = max(response['Contents'], key=lambda x: x['LastModified'])
    age = datetime.utcnow() - latest['LastModified'].replace(tzinfo=None)

    if age > timedelta(hours=26):  # 24h + 2h buffer
        send_alert(f"Latest backup is {age} old: {latest['Key']}")
        return False

    return True
```

---

## 7. 性能优化

### 7.1 连接池配置

```python
# config/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

def create_pg_engine(database_url: str):
    """生产环境 PostgreSQL 连接池."""
    return create_async_engine(
        database_url,

        # 连接池配置
        poolclass=AsyncAdaptedQueuePool,
        pool_size=20,              # 常驻连接数
        max_overflow=10,           # 额外连接数
        pool_timeout=30,           # 等待连接超时（秒）
        pool_recycle=3600,         # 连接回收时间（秒）
        pool_pre_ping=True,        # 使用前检测连接健康

        # 执行配置
        execution_options={
            "isolation_level": "READ COMMITTED"
        },

        # 日志
        echo=False,
        echo_pool=False,
    )
```

```yaml
# 连接池参数参考（按服务器规格调整）
# 2 CPU / 4 GB RAM:
#   pool_size: 10, max_overflow: 5
# 4 CPU / 8 GB RAM:
#   pool_size: 20, max_overflow: 10
# 8 CPU / 16 GB RAM:
#   pool_size: 40, max_overflow: 20
```

### 7.2 查询优化

#### 7.2.1 常见查询优化

```sql
-- 反模式：全表扫描
EXPLAIN ANALYZE
SELECT * FROM videos WHERE user_id = 123 ORDER BY created_at DESC;
-- Seq Scan on videos (cost=0.00..1000.00 rows=500)

-- 优化后：使用复合索引
CREATE INDEX idx_videos_user_created ON videos(user_id, created_at DESC);
EXPLAIN ANALYZE
SELECT * FROM videos WHERE user_id = 123 ORDER BY created_at DESC LIMIT 20;
-- Index Scan using idx_videos_user_created (cost=0.42..12.50 rows=20)
```

#### 7.2.2 分页优化

```sql
-- 反模式：OFFSET 分页（深页性能差）
SELECT * FROM videos WHERE user_id = 123
ORDER BY created_at DESC
LIMIT 20 OFFSET 10000;

-- 优化后：游标分页（keyset pagination）
SELECT * FROM videos
WHERE user_id = 123 AND (created_at, id) < ($last_created_at, $last_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

#### 7.2.3 JSON 查询优化

```sql
-- 反模式：JSON 全量扫描
SELECT * FROM videos WHERE metadata->>'resolution' = '1080p';

-- 优化后：使用 GIN 索引 + JSONB 操作符
SELECT * FROM videos
WHERE metadata @> '{"resolution": "1080p"}';

-- 或使用表达式索引
CREATE INDEX idx_videos_resolution ON videos
    ((metadata->>'resolution'));
```

#### 7.2.4 N+1 查询避免

```python
# 反模式：N+1 查询
videos = await session.execute(select(Videos).where(Videos.user_id == user_id))
for video in videos:
    summary = await session.execute(
        select(Summaries).where(Summaries.video_id == video.id)
    )  # 每个视频一次查询！

# 优化后：JOIN 预加载
from sqlalchemy.orm import selectinload

stmt = (
    select(Videos)
    .where(Videos.user_id == user_id)
    .options(
        selectinload(Videos.summaries),
        selectinload(Videos.transcripts),
    )
    .order_by(Videos.created_at.desc())
)
result = await session.execute(stmt)
```

### 7.3 缓存层（Redis，可选）

```python
# config/cache.py
"""Redis 缓存层，缓存 AI 总结等昂贵数据."""
import json
import redis.asyncio as redis
from typing import Optional
from functools import wraps

redis_client = redis.Redis.from_url(
    "redis://localhost:6379/0",
    decode_responses=True,
    max_connections=20,
)

# 缓存键前缀
CACHE_PREFIX = "vs:"
CACHE_TTL = {
    "summary": 3600,        # 1 小时
    "video_meta": 1800,     # 30 分钟
    "user_quota": 300,      # 5 分钟
    "subscription": 600,    # 10 分钟
}

async def get_cached_summary(video_id: int, language: str) -> Optional[dict]:
    """获取缓存的总结."""
    key = f"{CACHE_PREFIX}summary:{video_id}:{language}"
    data = await redis_client.get(key)
    return json.loads(data) if data else None

async def set_cached_summary(video_id: int, language: str, summary: dict):
    """缓存总结."""
    key = f"{CACHE_PREFIX}summary:{video_id}:{language}"
    await redis_client.setex(key, CACHE_TTL["summary"], json.dumps(summary))

async def invalidate_summary(video_id: int, language: str):
    """总结更新后失效缓存."""
    key = f"{CACHE_PREFIX}summary:{video_id}:{language}"
    await redis_client.delete(key)

async def get_cached_quota(user_id: int) -> Optional[dict]:
    """获取缓存的用户配额."""
    key = f"{CACHE_PREFIX}quota:{user_id}"
    data = await redis_client.get(key)
    return json.loads(data) if data else None

async def increment_quota(user_id: int, tokens: int):
    """增加配额计数."""
    key = f"{CACHE_PREFIX}quota:{user_id}"
    pipe = redis_client.pipeline()
    pipe.incrby(key, tokens)
    pipe.expire(key, CACHE_TTL["user_quota"])
    await pipe.execute()
```

### 7.4 慢查询监控

```python
# middleware/query_monitor.py
"""慢查询监控中间件."""
import time
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("db.slow_query")

SLOW_QUERY_THRESHOLD_MS = 500  # 500ms 阈值

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.monotonic())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.monotonic() - conn.info["query_start_time"].pop(-1)
    duration_ms = total * 1000

    if duration_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            "Slow query detected: %.2fms\n%s",
            duration_ms,
            statement[:500],  # 截断长查询
        )
        # 发送到监控系统（Datadog / Prometheus）
        metrics.timing("db.slow_query", duration_ms, tags={"query": get_query_type(statement)})
```

```yaml
# 告警规则（Prometheus AlertGroups）
groups:
  - name: database
    rules:
      - alert: SlowQueryHigh
        expr: rate(db_slow_query_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "数据库慢查询过多"

      - alert: ConnectionPoolHigh
        expr: db_pool_active_connections / db_pool_max_connections > 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "数据库连接池使用率超过 80%"
```

---

## 8. 数据一致性

### 8.1 用户删除级联

```sql
-- 外键级联规则
-- videos.user_id → users.id ON DELETE CASCADE
-- transcripts.video_id → videos.id ON DELETE CASCADE
-- summaries.video_id → videos.id ON DELETE CASCADE
-- mindmaps.summary_id → summaries.id ON DELETE CASCADE
-- qa_sessions.user_id → users.id ON DELETE CASCADE
-- qa_sessions.video_id → videos.id ON DELETE CASCADE
-- subscriptions.user_id → users.id ON DELETE CASCADE
-- api_keys.user_id → users.id ON DELETE CASCADE
-- audit_logs.user_id → users.id ON DELETE SET NULL（保留审计）

-- 用户删除流程
CREATE OR REPLACE FUNCTION soft_delete_user(p_user_id BIGINT)
RETURNS VOID AS $$
BEGIN
    -- 1. 软删除用户
    UPDATE users SET deleted_at = NOW() WHERE id = p_user_id;

    -- 2. 取消订阅
    UPDATE subscriptions
    SET status = 'canceled', canceled_at = NOW()
    WHERE user_id = p_user_id AND status = 'active';

    -- 3. 撤销 API Key
    UPDATE api_keys
    SET revoked_at = NOW()
    WHERE user_id = p_user_id AND revoked_at IS NULL;

    -- 4. 记录审计
    INSERT INTO audit_logs (user_id, action, metadata)
    VALUES (p_user_id, 'user.soft_delete', '{"reason": "user_requested"}');
END;
$$ LANGUAGE plpgsql;
```

### 8.2 Stripe 订阅状态同步策略

```python
# services/subscription_sync.py
"""Stripe 订阅状态同步."""
from datetime import datetime
import stripe

async def sync_subscription_status(subscription):
    """从 Stripe 同步订阅状态到本地数据库."""
    stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

    # 状态映射
    status_map = {
        "incomplete": "incomplete",
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "unpaid",
    }

    await session.execute(
        update(Subscriptions)
        .where(Subscriptions.id == subscription.id)
        .values(
            status=status_map.get(stripe_sub.status, "incomplete"),
            current_period_start=datetime.fromtimestamp(
                stripe_sub.current_period_start
            ),
            current_period_end=datetime.fromtimestamp(
                stripe_sub.current_period_end
            ),
            cancel_at_period_end=stripe_sub.cancel_at_period_end,
            canceled_at=datetime.fromtimestamp(stripe_sub.canceled_at)
            if stripe_sub.canceled_at else None,
            updated_at=datetime.utcnow(),
        )
    )

    # 同步用户配额
    if stripe_sub.status == "active":
        plan_limits = {
            "pro_monthly": 100,
            "pro_yearly": 100,
        }
        limit = plan_limits.get(subscription.plan, 10)
        await session.execute(
            update(Users)
            .where(Users.id == subscription.user_id)
            .values(
                role="pro",
                monthly_quota_limit=limit,
            )
        )
    else:
        await session.execute(
            update(Users)
            .where(Users.id == subscription.user_id)
            .values(
                role="free",
                monthly_quota_limit=10,
            )
        )
```

### 8.3 缓存失效策略

```python
# services/cache_invalidation.py
"""缓存失效策略."""
from config.cache import redis_client, CACHE_PREFIX

class CacheInvalidation:
    """缓存失效管理器."""

    @staticmethod
    async def on_summary_created(video_id: int, language: str):
        """总结创建后缓存新数据."""
        # 不缓存，等读取时 lazy cache
        pass

    @staticmethod
    async def on_summary_updated(video_id: int, language: str):
        """总结更新后失效缓存."""
        key = f"{CACHE_PREFIX}summary:{video_id}:{language}"
        await redis_client.delete(key)

    @staticmethod
    async def on_video_deleted(video_id: int):
        """视频删除后清理所有相关缓存."""
        # 查找该视频的所有语言总结
        patterns = [
            f"{CACHE_PREFIX}summary:{video_id}:*",
            f"{CACHE_PREFIX}video_meta:{video_id}",
        ]
        for pattern in patterns:
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await redis_client.delete(*keys)

    @staticmethod
    async def on_user_quota_changed(user_id: int):
        """用户配额变化后失效配额缓存."""
        key = f"{CACHE_PREFIX}quota:{user_id}"
        await redis_client.delete(key)

    @staticmethod
    async def on_subscription_changed(user_id: int):
        """订阅变化后失效订阅缓存."""
        key = f"{CACHE_PREFIX}subscription:{user_id}"
        await redis_client.delete(key)
        # 同时失效配额缓存
        await CacheInvalidation.on_user_quota_changed(user_id)
```

### 8.4 事务管理

```python
# utils/transaction.py
"""事务管理工具."""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def transaction(session: AsyncSession):
    """事务上下文管理器."""
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise

# 使用示例
async def create_video_with_summary(video_data: dict, summary_data: dict):
    """创建视频并生成总结（原子操作）."""
    async with transaction(session) as tx:
        # 1. 创建视频
        video = Videos(**video_data)
        tx.add(video)
        await tx.flush()  # 获取 video.id

        # 2. 创建总结
        summary = Summary(video_id=video.id, **summary_data)
        tx.add(summary)

        # 3. 更新用户统计
        await tx.execute(
            update(Users)
            .where(Users.id == video_data["user_id"])
            .values(
                total_videos=Users.total_videos + 1,
                total_summary_tokens=Users.total_summary_tokens + summary_data.get("token_count", 0),
            )
        )
    # 事务自动提交
```

---

## 9. 验证清单（Checklist）

### 9.1 Schema 设计验证

- [ ] 所有表都有主键（`id BIGINT GENERATED ALWAYS AS IDENTITY`）
- [ ] 所有外键都有明确的 `ON DELETE` 行为
- [ ] 时间戳字段使用 `TIMESTAMPTZ`（带时区）
- [ ] JSON 字段使用 `JSONB`（PostgreSQL）或 `TEXT`（SQLite）
- [ ] 枚举类型使用 `CREATE TYPE ... AS ENUM` 或 `CHECK` 约束
- [ ] 所有 `VARCHAR` 字段有明确长度限制
- [ ] 所有表都有 `created_at` 和 `updated_at`
- [ ] 软删除表有 `deleted_at TIMESTAMPTZ`

### 9.2 索引验证

- [ ] 所有外键字段都有索引
- [ ] 高频查询字段有复合索引
- [ ] JSON 字段有 GIN 索引
- [ ] 部分索引覆盖常见过滤条件
- [ ] 唯一索引保证数据完整性
- [ ] 全文搜索索引覆盖标题和内容

### 9.3 性能验证

- [ ] 连接池配置合理（pool_size, max_overflow）
- [ ] 所有列表查询支持游标分页
- [ ] N+1 查询已识别并优化
- [ ] 慢查询阈值已设置（500ms）
- [ ] 缓存层已部署（Redis）
- [ ] EXPLAIN ANALYZE 验证关键查询

### 9.4 安全验证

- [ ] 用户密码不存储（Supabase Auth 处理）
- [ ] API Key 只存哈希（SHA-256）
- [ ] Stripe Webhook 签名验证
- [ ] SQL 注入防护（参数化查询）
- [ ] 审计日志记录所有敏感操作
- [ ] 外键级联不会意外删除关键数据

### 9.5 备份验证

- [ ] 自动备份 cron job 已配置
- [ ] 备份上传到 S3/R2
- [ ] 备份保留策略已设置
- [ ] 恢复演练已执行（每季度）
- [ ] 备份监控告警已配置

### 9.6 迁移验证

- [ ] Alembic 初始化完成
- [ ] 初始 migration 已生成
- [ ] SQLite → PostgreSQL 迁移脚本已测试
- [ ] 数据完整性验证查询已通过
- [ ] 回滚方案已文档化
- [ ] 迁移触发条件已监控

### 9.7 数据保留验证

- [ ] AI 总结 30 天清理 cron 已配置
- [ ] 审计日志 1 年清理 cron 已配置
- [ ] 软删除用户 30 天硬删除 cron 已配置
- [ ] Stripe 收据 7 年保留策略已确认
- [ ] 临时文件请求结束清理已实现

### 9.8 一致性验证

- [ ] 用户删除级联测试通过
- [ ] Stripe 订阅同步测试通过
- [ ] 缓存失效策略测试通过
- [ ] 事务回滚测试通过
- [ ] 并发写入测试通过

### 9.9 监控验证

- [ ] 慢查询日志已配置
- [ ] 连接池使用率监控已配置
- [ ] 备份状态监控已配置
- [ ] 磁盘使用率告警已配置
- [ ] 错误率告警已配置

### 9.10 文档验证

- [ ] ER 关系图已绘制
- [ ] 所有字段有 COMMENT
- [ ] 索引策略有说明
- [ ] 清理策略有说明
- [ ] 回滚方案有测试记录

---

## 附录 A：SQLite 兼容性注意事项

SQLite 与 PostgreSQL 的差异处理：

| 特性 | SQLite | PostgreSQL | 兼容方案 |
|------|--------|------------|----------|
| JSON | TEXT | JSONB | ORM 层抽象 |
| 枚举 | VARCHAR + CHECK | CREATE TYPE AS ENUM | 使用 CHECK |
| 自增 | AUTOINCREMENT | GENERATED ALWAYS AS IDENTITY | ORM 层抽象 |
| 布尔 | INTEGER (0/1) | BOOLEAN | ORM 层抽象 |
| 时间戳 | TEXT | TIMESTAMPTZ | ORM 层抽象 |
| GIN 索引 | 不支持 | 支持 | SQLite 用普通索引 |
| 数组 | 不支持 | 支持 | 用 JSON 代替 |

## 附录 B：常用查询示例

```sql
-- 1. 获取用户视频列表（分页）
SELECT v.id, v.title, v.duration, v.status, v.created_at,
       COUNT(s.id) as summary_count
FROM videos v
LEFT JOIN summaries s ON v.id = s.video_id
WHERE v.user_id = $1 AND v.deleted_at IS NULL
GROUP BY v.id
ORDER BY v.created_at DESC
LIMIT 20 OFFSET 0;

-- 2. 获取视频详情（含总结和转录）
SELECT v.*,
       json_agg(DISTINCT s.*) as summaries,
       json_agg(DISTINCT t.*) as transcripts
FROM videos v
LEFT JOIN summaries s ON v.id = s.video_id
LEFT JOIN transcripts t ON v.id = t.video_id
WHERE v.id = $1 AND v.user_id = $2
GROUP BY v.id;

-- 3. 用户配额检查
SELECT u.id, u.monthly_quota_used, u.monthly_quota_limit,
       u.monthly_quota_limit - u.monthly_quota_used as remaining,
       s.status as subscription_status
FROM users u
LEFT JOIN subscriptions s ON u.id = s.user_id AND s.status = 'active'
WHERE u.id = $1;

-- 4. 平台统计
SELECT platform,
       COUNT(*) as video_count,
       SUM(duration) as total_duration,
       AVG(duration) as avg_duration
FROM videos
WHERE status = 'completed'
GROUP BY platform
ORDER BY video_count DESC;

-- 5. 搜索视频（全文搜索）
SELECT id, title, ts_rank(to_tsvector('simple', title), query) as rank
FROM videos, plainto_tsquery('simple', $1) as query
WHERE to_tsvector('simple', title) @@ query
  AND user_id = $2
ORDER BY rank DESC
LIMIT 20;
```

## 附录 C：环境变量配置

```bash
# .env.example

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
# 生产环境：DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/videosummary

# Redis（可选）
REDIS_URL=redis://localhost:6379/0

# 备份
BACKUP_S3_BUCKET=s3://your-bucket/db-backups/
BACKUP_AWS_ACCESS_KEY_ID=your-key
BACKUP_AWS_SECRET_ACCESS_KEY=your-secret

# 监控
SLOW_QUERY_THRESHOLD_MS=500
ALERT_WEBHOOK_URL=https://hooks.slack.com/xxx
```

---

**文档版本历史**：

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-25 | 初始版本 |
