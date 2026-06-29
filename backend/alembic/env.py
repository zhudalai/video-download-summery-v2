"""Alembic 环境配置 — 支持 SQLite (开发) 和 PostgreSQL (生产) 双数据库。"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Alembic Config 对象
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型,确保 Alembic 能发现它们
from app.models import Base  # noqa: E402, F401
from app.config import get_settings  # noqa: E402

target_metadata = Base.metadata

settings = get_settings()


def get_database_url() -> str:
    """获取数据库 URL,确保使用 async 驱动。"""
    url = settings.DATABASE_URL
    # 确保使用 async 驱动
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def run_migrations_offline() -> None:
    """离线模式生成 SQL 脚本 (不连接数据库)。"""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 兼容: 使用 batch 模式
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式连接数据库执行迁移。"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_migrations)

    await connectable.dispose()


def do_migrations(connection):
    """同步迁移回调。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite 兼容
        compare_type=True,     # 检测列类型变化
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
