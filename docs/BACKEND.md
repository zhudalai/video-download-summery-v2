# FastAPI 后端架构规范文档

> 项目：Video Download Summary（视频下载 + AI 总结 SaaS）
> 版本：v1.0
> 语言：中文 / English / 日本語
> 状态：MVP 架构基线（1-2 个月交付）

---

## 目录

1. [项目概览与约束](#1-项目概览与约束)
2. [目录结构](#2-目录结构)
3. [核心模块设计](#3-核心模块设计)
4. [SSE 流式输出实现](#4-sse-流式输出实现)
5. [yt-dlp 集成](#5-yt-dlp-集成)
6. [OpenRouter 网关](#6-openrouter-网关)
7. [错误码体系](#7-错误码体系)
8. [配置管理](#8-配置管理)
9. [日志规范](#9-日志规范)
10. [国际化与本地化](#10-国际化与本地化)
11. [安全与合规](#11-安全与合规)
12. [部署与运维](#12-部署与运维)
13. [验证清单](#13-验证清单)

---

## 1. 项目概览与约束

### 1.1 技术栈

| 层级 | 技术 | 备注 |
|---|---|---|
| Web 框架 | FastAPI 0.115+ | 原生异步、OpenAPI 自动生成 |
| ASGI 服务器 | Uvicorn + Gunicorn | 生产多 worker |
| 数据库 | SQLite (MVP) → PostgreSQL (生产) | 通过 SQLAlchemy 抽象 |
| ORM | SQLAlchemy 2.0 (async) | 统一异步会话 |
| 数据验证 | Pydantic v2 | 请求/响应模型 |
| 认证 | Supabase Auth (云端) | 抽象层保护可迁移性 |
| AI 网关 | OpenRouter | 按语言路由 |
| 支付 | Stripe Checkout + Webhook | PDF 自渲染收据 |
| 任务队列 | asyncio (MVP) → Celery (V2) | 下载与总结异步化 |
| 日志 | structlog | 结构化 JSON 日志 |
| 测试 | pytest + httpx.AsyncClient | 全异步测试 |

### 1.2 关键约束

- **不持久化视频文件**：下载到临时目录，总结完成后立即删除
- **性能目标**：API P99 < 800ms（不含 SSE 流式时间）
- **三语言 V1**：英语 + 中文（简体）+ 日语
- **MVP 数据库**：SQLite，迁移路径已预留
- **部署**：Railway / Fly.io（后端），Vercel（前端）

---

## 2. 目录结构

```
backend/
├── alembic/                        # 数据库迁移
│   ├── versions/
│   └── env.py
├── app/
│   ├── __init__.py
│   ├── main.py                     # 应用启动、中间件、异常处理
│   ├── config.py                   # pydantic-settings 配置
│   ├── database.py                 # SQLAlchemy 引擎/会话
│   ├── exceptions.py               # 统一异常类
│   ├── dependencies.py             # 依赖注入（get_db, get_current_user, get_locale）
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── request_id.py           # X-Request-ID 注入
│   │   ├── rate_limit.py           # 速率限制（按用户/IP）
│   │   └── logging.py              # 请求/响应日志中间件
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── router.py               # 路由聚合
│   │   ├── video.py                # /api/video/* 视频解析与下载
│   │   ├── ai.py                   # /api/ai/* AI 总结（SSE）
│   │   ├── payment.py              # /api/payment/* Stripe 相关
│   │   ├── users.py                # /api/users/* 用户配置
│   │   └── admin.py                # /api/admin/* 运营后台
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ytdlp_service.py        # yt-dlp 封装（含抖音模块）
│   │   ├── openrouter_client.py    # OpenRouter 网关客户端
│   │   ├── summary_service.py      # 总结编排（下载→提取→LLM）
│   │   ├── stripe_client.py        # Stripe 客户端封装
│   │   ├── receipt_renderer.py     # PDF 收据自渲染
│   │   ├── auth_service.py         # Supabase Auth 抽象层
│   │   ├── usage_service.py        # Token/次数用量统计
│   │   └── locale_service.py       # 语言与 Prompt 选择
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py              # Pydantic 请求/响应模型
│   │   ├── db_models.py            # SQLAlchemy ORM 模型
│   │   └── enums.py                # 枚举（Plan, Language, SummaryStatus）
│   ├── deps/
│   │   ├── __init__.py
│   │   ├── db.py                   # get_db 异步会话注入
│   │   ├── auth.py                 # get_current_user 注入
│   │   ├── locale.py               # get_locale 注入
│   │   └── usage.py                # 用户配额注入
│   ├── prompts/
│   │   ├── zh.md                   # 中文总结 Prompt
│   │   ├── en.md                   # 英文总结 Prompt
│   │   └── ja.md                   # 日文总结 Prompt
│   └── utils/
│       ├── __init__.py
│       ├── security.py             # 签名/脱敏工具
│       ├── i18n.py                 # 错误消息翻译
│       └── helpers.py              # 通用工具函数
├── tests/
│   ├── conftest.py
│   ├── test_video.py
│   ├── test_ai.py
│   ├── test_payment.py
│   └── test_openrouter.py
├── scripts/
│   ├── seed_data.py
│   └── migrate_sqlite_to_pg.py
├── .env.example                    # 环境变量模板
├── .env.local                      # 本地配置（不提交）
├── pyproject.toml                  # 依赖与工具配置
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 3. 核心模块设计

### 3.1 app/main.py — 启动、中间件、异常处理

```python
"""应用入口：中间件注册、异常处理器、生命周期管理。"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, async_session_factory
from app.exceptions import AppError, ErrorCode
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers.router import api_router
from app.utils.i18n import translate_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动连接池、关闭清理。"""
    # Startup
    async with engine.begin() as conn:
        # SQLite 模式下自动建表（MVP）；生产走 Alembic
        if settings.DB_TYPE == "sqlite":
            from app.models.db_models import Base
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Video Summary API",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # 中间件注册（顺序 = 执行顺序，最后注册的最先执行）
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 统一异常处理器
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        """业务异常 → 统一错误响应。"""
        locale = request.state.locale if hasattr(request.state, "locale") else "en"
        message = translate_error(exc.code, locale, exc.detail)
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.code,
                "message": message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """兜底：未处理异常。"""
        # 内部日志记录完整堆栈
        import logging
        logger = logging.getLogger("app")
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "detail": str(exc) if settings.DEBUG else None,
            },
        )

    # 路由挂载
    app.include_router(api_router, prefix="/api")

    # 健康检查
    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    return app


app = create_app()
```

### 3.2 app/routers/ — 路由分组

```python
"""app/routers/router.py — 路由聚合中心。"""

from fastapi import APIRouter

from app.routers.video import router as video_router
from app.routers.ai import router as ai_router
from app.routers.payment import router as payment_router
from app.routers.users import router as users_router
from app.routers.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(video_router, prefix="/video", tags=["video"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai"])
api_router.include_router(payment_router, prefix="/payment", tags=["payment"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
```

```python
"""app/routers/ai.py — AI 总结路由（SSE 流式）。"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.deps.auth import get_current_user
from app.deps.locale import get_locale
from app.models.schemas import (
    SummaryRequest,
    SummaryStreamEvent,
    SummaryResponse,
)
from app.services.summary_service import SummaryService

router = APIRouter()


@router.post("/summary", response_model=SummaryResponse)
async def create_summary(
    req: SummaryRequest,
    user=Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """非流式总结（短视频/兼容接口）。"""
    service = SummaryService()
    return await service.summarize_video(req, user, locale)


@router.post("/summary/stream")
async def stream_summary(
    req: SummaryRequest,
    user=Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """SSE 流式总结（主要入口）。"""
    service = SummaryService()

    async def event_generator():
        async for event in service.stream_summary(req, user, locale):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
```

### 3.3 app/services/ — 业务逻辑层

```python
"""app/services/summary_service.py — 总结编排：下载 → 提取 → LLM。"""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator

from app.exceptions import AppError, ErrorCode
from app.models.db_models import Summary, SummaryStatus
from app.models.schemas import SummaryRequest, SummaryStreamEvent
from app.services.ytdlp_service import YTDLPService
from app.services.openrouter_client import OpenRouterClient
from app.services.locale_service import LocaleService
from app.deps.db import get_db


class SummaryService:
    """视频总结主流程。"""

    def __init__(self):
        self.ytdlp = YTDLPService()
        self.llm = OpenRouterClient()
        self.locale_svc = LocaleService()

    async def stream_summary(
        self,
        req: SummaryRequest,
        user,
        locale: str,
    ) -> AsyncGenerator[SummaryStreamEvent, None]:
        """
        SSE 事件流：
        1. status: parsing（解析视频信息）
        2. status: downloading（下载进度 0-100）
        3. status: extracting（提取音频/字幕）
        4. status: summarizing（LLM 流式输出）
        5. done: 最终结果
        6. error: 失败（含 fallback 通知）
        """
        # 1. 解析视频信息
        yield SummaryStreamEvent(
            event="status",
            data={"stage": "parsing", "progress": 0},
        )
        try:
            video_info = await self.ytdlp.extract_info(req.url)
        except Exception as e:
            yield SummaryStreamEvent(
                event="error",
                data={"code": ErrorCode.VIDEO_PARSE_ERROR, "detail": str(e)},
            )
            return

        # 2. 下载到临时目录
        with tempfile.TemporaryDirectory(prefix="vsum_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            def on_progress(progress: int):
                """下载进度回调。"""
                asyncio.ensure_future(
                    # 通过队列回传进度（简化示意）
                    self._emit_progress(progress)
                )

            yield SummaryStreamEvent(
                event="status",
                data={"stage": "downloading", "progress": 0},
            )

            video_path = await self.ytdlp.download(
                req.url,
                tmp_path,
                on_progress=on_progress,
            )

            # 3. 提取字幕/转录
            yield SummaryStreamEvent(
                event="status",
                data={"stage": "extracting", "progress": 0},
            )
            transcript = await self.ytdlp.extract_subtitles(video_path, locale)

            # 4. LLM 流式总结
            yield SummaryStreamEvent(
                event="status",
                data={"stage": "summarizing", "progress": 0},
            )

            prompt = self.locale_svc.build_prompt(locale, video_info, transcript)
            async for chunk in self.llm.stream_chat(prompt, locale):
                yield SummaryStreamEvent(
                    event="chunk",
                    data={"text": chunk},
                )

            # 5. 完成（临时目录自动清理）
            yield SummaryStreamEvent(
                event="done",
                data={"message": "Summary completed"},
            )

    async def summarize_video(self, req, user, locale):
        """非流式版本（收集所有 chunk 后返回）。"""
        chunks = []
        async for event in self.stream_summary(req, user, locale):
            if event.event == "chunk":
                chunks.append(event.data["text"])
            elif event.event == "error":
                raise AppError(code=event.data["code"], detail=event.data["detail"])

        full_text = "".join(chunks)
        return SummaryResponse(summary=full_text, language=locale)

    async def _emit_progress(self, progress: int):
        """内部：通过队列发送进度事件（实现略）。"""
        pass
```

```python
"""app/services/openrouter_client.py — OpenRouter 网关客户端。"""

import httpx
from typing import AsyncGenerator

from app.config import settings
from app.exceptions import AppError, ErrorCode


# 语言路由规则（核心配置）
LANGUAGE_MODEL_MAP = {
    "zh": {
        "primary": "deepseek/deepseek-chat",
        "fallback": ["deepseek/deepseek-coder", "qwen/qwen-2.5-72b-instruct"],
    },
    "en": {
        "primary": "anthropic/claude-sonnet-4-20250514",
        "fallback": ["openai/gpt-4o", "google/gemini-2.5-flash"],
    },
    "ja": {
        "primary": "openai/gpt-4o",
        "fallback": ["anthropic/claude-sonnet-4-20250514", "google/gemini-2.5-flash"],
    },
}


class OpenRouterClient:
    """OpenRouter 统一网关：语言路由 + fallback + 用量统计。"""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": settings.APP_URL,
                "X-Title": "Video Summary",
            },
            timeout=120.0,
        )

    def get_model(self, locale: str) -> dict:
        """根据语言返回主模型 + fallback 列表。"""
        return LANGUAGE_MODEL_MAP.get(locale, LANGUAGE_MODEL_MAP["en"])

    async def stream_chat(
        self,
        prompt: str,
        locale: str,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """流式聊天，自动 fallback。"""
        model_config = self.get_model(locale)
        models = [model_config["primary"]] + model_config["fallback"]

        last_error = None
        for model in models:
            try:
                async for chunk in self._stream_request(model, prompt, max_tokens):
                    yield chunk
                return  # 成功则退出 fallback 链
            except Exception as e:
                last_error = e
                # 记录 fallback 事件
                continue

        # 所有模型都失败
        raise AppError(
            code=ErrorCode.LLM_ALL_FAILED,
            detail=f"All models failed. Last error: {last_error}",
        )

    async def _stream_request(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """单次 SSE 请求。"""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "max_tokens": max_tokens,
        }

        async with self.client.stream(
            "POST",
            "/chat/completions",
            json=payload,
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise Exception(f"OpenRouter error {response.status_code}: {body}")

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    # 解析 SSE chunk（简化示意）
                    import json
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        if content := delta.get("content"):
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def get_usage_stats(self, user_id: str) -> dict:
        """查询用户 Token 用量（从本地统计表聚合）。"""
        # 实际实现查询 usage_logs 表
        return {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
```

```python
"""app/services/stripe_client.py — Stripe 客户端封装。"""

import stripe
from fastapi import Request

from app.config import settings
from app.exceptions import AppError, ErrorCode


class StripeClient:
    """Stripe Checkout + Webhook 封装。"""

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        self.price_ids = {
            "pro_monthly": settings.STRIPE_PRICE_PRO_MONTHLY,
            "pro_yearly": settings.STRIPE_PRICE_PRO_YEARLY,
            "premium_monthly": settings.STRIPE_PRICE_PREMIUM_MONTHLY,
        }

    async def create_checkout_session(
        self,
        user_id: str,
        plan: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """创建 Stripe Checkout 会话，返回 URL。"""
        price_id = self.price_ids.get(plan)
        if not price_id:
            raise AppError(
                code=ErrorCode.PAYMENT_INVALID_PLAN,
                detail=f"Unknown plan: {plan}",
            )

        session = stripe.checkout.Session.create(
            mode="payment" if "yearly" in plan else "subscription",
            customer_email=None,  # 由前端传入或从 user 取
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id, "plan": plan},
        )
        return session.url

    async def verify_webhook(self, request: Request) -> dict:
        """验证并解析 Stripe Webhook 事件。"""
        body = await request.body()
        sig_header = request.headers.get("stripe-signature")

        try:
            event = stripe.Webhook.construct_event(
                body, sig_header, self.webhook_secret
            )
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            raise AppError(
                code=ErrorCode.PAYMENT_WEBHOOK_INVALID,
                detail=str(e),
                http_status=400,
            )

        return event
```

### 3.4 app/models/ — Pydantic 请求/响应模型

```python
"""app/models/schemas.py — 请求/响应数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


# ===== 枚举 =====

class SummaryStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


class Locale(str, Enum):
    EN = "en"
    ZH = "zh"
    JA = "ja"


# ===== 请求模型 =====

class SummaryRequest(BaseModel):
    url: HttpUrl = Field(..., description="视频 URL（支持 YouTube/Bilibili/TikTok 等）")
    language: Optional[Locale] = Field(
        None,
        description="总结语言，默认跟随用户偏好",
    )
    format: str = Field(
        "markdown",
        description="输出格式：markdown / plain / bullet",
    )
    length: str = Field(
        "medium",
        description="总结长度：short / medium / long",
    )


class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="pro_monthly / pro_yearly / premium_monthly")
    success_url: HttpUrl
    cancel_url: HttpUrl


# ===== 响应模型 =====

class VideoInfo(BaseModel):
    title: str
    duration: int = Field(..., description="视频时长（秒）")
    uploader: Optional[str] = None
    thumbnail: Optional[HttpUrl] = None
    platform: str = Field(..., description="youtube / bilibili / tiktok / etc.")


class SummaryResponse(BaseModel):
    id: str = Field(..., description="总结记录 ID")
    summary: str
    language: Locale
    created_at: datetime
    tokens_used: Optional[int] = None


class UserProfile(BaseModel):
    id: str
    email: str
    plan: PlanTier
    daily_usage: int = Field(..., description="今日已用次数")
    daily_limit: int = Field(..., description="每日上限")
    preferred_language: Locale


# ===== SSE 事件模型 =====

class SummaryStreamEvent(BaseModel):
    """SSE 事件载荷。"""
    event: str = Field(..., description="status / chunk / done / error / ping")
    data: dict = Field(default_factory=dict)


# ===== 通用错误响应 =====

class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Optional[str] = None
```

### 3.5 app/deps/ — 依赖注入

```python
"""app/deps/db.py — 数据库会话注入。"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """注入异步数据库会话，请求结束自动关闭。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

```python
"""app/deps/auth.py — 当前用户注入（Supabase Auth 抽象层）。"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth_service import AuthService
from app.models.db_models import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    从 Supabase JWT 解析当前用户。
    抽象层保护：未来可切换为自建 Auth，只需替换此函数实现。
    """
    token = credentials.credentials
    auth_service = AuthService()

    try:
        supabase_user = await auth_service.verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # 映射到本地 User 记录（首次登录自动创建）
    user = await auth_service.get_or_create_local_user(supabase_user)
    return user
```

```python
"""app/deps/locale.py — 语言环境注入。"""

from fastapi import Request


async def get_locale(request: Request) -> str:
    """
    语言优先级：
    1. 请求体中的 language 字段（需中间件提前解析）
    2. 用户偏好（从 DB 取）
    3. Accept-Language 头
    4. 默认英语
    """
    # 从请求头解析
    accept_lang = request.headers.get("Accept-Language", "")
    if accept_lang:
        primary = accept_lang.split(",")[0].split("-")[0].lower()
        if primary in ("en", "zh", "ja"):
            return primary

    # 从查询参数
    if lang := request.query_params.get("lang"):
        if lang in ("en", "zh", "ja"):
            return lang

    return "en"
```

---

## 4. SSE 流式输出实现

### 4.1 协议设计

SSE 事件类型定义：

| event 类型 | 载荷 | 说明 |
|---|---|---|
| `status` | `{stage, progress}` | 阶段切换：parsing/downloading/extracting/summarizing |
| `chunk` | `{text}` | LLM 流式输出片段 |
| `done` | `{message}` | 总结完成 |
| `error` | `{code, detail}` | 错误（含错误码） |
| `ping` | `{}` | 心跳保活（每 30s） |

### 4.2 路由实现

```python
"""app/routers/ai.py（SSE 核心实现）。"""

import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.models.schemas import SummaryRequest, SummaryStreamEvent
from app.services.summary_service import SummaryService
from app.deps.auth import get_current_user
from app.deps.locale import get_locale

router = APIRouter()


@router.post("/summary/stream")
async def stream_summary(
    req: SummaryRequest,
    user=Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """
    SSE 流式总结端点。

    特性：
    - 心跳保活：每 30s 发送 ping 事件
    - 错误 fallback：LLM 失败自动切换模型
    - 进度反馈：下载进度实时推送
    """
    service = SummaryService()

    async def event_generator() -> AsyncGenerator[str, None]:
        heartbeat_task = None
        try:
            # 启动心跳协程
            heartbeat_task = asyncio.create_task(_heartbeat_loop())

            async for event in service.stream_summary(req, user, locale):
                yield _format_sse(event)

        except Exception as e:
            # 兜底错误
            error_event = SummaryStreamEvent(
                event="error",
                data={"code": "STREAM_ERROR", "detail": str(e)},
            )
            yield _format_sse(error_event)
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _format_sse(event: SummaryStreamEvent) -> str:
    """格式化为 SSE 帧。"""
    return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


async def _heartbeat_loop():
    """每 30s 发送 ping 保持连接。"""
    while True:
        await asyncio.sleep(30)
        yield _format_sse(SummaryStreamEvent(event="ping", data={}))
```

### 4.3 前端消费示例

```javascript
// 前端（Vue 3）消费 SSE
async function streamSummary(videoUrl, language) {
  const response = await fetch('/api/ai/summary/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ url: videoUrl, language }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const event = JSON.parse(line.slice(6));
        switch (event.event) {
          case 'status':
            updateProgress(event.data.stage, event.data.progress);
            break;
          case 'chunk':
            appendSummary(event.data.text);
            break;
          case 'done':
            finishSummary();
            break;
          case 'error':
            showError(event.data.code, event.data.detail);
            break;
        }
      }
    }
  }
}
```

### 4.4 错误处理与 Fallback

```python
"""LLM 调用失败 fallback 策略。"""

from app.exceptions import ErrorCode

# 错误码 → 用户提示映射
ERROR_MESSAGES = {
    ErrorCode.VIDEO_PARSE_ERROR: {
        "en": "Unable to parse this video URL. Please check the link.",
        "zh": "无法解析该视频链接，请检查地址是否正确。",
        "ja": "この動画URLを解析できません。リンクをご確認ください。",
    },
    ErrorCode.LLM_ALL_FAILED: {
        "en": "AI service is temporarily unavailable. Please retry.",
        "zh": "AI 服务暂时不可用，请稍后重试。",
        "ja": "AIサービスが一時的に利用できません。再試行してください。",
    },
    ErrorCode.QUOTA_EXCEEDED: {
        "en": "Daily limit reached. Upgrade to Pro for unlimited access.",
        "zh": "今日次数已用完，升级 Pro 可无限使用。",
        "ja": "本日の上限に達しました。Pro にアップグレードしてください。",
    },
}


class FallbackStrategy:
    """模型 fallback 策略。"""

    @staticmethod
    def should_retry(error_code: str) -> bool:
        """判断是否可重试。"""
        retryable = {
            ErrorCode.LLM_TIMEOUT,
            ErrorCode.LLM_RATE_LIMIT,
            ErrorCode.NETWORK_ERROR,
        }
        return error_code in retryable

    @staticmethod
    def get_fallback_model(primary_model: str, locale: str) -> str:
        """获取 fallback 模型。"""
        from app.services.openrouter_client import LANGUAGE_MODEL_MAP
        config = LANGUAGE_MODEL_MAP.get(locale, LANGUAGE_MODEL_MAP["en"])
        for model in config["fallback"]:
            if model != primary_model:
                return model
        return config["fallback"][0]
```

---

## 5. yt-dlp 集成

### 5.1 核心服务

```python
"""app/services/ytdlp_service.py — yt-dlp 异步封装。"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from app.exceptions import AppError, ErrorCode


class YTDLPService:
    """视频信息提取与下载服务。"""

    # 通用下载选项
    BASE_OPTS = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": 500 * 1024 * 1024,  # 500MB 上限
        "socket_timeout": 30,
    }

    async def extract_info(self, url: str) -> dict:
        """异步提取视频元信息（不下载）。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_extract_info, url
        )

    def _sync_extract_info(self, url: str) -> dict:
        """同步提取（在线程池执行）。"""
        opts = {**self.BASE_OPTS, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as e:
                raise AppError(
                    code=ErrorCode.VIDEO_PARSE_ERROR,
                    detail=str(e),
                )

        return {
            "id": info.get("id"),
            "title": info.get("title", "Untitled"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader"),
            "thumbnail": info.get("thumbnail"),
            "platform": info.get("extractor", "unknown").split(":")[0],
            "categories": info.get("categories", []),
            "automatic_captions": list(info.get("automatic_captions", {}).keys()),
            "subtitles": list(info.get("subtitles", {}).keys()),
        }

    async def download(
        self,
        url: str,
        output_dir: Path,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> Path:
        """
        异步下载视频到指定目录。
        返回下载文件路径。
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._sync_download,
            url,
            output_dir,
            on_progress,
        )

    def _sync_download(
        self,
        url: str,
        output_dir: Path,
        on_progress: Optional[Callable[[int], None]],
    ) -> Path:
        """同步下载（在线程池执行）。"""
        opts = {
            **self.BASE_OPTS,
            "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
            "progress_hooks": [
                lambda d: self._on_progress(d, on_progress)
            ] if on_progress else [],
        }

        # 抖音专用处理
        if "tiktok" in url or "douyin" in url:
            opts.update(self._douyin_opts())

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            path = Path(filename)

        if not path.exists():
            raise AppError(
                code=ErrorCode.VIDEO_DOWNLOAD_ERROR,
                detail="Download completed but file not found",
            )

        return path

    def _on_progress(self, d: dict, callback: Callable[[int], None]):
        """yt-dlp 进度回调 → 转换为 0-100 整数。"""
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                progress = int(downloaded / total * 100)
                callback(progress)

    def _douyin_opts(self) -> dict:
        """抖音专用下载选项。"""
        return {
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.douyin.com/",
            },
            "extractor_args": {
                "douyin": {
                    "api_hostname": "api.douyin.com",
                }
            },
        }

    async def extract_subtitles(
        self,
        video_path: Path,
        locale: str,
    ) -> str:
        """
        提取字幕/转录文本。
        优先使用已有字幕，否则提取音频后用 Whisper 转录。
        """
        # 1. 尝试从 info 中获取字幕 URL（实现略）
        # 2. 无字幕时提取音频 → Whisper 转录
        # MVP 阶段：返回字幕文本或空字符串
        return await self._extract_captions(video_path, locale)

    async def _extract_captions(self, video_path: Path, locale: str) -> str:
        """提取字幕（简化实现）。"""
        # 实际实现：读取 yt-dlp 下载的 .vtt/.srt 文件
        # 或调用 Whisper API
        return ""

    async def cleanup(self, video_path: Path):
        """显式清理视频文件（双保险）。"""
        if video_path.exists():
            video_path.unlink()
        # 清理父目录（如果是临时目录）
        parent = video_path.parent
        if parent.name.startswith("vsum_") and parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
```

### 5.2 抖音专用解析模块

```python
"""app/services/platforms/douyin.py — 抖音专用解析器。"""

import re
import httpx
from urllib.parse import urlparse

from app.exceptions import AppError, ErrorCode


class DouyinParser:
    """
    yt-dlp 对抖音支持不稳定时的专用解析模块。
    直接调用抖音网页版 API 获取视频信息。
    """

    API_BASE = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.douyin.com/",
        "Cookie": "msToken=abcdefg",
    }

    @classmethod
    def parse_url(cls, url: str) -> str:
        """从分享链接提取实际 URL。"""
        # 处理短链接 vm.douyin.com/xxxxx
        if "vm.douyin.com" in url:
            parsed = urlparse(url)
            # 跟随重定向获取真实 URL
            with httpx.Client(follow_redirects=True) as client:
                resp = client.head(url, headers=cls.HEADERS)
                return str(resp.url)
        return url

    @classmethod
    async def get_video_id(cls, url: str) -> str:
        """提取抖音视频 ID。"""
        # 从 URL 中提取 video ID
        patterns = [
            r"/video/(\d+)",
            r"modal_id=(\d+)",
            r"/note/(\d+)",
        ]
        for pattern in patterns:
            if match := re.search(pattern, url):
                return match.group(1)
        raise AppError(
            code=ErrorCode.VIDEO_PARSE_ERROR,
            detail="Cannot extract Douyin video ID from URL",
        )

    @classmethod
    async def get_video_info(cls, video_id: str) -> dict:
        """调用抖音 API 获取视频详情。"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                cls.API_BASE,
                json={"aweme_id": video_id},
                headers=cls.HEADERS,
            )
            data = resp.json()

        detail = data.get("aweme_detail", {})
        if not detail:
            raise AppError(
                code=ErrorCode.VIDEO_PARSE_ERROR,
                detail="Douyin API returned empty detail",
            )

        return {
            "id": detail.get("aweme_id"),
            "title": detail.get("desc", "Douyin Video"),
            "duration": detail.get("video", {}).get("duration", 0) // 1000,
            "uploader": detail.get("author", {}).get("nickname"),
            "thumbnail": detail.get("video", {}).get("cover", {}).get("url_list", [None])[0],
            "platform": "douyin",
            "play_addr": detail.get("video", {}).get("play_addr", {}).get("url_list", [None])[0],
        }
```

### 5.3 进度回调机制

```python
"""下载进度实时推送（通过 SSE channel）。"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class DownloadProgress:
    """下载进度状态。"""
    user_id: str
    task_id: str
    progress: int = 0
    stage: str = "pending"
    _subscribers: list = field(default_factory=list)

    def subscribe(self, queue: asyncio.Queue):
        self._subscribers.append(queue)

    async def update(self, progress: int, stage: str = None):
        self.progress = progress
        if stage:
            self.stage = stage
        for q in self._subscribers:
            await q.put({"progress": progress, "stage": self.stage})


# 全局进度管理器
class ProgressManager:
    _tasks: Dict[str, DownloadProgress] = {}

    @classmethod
    def create_task(cls, user_id: str, task_id: str) -> DownloadProgress:
        progress = DownloadProgress(user_id=user_id, task_id=task_id)
        cls._tasks[task_id] = progress
        return progress

    @classmethod
    def get_task(cls, task_id: str) -> Optional[DownloadProgress]:
        return cls._tasks.get(task_id)

    @classmethod
    def cleanup(cls, task_id: str):
        cls._tasks.pop(task_id, None)
```

---

## 6. OpenRouter 网关

### 6.1 语言路由规则

| 语言 | 主模型 | Fallback 链 |
|---|---|---|
| 中文 (zh) | `deepseek/deepseek-chat` | `deepseek/deepseek-coder` → `qwen/qwen-2.5-72b-instruct` |
| 英文 (en) | `anthropic/claude-sonnet-4-20250514` | `openai/gpt-4o` → `google/gemini-2.5-flash` |
| 日文 (ja) | `openai/gpt-4o` | `anthropic/claude-sonnet-4-20250514` → `google/gemini-2.5-flash` |

### 6.2 路由决策流程

```
请求到达
    ↓
提取 locale（查询参数 / 用户偏好 / Accept-Language）
    ↓
查找 LANGUAGE_MODEL_MAP[locale]
    ↓
尝试 primary 模型
    ↓ 失败
尝试 fallback[0]
    ↓ 失败
尝试 fallback[1]
    ↓ 全部失败
返回 LLM_ALL_FAILED 错误
```

### 6.3 Token 用量统计

```python
"""app/services/usage_service.py — Token 用量追踪。"""

from datetime import datetime, date
from sqlalchemy import func, select

from app.deps.db import get_db
from app.models.db_models import UsageLog


class UsageService:
    """用户用量统计。"""

    async def log_usage(
        self,
        user_id: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        request_type: str,  # "summary" / "transcript"
    ):
        """记录每次 LLM 调用。"""
        async for session in get_db():
            log = UsageLog(
                user_id=user_id,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                request_type=request_type,
                created_at=datetime.utcnow(),
            )
            session.add(log)
            await session.commit()
            break

    async def get_daily_usage(self, user_id: str) -> int:
        """获取用户今日已用次数。"""
        today = date.today()
        async for session in get_db():
            result = await session.execute(
                select(func.count(UsageLog.id)).where(
                    UsageLog.user_id == user_id,
                    func.date(UsageLog.created_at) == today,
                )
            )
            return result.scalar() or 0

    async def get_monthly_cost(self, user_id: str) -> float:
        """获取用户本月累计费用。"""
        async for session in get_db():
            result = await session.execute(
                select(func.sum(UsageLog.cost_usd)).where(
                    UsageLog.user_id == user_id,
                    func.strftime("%Y-%m", UsageLog.created_at) == date.today().strftime("%Y-%m"),
                )
            )
            return float(result.scalar() or 0)
```

---

## 7. 错误码体系

### 7.1 统一错误响应格式

```json
{
  "code": "VIDEO_PARSE_ERROR",
  "message": "无法解析该视频链接，请检查地址是否正确。",
  "detail": "Unsupported URL: https://example.com/not-a-video"
}
```

### 7.2 错误码命名规范

格式：`{模块}_{动作}_{状态}`

| 模块 | 前缀 | 示例 |
|---|---|---|
| 视频 | `VIDEO_` | `VIDEO_PARSE_ERROR`, `VIDEO_DOWNLOAD_ERROR` |
| AI/LLM | `LLM_` | `LLM_TIMEOUT`, `LLM_ALL_FAILED`, `LLM_RATE_LIMIT` |
| 支付 | `PAYMENT_` | `PAYMENT_WEBHOOK_INVALID`, `PAYMENT_INVALID_PLAN` |
| 用户 | `USER_` | `USER_NOT_FOUND`, `USER_QUOTA_EXCEEDED` |
| 认证 | `AUTH_` | `AUTH_TOKEN_EXPIRED`, `AUTH_INVALID_CREDENTIALS` |
| 系统 | `INTERNAL_` | `INTERNAL_ERROR`, `NETWORK_ERROR` |

### 7.3 完整错误码清单

```python
"""app/exceptions.py — 统一异常类与错误码定义。"""

from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    # 视频模块
    VIDEO_PARSE_ERROR = "VIDEO_PARSE_ERROR"
    VIDEO_DOWNLOAD_ERROR = "VIDEO_DOWNLOAD_ERROR"
    VIDEO_TOO_LONG = "VIDEO_TOO_LONG"
    VIDEO_REGION_BLOCKED = "VIDEO_REGION_BLOCKED"
    VIDEO_UNSUPPORTED_PLATFORM = "VIDEO_UNSUPPORTED_PLATFORM"

    # LLM 模块
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    LLM_ALL_FAILED = "LLM_ALL_FAILED"
    LLM_CONTENT_FILTERED = "LLM_CONTENT_FILTERED"

    # 支付模块
    PAYMENT_INVALID_PLAN = "PAYMENT_INVALID_PLAN"
    PAYMENT_WEBHOOK_INVALID = "PAYMENT_WEBHOOK_INVALID"
    PAYMENT_SESSION_EXPIRED = "PAYMENT_SESSION_EXPIRED"

    # 用户模块
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_QUOTA_EXCEEDED = "USER_QUOTA_EXCEEDED"
    USER_PLAN_EXPIRED = "USER_PLAN_EXPIRED"

    # 认证模块
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED"

    # 系统模块
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    VALIDATION_ERROR = "VALIDATION_ERROR"


# 错误码 → HTTP 状态码映射
ERROR_HTTP_STATUS = {
    ErrorCode.VIDEO_PARSE_ERROR: 400,
    ErrorCode.VIDEO_DOWNLOAD_ERROR: 400,
    ErrorCode.VIDEO_TOO_LONG: 400,
    ErrorCode.VIDEO_REGION_BLOCKED: 403,
    ErrorCode.VIDEO_UNSUPPORTED_PLATFORM: 400,
    ErrorCode.LLM_TIMEOUT: 504,
    ErrorCode.LLM_RATE_LIMIT: 429,
    ErrorCode.LLM_ALL_FAILED: 503,
    ErrorCode.LLM_CONTENT_FILTERED: 400,
    ErrorCode.PAYMENT_INVALID_PLAN: 400,
    ErrorCode.PAYMENT_WEBHOOK_INVALID: 400,
    ErrorCode.PAYMENT_SESSION_EXPIRED: 400,
    ErrorCode.USER_NOT_FOUND: 404,
    ErrorCode.USER_QUOTA_EXCEEDED: 429,
    ErrorCode.USER_PLAN_EXPIRED: 403,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_UNAUTHORIZED: 403,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.NETWORK_ERROR: 502,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.VALIDATION_ERROR: 422,
}


class AppError(Exception):
    """业务异常基类。"""

    def __init__(
        self,
        code: ErrorCode,
        detail: Optional[str] = None,
        http_status: Optional[int] = None,
    ):
        self.code = code
        self.detail = detail
        self.http_status = http_status or ERROR_HTTP_STATUS.get(code, 500)
        super().__init__(f"{code}: {detail}")
```

### 7.4 前后端错误码对齐

前端根据 `code` 字段做分支判断，`message` 字段可直接展示给用户（已翻译）。

```typescript
// 前端错误处理（Vue 3 composable）
export function useErrorHandler() {
  const handleApiError = (error: ApiError) => {
    switch (error.code) {
      case 'USER_QUOTA_EXCEEDED':
        router.push('/pricing')
        break
      case 'AUTH_TOKEN_EXPIRED':
        authStore.logout()
        break
      case 'VIDEO_PARSE_ERROR':
        toast.error(error.message)
        break
      default:
        toast.error(error.message)
    }
  }
  return { handleApiError }
}
```

---

## 8. 配置管理

### 8.1 pydantic-settings 配置类

```python
"""app/config.py — 环境变量与配置管理。"""

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置（从 .env 或环境变量加载）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 应用基础 =====
    APP_NAME: str = "Video Summary"
    APP_URL: str = "http://localhost:3000"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development / staging / production
    SECRET_KEY: str = Field(..., description="应用密钥（用于签名等）")

    # ===== 数据库 =====
    DB_TYPE: str = "sqlite"  # sqlite / postgres
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"
    # PostgreSQL 示例：postgresql+asyncpg://user:pass@host:5432/vsum

    # ===== CORS =====
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # ===== Supabase Auth =====
    SUPABASE_URL: str = Field(..., description="Supabase 项目 URL")
    SUPABASE_JWT_SECRET: str = Field(..., description="Supabase JWT 签名密钥")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(..., description="Supabase Service Role Key")

    # ===== OpenRouter =====
    OPENROUTER_API_KEY: str = Field(..., description="OpenRouter API Key")

    # ===== Stripe =====
    STRIPE_SECRET_KEY: str = Field(..., description="Stripe Secret Key (sk_*)")
    STRIPE_WEBHOOK_SECRET: str = Field(..., description="Stripe Webhook Secret (whsec_*)")
    STRIPE_PRICE_PRO_MONTHLY: str = Field(default="", description="Price ID for Pro Monthly")
    STRIPE_PRICE_PRO_YEARLY: str = Field(default="", description="Price ID for Pro Yearly")
    STRIPE_PRICE_PREMIUM_MONTHLY: str = Field(default="", description="Price ID for Premium Monthly")

    # ===== 下载限制 =====
    MAX_VIDEO_DURATION: int = 3600  # 最大视频时长（秒）
    MAX_FILE_SIZE_MB: int = 500
    DOWNLOAD_TIMEOUT: int = 300  # 下载超时（秒）

    # ===== 速率限制 =====
    RATE_LIMIT_FREE: int = 3  # 免费用户每日次数
    RATE_LIMIT_PRO: int = 50
    RATE_LIMIT_PREMIUM: int = 200
    RATE_LIMIT_WINDOW_SECONDS: int = 86400  # 24h

    # ===== 日志 =====
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json / console

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v.startswith(("sqlite", "postgresql")):
            raise ValueError("DATABASE_URL must start with sqlite or postgresql")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
```

### 8.2 环境变量清单

#### 必需（启动失败）

| 变量 | 说明 | 示例 |
|---|---|---|
| `SECRET_KEY` | 应用密钥 | `a1b2c3d4e5f6...` |
| `SUPABASE_URL` | Supabase 项目 URL | `https://xxxxx.supabase.co` |
| `SUPABASE_JWT_SECRET` | JWT 签名密钥 | `your-jwt-secret` |
| `OPENROUTER_API_KEY` | OpenRouter API Key | `sk-or-v1-xxx` |
| `STRIPE_SECRET_KEY` | Stripe Secret Key | `sk_test_xxx` |
| `STRIPE_WEBHOOK_SECRET` | Stripe Webhook Secret | `whsec_xxx` |

#### 可选（有默认值）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEBUG` | `false` | 调试模式 |
| `ENVIRONMENT` | `development` | 环境标识 |
| `DB_TYPE` | `sqlite` | 数据库类型 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` | 数据库连接串 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `MAX_VIDEO_DURATION` | `3600` | 最大视频时长（秒） |
| `RATE_LIMIT_FREE` | `3` | 免费用户日配额 |

### 8.3 .env.example

```env
# ===== 应用基础 =====
APP_NAME=Video Summary
APP_URL=http://localhost:3000
DEBUG=true
ENVIRONMENT=development
SECRET_KEY=change-me-in-production

# ===== 数据库（MVP 用 SQLite） =====
DB_TYPE=sqlite
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# ===== CORS =====
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ===== Supabase =====
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# ===== OpenRouter =====
OPENROUTER_API_KEY=sk-or-v1-xxx

# ===== Stripe =====
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_PRO_MONTHLY=price_xxx
STRIPE_PRICE_PRO_YEARLY=price_xxx
STRIPE_PRICE_PREMIUM_MONTHLY=price_xxx

# ===== 下载限制 =====
MAX_VIDEO_DURATION=3600
MAX_FILE_SIZE_MB=500

# ===== 速率限制 =====
RATE_LIMIT_FREE=3
RATE_LIMIT_PRO=50
RATE_LIMIT_PREMIUM=200

# ===== 日志 =====
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

---

## 9. 日志规范

### 9.1 使用 structlog 配置

```python
"""app/logger.py — 结构化日志配置。"""

import logging
import sys
import structlog


def setup_logging(log_level: str = "INFO", log_format: str = "json"):
    """配置 structlog。"""

    # 标准库日志也走 structlog 处理
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # 处理器链
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        # 敏感信息脱敏
        _mask_sensitive_data,
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _mask_sensitive_data(logger, method_name, event_dict):
    """脱敏处理器：隐藏 token、key、email 等。"""
    sensitive_keys = {
        "token", "api_key", "secret", "password",
        "authorization", "email", "credit_card",
    }
    for key in event_dict:
        if any(s in key.lower() for s in sensitive_keys):
            value = str(event_dict[key])
            if len(value) > 8:
                event_dict[key] = value[:4] + "****" + value[-4:]
            else:
                event_dict[key] = "****"
    return event_dict
```

### 9.2 请求/响应日志中间件

```python
"""app/middleware/logging.py — 请求/响应日志。"""

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logger import setup_logging
import structlog

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的耗时、状态码、用户 ID。"""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # 注入请求 ID 到上下文
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        # 处理请求
        response: Response = await call_next(request)

        # 计算耗时
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 记录日志
        log_level = "info" if response.status_code < 400 else "warning"
        getattr(logger, log_level)(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # 注入响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response
```

### 9.3 日志输出示例

```json
{
  "timestamp": "2026-06-25T10:30:45.123Z",
  "level": "info",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "method": "POST",
  "path": "/api/ai/summary/stream",
  "client_ip": "127.0.0.1",
  "status_code": 200,
  "duration_ms": 4523.67,
  "event": "request_completed"
}
```

### 9.4 敏感信息脱敏规则

| 字段 | 脱敏方式 | 示例 |
|---|---|---|
| `email` | 首字母 + `***` + 域名 | `u***@example.com` |
| `token` | 前 4 + `****` + 后 4 | `eyJ****xYz` |
| `api_key` | 前 4 + `****` + 后 4 | `sk-o****abcd` |
| `authorization` | 完全隐藏 | `****` |
| `credit_card` | 仅保留后 4 位 | `****1234` |

---

## 10. 国际化与本地化

### 10.1 错误消息翻译

```python
"""app/utils/i18n.py — 错误消息翻译中心。"""

from typing import Optional

TRANSLATIONS = {
    "VIDEO_PARSE_ERROR": {
        "en": "Unable to parse this video URL. Please check the link.",
        "zh": "无法解析该视频链接，请检查地址是否正确。",
        "ja": "この動画URLを解析できません。リンクをご確認ください。",
    },
    "VIDEO_TOO_LONG": {
        "en": "Video is too long. Maximum duration is {max_duration} minutes.",
        "zh": "视频过长，最长支持 {max_duration} 分钟。",
        "ja": "動画が長すぎます。最大{max_duration}分までです。",
    },
    "LLM_ALL_FAILED": {
        "en": "AI service is temporarily unavailable. Please retry in a moment.",
        "zh": "AI 服务暂时不可用，请稍后重试。",
        "ja": "AIサービスが一時的に利用できません。しばらくして再試行してください。",
    },
    "USER_QUOTA_EXCEEDED": {
        "en": "Daily limit reached. {upgrade_prompt}",
        "zh": "今日次数已用完。{upgrade_prompt}",
        "ja": "本日の上限に達しました。{upgrade_prompt}",
    },
}


def translate_error(
    code: str,
    locale: str = "en",
    detail: Optional[str] = None,
) -> str:
    """翻译错误码为本地化消息。"""
    messages = TRANSLATIONS.get(code)
    if not messages:
        return detail or code

    message = messages.get(locale, messages.get("en", code))

    # 简单模板替换
    if detail and "{max_duration}" in message:
        message = message.replace("{max_duration}", detail)
    if "{upgrade_prompt}" in message:
        upgrade_prompts = {
            "en": "Upgrade to Pro for unlimited access.",
            "zh": "升级 Pro 可无限使用。",
            "ja": "Pro にアップグレードして無制限をご利用ください。",
        }
        message = message.replace(
            "{upgrade_prompt}",
            upgrade_prompts.get(locale, upgrade_prompts["en"]),
        )

    return message
```

### 10.2 Prompt 内嵌语言指令

```python
"""app/services/locale_service.py — 语言相关 Prompt 构建。"""

from app.models.enums import Locale


class LocaleService:
    """语言与 Prompt 管理。"""

    PROMPT_TEMPLATES = {
        "zh": "prompts/zh.md",
        "en": "prompts/en.md",
        "ja": "prompts/ja.md",
    }

    def build_prompt(
        self,
        locale: str,
        video_info: dict,
        transcript: str,
    ) -> str:
        """构建带语言指令的 Prompt。"""
        template_path = self.PROMPT_TEMPLATES.get(
            locale, self.PROMPT_TEMPLATES["en"]
        )

        import importlib.resources
        with importlib.resources.files("app").joinpath(template_path).open("r", encoding="utf-8") as f:
            template = f.read()

        # 注入语言指令
        language_instructions = {
            "zh": "请用中文（简体）撰写总结。",
            "en": "Please write the summary in English.",
            "ja": "要約を日本語で書いてください。",
        }

        prompt = template.format(
            title=video_info.get("title", ""),
            duration=video_info.get("duration", 0),
            transcript=transcript,
            language_instruction=language_instructions.get(locale, ""),
        )

        return prompt
```

---

## 11. 安全与合规

### 11.1 核心安全原则

1. **不持久化视频文件**：下载到 `tempfile.TemporaryDirectory`，上下文退出自动清理
2. **API Key 不入库**：所有第三方密钥存环境变量，不写入数据库
3. **用户输入校验**：Pydantic 严格校验所有输入，URL 白名单域名
4. **速率限制**：按用户 + IP 双重限制，防止滥用
5. **CORS 白名单**：生产环境严格限制来源

### 11.2 速率限制实现

```python
"""app/middleware/rate_limit.py — 速率限制中间件。"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于内存的滑动窗口速率限制（MVP）。"""

    # 生产环境应改用 Redis
    _requests: dict = defaultdict(list)

    RATE_LIMITS = {
        "free": 3,
        "pro": 50,
        "premium": 200,
    }
    WINDOW_SECONDS = 86400  # 24h

    async def dispatch(self, request: Request, call_next):
        # 仅限制写操作
        if request.method in ("POST", "PUT", "DELETE"):
            user_id = self._get_user_id(request)
            plan = self._get_user_plan(request)
            limit = self.RATE_LIMITS.get(plan, 3)

            now = time.time()
            window_start = now - self.WINDOW_SECONDS

            # 清理过期记录
            self._requests[user_id] = [
                t for t in self._requests[user_id] if t > window_start
            ]

            if len(self._requests[user_id]) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded: {limit} requests per day",
                    },
                )

            self._requests[user_id].append(now)

        response = await call_next(request)
        return response

    def _get_user_id(self, request: Request) -> str:
        # 从 JWT 或 API Key 提取用户 ID
        return request.headers.get("X-User-Id", request.client.host)

    def _get_user_plan(self, request: Request) -> str:
        # 从 JWT claims 中提取 plan
        return request.headers.get("X-User-Plan", "free")
```

### 11.3 DMCA 合规

```python
"""app/services/dmca_service.py — DMCA 黑名单与合规。"""

from typing import Set


class DMCAService:
    """DMCA 合规：黑名单 + 侵权通知处理。"""

    # 黑名单（持久化到数据库）
    _blacklisted_domains: Set[str] = set()

    async def check_url(self, url: str) -> bool:
        """检查 URL 是否在黑名单中。"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        return domain in self._blacklisted_domains

    async def add_to_blacklist(self, domain: str, reason: str):
        """添加域名到黑名单。"""
        self._blacklisted_domains.add(domain)
        # 持久化到数据库（实现略）

    async def handle_takedown_notice(self, notice: dict):
        """处理 DMCA 下架通知。"""
        # 1. 验证通知格式
        # 2. 添加到黑名单
        # 3. 通知相关用户
        # 4. 记录审计日志
        pass
```

---

## 12. 部署与运维

### 12.1 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# 应用代码
COPY . .

# 非 root 用户
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

### 12.2 生产环境检查清单

- [ ] `DEBUG=false`
- [ ] `SECRET_KEY` 已更换为强随机值
- [ ] `DATABASE_URL` 指向 PostgreSQL
- [ ] CORS_ORIGINS 仅包含生产域名
- [ ] `LOG_FORMAT=json`
- [ ] Stripe 使用 `sk_live_*` 生产密钥
- [ ] Supabase JWT Secret 已配置
- [ ] 速率限制后端切换为 Redis
- [ ] HTTPS 强制
- [ ] 健康检查 `/health` 接入监控

---

## 13. 验证清单

### 13.1 功能验证

- [ ] `/api/video/parse` 能正确解析 YouTube/Bilibili/TikTok/抖音 URL
- [ ] `/api/ai/summary/stream` SSE 流正常，心跳 30s 间隔
- [ ] `/api/ai/summary/stream` 下载进度事件正确推送
- [ ] 视频文件在总结完成后自动删除
- [ ] 中文请求路由到 DeepSeek，英文到 Claude，日文到 GPT
- [ ] LLM 主模型失败时自动 fallback
- [ ] Stripe Checkout 创建会话成功
- [ ] Stripe Webhook 签名验证通过
- [ ] 免费用户超过 3 次/天返回 429
- [ ] 错误响应格式统一 `{code, message, detail}`

### 13.2 性能验证

- [ ] 健康检查 P99 < 50ms
- [ ] 视频解析 P99 < 2s
- [ ] SSE 首字节时间 < 1.5s
- [ ] 并发 100 用户下服务稳定
- [ ] 内存泄漏检测通过（长时间运行）

### 13.3 安全验证

- [ ] 无 API Key 硬编码在代码中
- [ ] 所有密钥通过环境变量注入
- [ ] SQL 注入测试通过（ORM 参数化）
- [ ] XSS 测试通过（响应头 `X-Content-Type-Options: nosniff`）
- [ ] CORS 跨域测试通过
- [ ] 速率限制生效
- [ ] 日志中无敏感信息明文

### 13.4 国际化验证

- [ ] 中文错误消息正确显示
- [ ] 日文错误消息正确显示
- [ ] 英文错误消息正确显示
- [ ] Prompt 语言指令与用户语言匹配
- [ ] SSE 消息中无乱码

### 13.5 合规验证

- [ ] DMCA 黑名单生效
- [ ] 视频文件不留存
- [ ] GDPR 数据处理协议（DPA）可导出
- [ ] 用户数据删除接口可用
- [ ] `.com` 域名 + 境外实体（PIPL 不面向中国用户）

---

## 附录 A：依赖清单

```toml
# pyproject.toml 核心依赖
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "gunicorn>=22.0.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "aiosqlite>=0.20.0",          # SQLite 异步驱动
    "asyncpg>=0.29.0",            # PostgreSQL 异步驱动
    "alembic>=1.13.0",            # 数据库迁移
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",              # 异步 HTTP 客户端
    "structlog>=24.0.0",          # 结构化日志
    "yt-dlp>=2024.0.0",           # 视频下载
    "stripe>=7.0.0",              # 支付
    "supabase>=2.0.0",           # Auth
    "python-multipart>=0.0.9",   # 文件上传
    "jinja2>=3.1.0",              # PDF 模板
    "weasyprint>=60.0",           # PDF 渲染
    "python-jose[cryptography]>=3.3.0",  # JWT 解析
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

## 附录 B：数据库 ER 图（简化）

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    users     │     │   summaries  │     │  usage_logs  │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id (PK)      │────<│ user_id (FK) │     │ user_id (FK) │
│ email        │     │ id (PK)      │     │ id (PK)      │
│ plan         │     │ video_url    │     │ model        │
│ locale       │     │ summary_text │     │ tokens_in    │
│ created_at   │     │ language     │     │ tokens_out   │
└──────────────┘     │ status       │     │ cost_usd     │
                     │ created_at   │     │ created_at   │
                     └──────────────┘     └──────────────┘

┌──────────────┐
│  blacklist   │    (DMCA 黑名单)
├──────────────┤
│ id (PK)      │
│ domain       │
│ reason       │
│ created_at   │
└──────────────┘
```

---

> 文档维护：架构组
> 最后更新：2026-06-25
> 下次评审：MVP 交付后（V1.1 迭代）
