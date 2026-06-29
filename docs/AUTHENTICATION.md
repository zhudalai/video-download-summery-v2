# 认证系统设计文档

| 属性 | 值 |
|---|---|
| 文档版本 | v1.0.0 |
| 发布日期 | 2026-06-25 |
| 作者 | 工程团队 |
| 状态 | 正式发布 |
| 适用产品 | Video Download Summary (Web SPA) |
| 适用环境 | Production |

---

## 目录

- [1. Supabase Auth 集成](#1-supabase-auth-集成)
- [2. JWT 校验中间件](#2-jwt-校验中间件)
- [3. 用户偏好存储](#3-用户偏好存储)
- [4. 用户注册流程](#4-用户注册流程)
- [5. 用户登录流程](#5-用户登录流程)
- [6. 用户账户删除 (GDPR Art. 17)](#6-用户账户删除-gdpr-art-17)
- [7. 用户数据导出 (GDPR Art. 20)](#7-用户数据导出-gdpr-art-20)
- [8. 角色与权限](#8-角色与权限)
- [9. 会话管理](#9-会话管理)
- [10. 安全最佳实践](#10-安全最佳实践)
- [11. 验证清单](#11-验证清单)

---

## 1. Supabase Auth 集成

### 1.1 概述

本项目使用 Supabase Auth（云端托管）作为身份认证服务，并通过抽象层封装底层实现，保证未来可迁移至其他认证提供商（如 Auth0、Firebase Auth、Keycloak 等）。所有认证操作（注册、登录、OAuth、密码重置）均通过 Supabase 客户端 SDK 完成，后端仅做 JWT 校验与业务数据关联。

### 1.2 架构图

```mermaid
flowchart LR
    Client[Vue 3 SPA] -->|HTTP 请求| API[FastAPI 后端]
    Client -->|sign_up / sign_in| Supabase[Supabase Auth]
    Supabase -->|返回 access_token + refresh_token| Client
    API -->|校验 JWT| Supabase
    Supabase -->|JWKS 公钥| API
    Supabase -->|user.created Webhook| Webhook[后端 /api/auth/webhook]
    Webhook -->|创建用户记录| DB[(PostgreSQL)]
    SMTP[Brevo 邮件] <--|发送欢迎/重置邮件| Supabase
```

### 1.3 项目配置

在 Supabase Dashboard 中配置以下项目参数：

| 配置项 | 说明 | 获取方式 |
|---|---|---|
| Project URL | Supabase 项目访问地址 | Dashboard > Settings > API > Project URL |
| anon public | 匿名公钥，前端使用 | Dashboard > Settings > API > Project API keys |
| service_role secret | 服务端密钥，仅后端使用 | Dashboard > Settings > API > Project API keys |
| JWT Secret | JWT 签名密钥（HS256） | Dashboard > Settings > API > JWT Settings |
| JWT 过期时间 | 默认 3600 秒（1 小时） | Dashboard > Settings > API > JWT Settings |

### 1.4 环境变量

#### 后端 `.env` 变量

| 变量名 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `SUPABASE_URL` | string | 是 | Supabase 项目 URL | `https://xyzcompany.supabase.co` |
| `SUPABASE_ANON_KEY` | string | 是 | Supabase anon public key | `eyJhbGciOiJIUzI1NiIs...` |
| `SUPABASE_SERVICE_ROLE_KEY` | string | 是 | Supabase service_role secret | `eyJhbGciOiJIUzI1NiIs...` |
| `SUPABASE_JWT_SECRET` | string | 是 | JWT 签名密钥 | `super-secret-jwt-token-with-at-least-32-characters-long` |
| `SUPABASE_JWKS_URL` | string | 否 | JWKS 公钥集 URL（RS256 时使用） | `https://xyzcompany.supabase.co/auth/v1/keys` |
| `BREVO_API_KEY` | string | 是 | Brevo 事务邮件 API 密钥 | `xkeysib-...` |
| `DATABASE_URL` | string | 是 | PostgreSQL 连接串 | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | string | 是 | Redis 连接串（权限缓存） | `redis://localhost:6379/0` |
| `STRIPE_SECRET_KEY` | string | 是 | Stripe 密钥 | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | string | 是 | Stripe Webhook 签名密钥 | `whsec_...` |
| `GDPR_DELETION_DAYS` | int | 是 | GDPR 删除响应天数 | `30` |
| `GDPR_EXPORT_DAYS` | int | 是 | GDPR 导出响应天数 | `45` |

#### 前端 `.env` 变量

| 变量名 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `VITE_SUPABASE_URL` | string | 是 | Supabase 项目 URL | `https://xyzcompany.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | string | 是 | Supabase anon public key | `eyJhbGciOiJIUzI1NiIs...` |
| `VITE_API_BASE_URL` | string | 是 | 后端 API 地址 | `https://api.example.com` |

### 1.5 第三方登录提供商配置

#### Email + Magic Link

在 Supabase Dashboard > Authentication > Providers 中启用 Email，并关闭 "Confirm email"（若使用 Magic Link 则开启）。

```python
# backend/config/supabase.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class SupabaseSettings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_JWKS_URL: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_supabase_settings() -> SupabaseSettings:
    return SupabaseSettings()
```

#### Google OAuth

1. 在 Google Cloud Console 创建 OAuth 2.0 客户端 ID（Web 应用类型）。
2. 配置授权重定向 URI：`https://xyzcompany.supabase.co/auth/v1/callback`。
3. 在 Supabase Dashboard > Authentication > Providers > Google 填入 Client ID 与 Client Secret。

#### Apple OAuth

1. 在 Apple Developer Portal 创建 Services ID 与 Private Key。
2. 配置回调 URL：`https://xyzcompany.supabase.co/auth/v1/callback`。
3. 在 Supabase Dashboard > Authentication > Providers > Apple 填入 Services ID、Private Key 与 Team ID。

### 1.6 自定义邮件模板（多语言）

Supabase 支持通过自定义 SMTP 发送邮件，并在模板中使用 Handlebars 语法。本项目使用 Brevo 作为事务邮件提供商，并通过后端 API 发送本地化邮件（而非 Supabase 内置模板），以获得完全的多语言控制。

#### 邮件类型

| 邮件类型 | 触发时机 | 语言来源 |
|---|---|---|
| welcome | 用户首次注册成功 | 用户偏好语言（默认 en） |
| password_reset | 请求重置密码 | 用户偏好语言 |
| email_change | 修改邮箱 | 用户偏好语言 |
| deletion_confirm | 账户删除完成 | 用户偏好语言 |
| export_ready | 数据导出完成 | 用户偏好语言 |

#### 邮件模板示例（中文）

```html
<!-- backend/templates/emails/welcome_zh.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>欢迎使用 Video Download Summary</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #f8f9fa; border-radius: 8px; padding: 32px; text-align: center;">
        <h1 style="color: #1a1a1a; font-size: 24px; margin-bottom: 16px;">欢迎加入 Video Download Summary</h1>
        <p style="color: #555; font-size: 16px; line-height: 1.6;">
            您好 {{username}}，<br><br>
            感谢您注册 Video Download Summary。我们很高兴为您提供视频摘要服务。
        </p>
        <div style="margin: 24px 0;">
            <a href="{{dashboard_url}}" style="background: #4f46e5; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">
                进入控制台
            </a>
        </div>
        <p style="color: #888; font-size: 14px; margin-top: 24px;">
            如果您未注册此账户，请忽略此邮件。<br>
            如有任何问题，请联系 support@example.com
        </p>
    </div>
</body>
</html>
```

#### 邮件模板示例（英文）

```html
<!-- backend/templates/emails/welcome_en.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Video Download Summary</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #f8f9fa; border-radius: 8px; padding: 32px; text-align: center;">
        <h1 style="color: #1a1a1a; font-size: 24px; margin-bottom: 16px;">Welcome to Video Download Summary</h1>
        <p style="color: #555; font-size: 16px; line-height: 1.6;">
            Hi {{username}},<br><br>
            Thank you for registering with Video Download Summary. We are excited to provide you with video summarization services.
        </p>
        <div style="margin: 24px 0;">
            <a href="{{dashboard_url}}" style="background: #4f46e5; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">
                Go to Dashboard
            </a>
        </div>
        <p style="color: #888; font-size: 14px; margin-top: 24px;">
            If you did not create this account, please ignore this email.<br>
            If you have any questions, contact support@example.com
        </p>
    </div>
</body>
</html>
```

#### 邮件发送服务

```python
# backend/services/email_service.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.config.supabase import get_supabase_settings

logger = logging.getLogger(__name__)

settings = get_supabase_settings()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


LANGUAGE_TEMPLATE_MAP: dict[str, dict[str, str]] = {
    "welcome": {
        "en": "welcome_en.html",
        "zh": "welcome_zh.html",
        "ja": "welcome_ja.html",
        "ko": "welcome_ko.html",
    },
    "password_reset": {
        "en": "password_reset_en.html",
        "zh": "password_reset_zh.html",
        "ja": "password_reset_ja.html",
        "ko": "password_reset_ko.html",
    },
    "email_change": {
        "en": "email_change_en.html",
        "zh": "email_change_zh.html",
        "ja": "email_change_ja.html",
        "ko": "email_change_ko.html",
    },
    "deletion_confirm": {
        "en": "deletion_confirm_en.html",
        "zh": "deletion_confirm_zh.html",
        "ja": "deletion_confirm_ja.html",
        "ko": "deletion_confirm_ko.html",
    },
    "export_ready": {
        "en": "export_ready_en.html",
        "zh": "export_ready_zh.html",
        "ja": "export_ready_ja.html",
        "ko": "export_ready_ko.html",
    },
}


class EmailService:
    """基于 Brevo API 的事务邮件发送服务。"""

    def __init__(self) -> None:
        self.api_key = settings.BREVO_API_KEY
        self.base_url = "https://api.brevo.com/v3"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def send_transactional_email(
        self,
        to_email: str,
        to_name: str,
        template_type: str,
        language: str,
        template_context: dict[str, Any],
    ) -> bool:
        """
        发送事务邮件。

        Args:
            to_email: 收件人邮箱
            to_name: 收件人姓名
            template_type: 邮件类型 (welcome, password_reset, ...)
            language: BCP-47 语言代码
            template_context: 模板变量字典

        Returns:
            是否发送成功
        """
        template_map = LANGUAGE_TEMPLATE_MAP.get(template_type)
        if template_map is None:
            logger.error("Unknown template type: %s", template_type)
            return False

        template_name = template_map.get(language, template_map.get("en", ""))
        if not template_name:
            logger.error(
                "No template found for type=%s language=%s",
                template_type,
                language,
            )
            return False

        template = jinja_env.get_template(template_name)
        html_content = template.render(**template_context)

        payload = {
            "sender": {
                "name": "Video Download Summary",
                "email": "noreply@example.com",
            },
            "to": [
                {"email": to_email, "name": to_name},
            ],
            "subject": self._get_subject(template_type, language),
            "htmlContent": html_content,
        }

        try:
            response = await self._client.post("/smtp/email", json=payload)
            response.raise_for_status()
            logger.info(
                "Email sent successfully: type=%s to=%s",
                template_type,
                to_email,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Brevo API error: status=%d body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            return False
        except httpx.RequestError as exc:
            logger.error("Brevo request failed: %s", exc)
            return False

    def _get_subject(self, template_type: str, language: str) -> str:
        """根据邮件类型和语言返回邮件主题。"""
        subjects = {
            ("welcome", "zh"): "欢迎使用 Video Download Summary",
            ("welcome", "en"): "Welcome to Video Download Summary",
            ("welcome", "ja"): "Video Download Summary へようこそ",
            ("welcome", "ko"): "Video Download Summary에 오신 것을 환영합니다",
            ("password_reset", "zh"): "重置您的密码",
            ("password_reset", "en"): "Reset your password",
            ("password_reset", "ja"): "パスワードのリセット",
            ("password_reset", "ko"): "비밀번호 재설정",
            ("email_change", "zh"): "邮箱地址变更确认",
            ("email_change", "en"): "Email address change confirmation",
            ("email_change", "ja"): "メールアドレス変更確認",
            ("email_change", "ko"): "이메일 주소 변경 확인",
            ("deletion_confirm", "zh"): "您的账户已被删除",
            ("deletion_confirm", "en"): "Your account has been deleted",
            ("deletion_confirm", "ja"): "アカウントが削除されました",
            ("deletion_confirm", "ko"): "계정이 삭제되었습니다",
            ("export_ready", "zh"): "您的数据导出已就绪",
            ("export_ready", "en"): "Your data export is ready",
            ("export_ready", "ja"): "データエクスポートの準備ができました",
            ("export_ready", "ko"): "데이터 내보내기 준비 완료",
        }
        return subjects.get((template_type, language), "Video Download Summary Notification")

    async def close(self) -> None:
        await self._client.aclose()


async def get_email_service() -> EmailService:
    """FastAPI 依赖注入工厂。"""
    service = EmailService()
    try:
        yield service
    finally:
        await service.close()
```

### 1.7 Supabase Auth Triggers

当 `auth.users` 表发生 `INSERT` 事件时，Supabase 触发器调用后端 Webhook，完成业务侧用户记录初始化。

#### 数据库触发器

```sql
-- supabase/migrations/00001_create_auth_triggers.sql

-- 创建扩展（若尚未创建）
CREATE EXTENSION IF NOT EXISTS "http";

-- 触发器函数：用户创建时调用后端 Webhook
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    webhook_url TEXT;
    webhook_secret TEXT;
    payload JSONB;
    response http_response;
BEGIN
    -- 从 Supabase 设置中读取 Webhook URL 和密钥
    -- 实际部署中这些值应通过 Supabase Secrets 管理
    webhook_url := 'https://api.example.com/api/auth/webhook/user-created';
    webhook_secret := current_setting('app.webhook_secret', true);

    -- 构造 Webhook 请求体
    payload := jsonb_build_object(
        'event', 'user.created',
        'user_id', NEW.id,
        'email', NEW.email,
        'created_at', NEW.created_at,
        'raw_user_meta_data', NEW.raw_user_meta_data
    );

    -- 发送 HTTP POST 请求
    SELECT * INTO response FROM http_post(
        webhook_url,
        payload::text,
        'application/json',
        concat('Bearer ', webhook_secret)
    );

    -- 记录日志
    RAISE NOTICE 'User created webhook sent: user_id=%, status=%', NEW.id, response.status;

    RETURN NEW;
END;
$$;

-- 绑定触发器到 auth.users 表
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();
```

#### Webhook 安全验证

```python
# backend/api/auth_webhook.py
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr

from backend.config.supabase import get_supabase_settings
from backend.database import get_async_session
from backend.models.user import User
from backend.models.user_preferences import UserPreferences
from backend.services.email_service import EmailService, get_email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/webhook", tags=["auth-webhook"])

settings = get_supabase_settings()


class UserCreatedPayload(BaseModel):
    event: str
    user_id: UUID
    email: EmailStr | None = None
    created_at: str
    raw_user_meta_data: dict[str, Any] = {}


def verify_webhook_signature(
    payload_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """验证 Webhook 请求签名。"""
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def get_webhook_signature(
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature"),
) -> str:
    """FastAPI 依赖：提取 Webhook 签名头。"""
    return x_webhook_signature


@router.post(
    "/user-created",
    status_code=status.HTTP_200_OK,
    summary="Supabase user.created Webhook",
)
async def handle_user_created(
    payload: UserCreatedPayload,
    signature: str = Depends(get_webhook_signature),
    session=Depends(get_async_session),
    email_service: EmailService = Depends(get_email_service),
) -> dict[str, str]:
    """
    处理 Supabase auth.users INSERT 触发器 Webhook。

    流程：
    1. 验证 Webhook 签名
    2. 检查事件类型
    3. 幂等性检查（用户是否已存在）
    4. 创建业务侧用户记录
    5. 创建默认用户偏好
    6. 发送欢迎邮件
    """
    logger.info("Received user.created webhook: user_id=%s", payload.user_id)

    # 幂等性检查
    existing_user = await session.get(User, payload.user_id)
    if existing_user is not None:
        logger.info("User already exists, skipping: user_id=%s", payload.user_id)
        return {"status": "skipped", "reason": "user_already_exists"}

    # 创建业务用户记录
    new_user = User(
        id=payload.user_id,
        email=payload.email,
        role="free",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(new_user)

    # 创建默认用户偏好
    default_preferences = UserPreferences(
        user_id=payload.user_id,
        language="en",
        currency="USD",
        timezone="UTC",
        updated_at=datetime.now(timezone.utc),
    )
    session.add(default_preferences)

    await session.commit()
    logger.info("User and preferences created: user_id=%s", payload.user_id)

    # 发送欢迎邮件
    if payload.email:
        await email_service.send_transactional_email(
            to_email=payload.email,
            to_name=payload.email.split("@")[0],
            template_type="welcome",
            language="en",
            template_context={
                "username": payload.email.split("@")[0],
                "dashboard_url": "https://app.example.com/dashboard",
            },
        )

    return {"status": "created", "user_id": str(payload.user_id)}
```

---

## 2. JWT 校验中间件

### 2.1 概述

后端使用 FastAPI 依赖注入机制实现 JWT 校验。所有需要认证的 API 端点通过 `Depends(get_current_user)` 获取当前用户信息。JWT 使用 HS256 算法（与 Supabase 默认配置一致），并通过 `python-jose` 库完成签名校验。

### 2.2 架构图

```mermaid
sequenceDiagram
    participant Client as Vue 3 SPA
    participant API as FastAPI Backend
    participant Supabase as Supabase Auth
    participant DB as PostgreSQL

    Client->>API: GET /api/me (Authorization: Bearer <access_token>)
    API->>API: 提取 Bearer Token
    API->>API: 校验 JWT 签名 (HS256 + JWT_SECRET)
    API->>API: 检查 Token 过期时间
    API->>API: 检查 Token 是否在黑名单中
    API->>DB: 查询用户信息
    DB-->>API: 返回用户数据
    API-->>Client: 200 OK + 用户信息

    Note over Client: Token 过期时
    API-->>Client: 401 Unauthorized + refresh_hint
    Client->>Supabase: POST /auth/v1/token (grant_type=refresh_token)
    Supabase-->>Client: 新 access_token + refresh_token
    Client->>API: 重试请求（新 Token）
```

### 2.3 JWT 配置

```python
# backend/config/jwt.py
from __future__ import annotations

from pydantic_settings import BaseSettings
from functools import lru_cache


class JWTSettings(BaseSettings):
    """JWT 校验相关配置。"""

    SUPABASE_JWT_SECRET: str
    SUPABASE_URL: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_jwt_settings() -> JWTSettings:
    return JWTSettings()
```

### 2.4 JWT 校验核心实现

```python
# backend/middleware/auth.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt, ExpiredSignatureError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.jwt import get_jwt_settings
from backend.database import get_async_session
from backend.models.user import User
from backend.models.token_blacklist import TokenBlacklist
from backend.redis import get_redis_client

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
jwt_settings = get_jwt_settings()


class TokenPayload(BaseModel):
    """JWT 载荷解析结果。"""

    sub: str  # 用户 ID (UUID)
    exp: int  # 过期时间戳
    iat: int  # 签发时间戳
    aud: str  # 受众
    iss: str  # 签发者
    email: str | None = None
    role: str | None = None
    session_id: str | None = None


class TokenExpiredError(Exception):
    """Token 过期异常。"""

    def __init__(self, expired_at: datetime) -> None:
        self.expired_at = expired_at
        super().__init__(f"Token expired at {expired_at.isoformat()}")


class TokenRevokedError(Exception):
    """Token 被撤销异常。"""

    def __init__(self, jti: str) -> None:
        self.jti = jti
        super().__init__(f"Token has been revoked: {jti}")


class InvalidTokenError(Exception):
    """Token 格式或签名无效异常。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid token: {reason}")


def decode_access_token(token: str) -> dict[str, Any]:
    """
    解码并校验 Supabase access_token。

    Args:
        token: JWT 字符串

    Returns:
        解码后的载荷字典

    Raises:
        TokenExpiredError: Token 已过期
        InvalidTokenError: Token 签名或格式无效
    """
    try:
        payload = jwt.decode(
            token,
            jwt_settings.SUPABASE_JWT_SECRET,
            algorithms=[jwt_settings.JWT_ALGORITHM],
            audience="authenticated",
            issuer=f"{jwt_settings.SUPABASE_URL}/auth/v1",
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
                "require_exp": True,
                "require_iat": True,
                "leeway": 30,  -- 允许 30 秒时钟偏移
            },
        )
        return payload
    except ExpiredSignatureError as exc:
        -- 尝试解码（不校验过期时间）以获取过期时间戳
        unverified = jwt.get_unverified_claims(token)
        exp_timestamp = unverified.get("exp", 0)
        expired_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        logger.warning(
            "Token expired: sub=%s expired_at=%s",
            unverified.get("sub"),
            expired_at.isoformat(),
        )
        raise TokenExpiredError(expired_at) from exc
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", str(exc))
        raise InvalidTokenError(str(exc)) from exc


async def is_token_revoked(jti: str, redis_client: Any) -> bool:
    """
    检查 Token 是否在黑名单中。

    Args:
        jti: JWT ID（唯一标识）
        redis_client: Redis 客户端

    Returns:
        True 表示已撤销
    """
    try:
        result = await redis_client.get(f"token:blacklist:{jti}")
        return result is not None
    except Exception as exc:
        logger.error("Redis lookup failed for jti=%s: %s", jti, exc)
        -- Redis 故障时降级为允许请求（fail-open）
        -- 生产环境应配置 Redis 高可用
        return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_async_session),
    redis_client: Any = Depends(get_redis_client),
) -> User:
    """
    FastAPI 依赖：获取当前认证用户。

    流程：
    1. 提取 Authorization 头中的 Bearer Token
    2. 解码并校验 JWT
    3. 检查 Token 是否在黑名单中
    4. 查询数据库获取用户信息
    5. 检查用户是否处于活跃状态

    Raises:
        HTTPException 401: Token 缺失、过期、无效或已撤销
        HTTPException 403: 用户被禁用
        HTTPException 404: 用户不存在
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authorization_required",
                "message": "Authorization header is required",
                "hint": "Include 'Authorization: Bearer <access_token>' header",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    -- 解码 JWT
    try:
        payload = decode_access_token(token)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_expired",
                "message": "Access token has expired",
                "expired_at": exc.expired_at.isoformat(),
                "hint": "Use refresh token to obtain a new access token",
                "refresh_url": "/api/auth/refresh",
            },
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token expired"',
                "X-Token-Expired": "true",
            },
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": exc.reason,
                "hint": "Request a new token from Supabase Auth",
            },
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token"',
            },
        )

    user_id = payload.get("sub")
    jti = payload.get("jti") or payload.get("ref")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Token payload missing 'sub' claim",
            },
        )

    -- 检查 Token 撤销状态
    if jti:
        revoked = await is_token_revoked(jti, redis_client)
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "token_revoked",
                    "message": "This token has been revoked",
                    "hint": "Please login again",
                },
                headers={
                    "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token revoked"',
                },
            )

    -- 查询用户
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Invalid user ID format in token",
            },
        )

    user = await session.get(User, user_uuid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "User associated with this token no longer exists",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "user_inactive",
                "message": "User account has been deactivated",
            },
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_async_session),
    redis_client: Any = Depends(get_redis_client),
) -> User | None:
    """
    可选认证依赖：未登录返回 None，已登录返回用户。
    用于部分端点需要区分登录/未登录状态的场景。
    """
    try:
        return await get_current_user(credentials, session, redis_client)
    except HTTPException:
        return None
```

### 2.5 Token 刷新端点

```python
# backend/api/auth.py
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.config.supabase import get_supabase_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

settings = get_supabase_settings()


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="刷新 Access Token",
)
async def refresh_access_token(
    request: RefreshTokenRequest,
) -> TokenResponse:
    """
    使用 refresh_token 换取新的 access_token。

    流程：
    1. 调用 Supabase Auth API 的 token 刷新端点
    2. 返回新的 token 对
    """
    supabase_token_url = f"{settings.SUPABASE_URL}/auth/v1/token"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                supabase_token_url,
                params={
                    "grant_type": "refresh_token",
                },
                headers={
                    "apikey": settings.SUPABASE_ANON_KEY,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "refresh_token": request.refresh_token,
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Token refresh failed: status=%d body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "invalid_refresh_token",
                    "message": "Refresh token is invalid or expired",
                    "hint": "Please login again",
                },
            )
        except httpx.RequestError as exc:
            logger.error("Supabase token refresh request failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "auth_service_unavailable",
                    "message": "Unable to reach authentication service",
                },
            )

    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data.get("expires_in", 3600),
        user_id=data["user"]["id"],
    )
```

### 2.6 Token 撤销逻辑

```python
# backend/services/token_service.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.token_blacklist import TokenBlacklist

logger = logging.getLogger(__name__)


class TokenService:
    """Token 撤销与黑名单管理服务。"""

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    async def revoke_token(
        self,
        jti: str,
        user_id: UUID,
        token_type: str,
        expires_at: datetime,
        reason: str,
        session: AsyncSession,
    ) -> None:
        """
        撤销指定 Token。

        Args:
            jti: Token 唯一标识
            user_id: 所属用户 ID
            token_type: token 类型 (access / refresh)
            expires_at: Token 原始过期时间
            reason: 撤销原因 (logout / password_change / account_deletion)
            session: 数据库会话
        """
        -- 计算 TTL（秒），确保不超过 Token 原始过期时间
        now = datetime.now(timezone.utc)
        ttl_seconds = max(0, int((expires_at - now).total_seconds()))

        -- 写入 Redis 黑名单
        try:
            await self.redis.setex(
                f"token:blacklist:{jti}",
                ttl_seconds,
                reason,
            )
            logger.info(
                "Token revoked in Redis: jti=%s user_id=%s ttl=%ds reason=%s",
                jti,
                user_id,
                ttl_seconds,
                reason,
            )
        except Exception as exc:
            logger.error("Failed to revoke token in Redis: %s", exc)

        -- 持久化到数据库（用于审计）
        blacklist_entry = TokenBlacklist(
            jti=jti,
            user_id=user_id,
            token_type=token_type,
            reason=reason,
            expires_at=expires_at,
            created_at=now,
        )
        session.add(blacklist_entry)
        await session.commit()

    async def revoke_all_user_tokens(
        self,
        user_id: UUID,
        reason: str,
        session: AsyncSession,
    ) -> int:
        """
        撤销用户所有活跃 Token（用于账户删除、密码修改等场景）。

        实现方式：在 Redis 中记录用户的 token 签发时间阈值，
        所有早于此时间的 Token 视为已撤销。

        Returns:
            撤销的 Token 数量
        """
        revocation_threshold = datetime.now(timezone.utc)

        try:
            await self.redis.set(
                f"user:token_threshold:{user_id}",
                revocation_threshold.isoformat(),
                ex=60 * 60 * 24 * 35,  -- 保留 35 天（略长于最长 refresh_token 有效期）
            )
            logger.info(
                "All tokens revoked for user: user_id=%s reason=%s",
                user_id,
                reason,
            )
        except Exception as exc:
            logger.error("Failed to set token threshold in Redis: %s", exc)

        return 1

    async def is_token_revoked_by_threshold(
        self,
        user_id: UUID,
        token_issued_at: datetime,
    ) -> bool:
        """检查 Token 是否在用户全局撤销阈值之前签发。"""
        try:
            threshold_str = await self.redis.get(
                f"user:token_threshold:{user_id}"
            )
            if threshold_str is None:
                return False
            threshold = datetime.fromisoformat(threshold_str.decode("utf-8"))
            return token_issued_at < threshold
        except Exception:
            return False
```

---

## 3. 用户偏好存储

### 3.1 概述

用户偏好（语言、货币、时区）存储在业务数据库的 `user_preferences` 表中，与 Supabase `auth.users` 形成 1:1 关系。该设计将认证数据与业务数据解耦，便于独立扩展与维护。

### 3.2 架构图

```mermaid
erDiagram
    auth.users ||--|| public.user_preferences : "1:1 (user_id = id)"
    auth.users {
        uuid id PK
        string email
        string encrypted_password
        timestamptz created_at
        jsonb raw_user_meta_data
    }
    public.user_preferences {
        uuid user_id PK,FK
        string language "BCP-47 语言代码"
        string currency "ISO 4217 货币代码"
        string timezone "IANA 时区"
        timestamptz updated_at
    }
```

### 3.3 数据库表定义

```sql
-- migrations/0002_create_user_preferences.sql

CREATE TABLE IF NOT EXISTS public.user_preferences (
    -- 主键 + 外键：与 auth.users 形成 1:1 关系
    user_id UUID NOT NULL PRIMARY KEY,

    -- 语言偏好 (BCP-47 标准)
    -- 支持: en, zh, ja, ko, es, fr, de, pt, it, ru, ar, hi
    language VARCHAR(10) NOT NULL DEFAULT 'en'
        CHECK (language ~ '^[a-z]{2}(-[A-Z]{2})?$'),

    -- 货币偏好 (ISO 4217 标准)
    -- 支持: USD, EUR, GBP, JPY, CNY, KRW, HKD, TWD, SGD
    currency VARCHAR(3) NOT NULL DEFAULT 'USD'
        CHECK (currency ~ '^[A-Z]{3}$'),

    -- 时区偏好 (IANA 时区数据库)
    -- 例如: America/New_York, Europe/London, Asia/Shanghai, Asia/Tokyo
    timezone VARCHAR(100) NOT NULL DEFAULT 'UTC',

    -- 更新时间
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 外键约束（级联删除：当 auth.users 记录删除时自动删除偏好）
    CONSTRAINT fk_user_preferences_user
        FOREIGN KEY (user_id)
        REFERENCES auth.users (id)
        ON DELETE CASCADE
);

-- 索引（虽然主键已有索引，但为 updated_at 添加索引以支持按时间查询）
CREATE INDEX IF NOT EXISTS idx_user_preferences_updated_at
    ON public.user_preferences (updated_at);

-- 注释
COMMENT ON TABLE public.user_preferences IS '用户偏好设置 - 与 auth.users 1:1 关联';
COMMENT ON COLUMN public.user_preferences.language IS 'BCP-47 语言代码，如 zh, en, ja';
COMMENT ON COLUMN public.user_preferences.currency IS 'ISO 4217 货币代码，如 USD, CNY';
COMMENT ON COLUMN public.user_preferences.timezone IS 'IANA 时区标识符，如 Asia/Shanghai';
```

### 3.4 ORM 模型

```python
# backend/models/user_preferences.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class UserPreferences(Base):
    """用户偏好模型。"""

    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint(
            "language ~ '^[a-z]{2}(-[A-Z]{2})?$'",
            name="ck_user_preferences_language",
        ),
        CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_user_preferences_currency",
        ),
        CheckConstraint(
            "timezone ~ '^[A-Za-z_]+/[A-Za-z_]+$' OR timezone = 'UTC'",
            name="ck_user_preferences_timezone",
        ),
        {"schema": "public"},
    )

    -- 主键 + 外键
    user_id: Mapped[UUID] = mapped_column(
        String(36),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    -- 偏好字段
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="BCP-47 语言代码",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 货币代码",
    )
    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="UTC",
        comment="IANA 时区标识符",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        comment="最后更新时间",
    )

    -- 关系
    user = relationship("User", back_populates="preferences", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<UserPreferences(user_id={self.user_id}, "
            f"language={self.language}, currency={self.currency}, "
            f"timezone={self.timezone})>"
        )
```

### 3.5 用户偏好 API

```python
# backend/api/preferences.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_async_session
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.user_preferences import UserPreferences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me/preferences", tags=["preferences"])

-- 支持的语言列表
SUPPORTED_LANGUAGES = ["en", "zh", "ja", "ko", "es", "fr", "de", "pt", "it", "ru"]
SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CNY", "KRW", "HKD", "TWD", "SGD"]
SUPPORTED_TIMEZONES = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Moscow",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Asia/Singapore",
    "Asia/Hong_Kong",
    "Asia/Taipei",
    "Australia/Sydney",
    "Pacific/Auckland",
]


class PreferencesUpdateRequest(BaseModel):
    """用户偏好更新请求。"""

    language: Annotated[
        str | None,
        Field(min_length=2, max_length=10, description="BCP-47 语言代码"),
    ] = None
    currency: Annotated[
        str | None,
        Field(min_length=3, max_length=3, description="ISO 4217 货币代码"),
    ] = None
    timezone: Annotated[
        str | None,
        Field(max_length=100, description="IANA 时区标识符"),
    ] = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {v}. Supported: {SUPPORTED_LANGUAGES}"
            )
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Unsupported currency: {v}. Supported: {SUPPORTED_CURRENCIES}"
            )
        return v.upper()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUPPORTED_TIMEZONES:
            raise ValueError(
                f"Unsupported timezone: {v}. Please use a valid IANA timezone."
            )
        return v


class PreferencesResponse(BaseModel):
    """用户偏好响应。"""

    user_id: UUID
    language: str
    currency: str
    timezone: str
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get(
    "",
    response_model=PreferencesResponse,
    summary="获取当前用户偏好",
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PreferencesResponse:
    """
    获取当前用户的偏好设置。

    如果用户偏好不存在（首次请求），自动创建默认偏好并返回。
    """
    result = await session.execute(
        select(UserPreferences).where(
            UserPreferences.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()

    if preferences is None:
        -- 自动创建默认偏好（upsert 语义）
        preferences = UserPreferences(
            user_id=current_user.id,
            language="en",
            currency="USD",
            timezone="UTC",
            updated_at=datetime.now(timezone.utc),
        )
        session.add(preferences)
        await session.commit()
        await session.refresh(preferences)
        logger.info(
            "Auto-created default preferences for user: %s",
            current_user.id,
        )

    return PreferencesResponse(
        user_id=preferences.user_id,
        language=preferences.language,
        currency=preferences.currency,
        timezone=preferences.timezone,
        updated_at=preferences.updated_at,
    )


@router.put(
    "",
    response_model=PreferencesResponse,
    summary="更新当前用户偏好",
)
async def update_preferences(
    request: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PreferencesResponse:
    """
    更新当前用户的偏好设置。

    使用 upsert 语义：存在则更新，不存在则创建。
    仅更新请求中提供的字段，未提供的字段保持不变。
    """
    result = await session.execute(
        select(UserPreferences).where(
            UserPreferences.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()

    if preferences is None:
        -- 创建新偏好
        preferences = UserPreferences(
            user_id=current_user.id,
            language=request.language or "en",
            currency=request.currency or "USD",
            timezone=request.timezone or "UTC",
            updated_at=datetime.now(timezone.utc),
        )
        session.add(preferences)
    else:
        -- 部分更新
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(preferences, field, value)
        preferences.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(preferences)
    logger.info("Preferences updated for user: %s", current_user.id)

    return PreferencesResponse(
        user_id=preferences.user_id,
        language=preferences.language,
        currency=preferences.currency,
        timezone=preferences.timezone,
        updated_at=preferences.updated_at,
    )
```

### 3.6 前端偏好 Composable

```typescript
// frontend/src/composables/usePreferences.ts
import { ref, computed, onMounted } from 'vue';
import { useSupabaseClient } from '@supabase/supabase-js';
import type { UserPreferences } from '@/types';

const DEFAULT_PREFERENCES: UserPreferences = {
  user_id: '',
  language: 'en',
  currency: 'USD',
  timezone: 'UTC',
  updated_at: '',
};

export function usePreferences() {
  const supabase = useSupabaseClient();
  const preferences = ref<UserPreferences>(DEFAULT_PREFERENCES);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const language = computed(() => preferences.value.language);
  const currency = computed(() => preferences.value.currency);
  const timezone = computed(() => preferences.value.timezone);

  async function fetchPreferences(): Promise<void> {
    loading.value = true;
    error.value = null;

    try {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) {
        throw new Error('User not authenticated');
      }

      const { data, error: fetchError } = await supabase
        .from('user_preferences')
        .select('*')
        .eq('user_id', user.id)
        .single();

      if (fetchError && fetchError.code !== 'PGRST116') {
        throw fetchError;
      }

      if (data) {
        preferences.value = data;
      } else {
        // 首次使用，创建默认偏好
        const { data: created, error: createError } = await supabase
          .from('user_preferences')
          .upsert({
            user_id: user.id,
            language: 'en',
            currency: 'USD',
            timezone: 'UTC',
          })
          .select()
          .single();

        if (createError) throw createError;
        preferences.value = created;
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch preferences';
      console.error('Fetch preferences error:', e);
    } finally {
      loading.value = false;
    }
  }

  async function updatePreferences(
    updates: Partial<Pick<UserPreferences, 'language' | 'currency' | 'timezone'>>
  ): Promise<boolean> {
    loading.value = true;
    error.value = null;

    try {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) {
        throw new Error('User not authenticated');
      }

      const { data, error: updateError } = await supabase
        .from('user_preferences')
        .upsert({
          user_id: user.id,
          ...updates,
          updated_at: new Date().toISOString(),
        })
        .select()
        .single();

      if (updateError) throw updateError;
      preferences.value = data;
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update preferences';
      console.error('Update preferences error:', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    fetchPreferences();
  });

  return {
    preferences,
    language,
    currency,
    timezone,
    loading,
    error,
    fetchPreferences,
    updatePreferences,
  };
}
```

---

## 4. 用户注册流程

### 4.1 概述

用户注册流程涉及前端 Supabase 客户端调用、后端 Webhook 处理、默认角色分配与欢迎邮件发送。整个流程设计为幂等操作，确保网络重试不会产生重复用户。

### 4.2 流程图

```mermaid
sequenceDiagram
    participant Client as Vue 3 SPA
    participant Supabase as Supabase Auth
    participant Webhook as 后端 Webhook
    participant DB as PostgreSQL
    participant Email as Brevo 邮件

    Client->>Supabase: sign_up(email, password, options)
    Supabase->>Supabase: 校验密码策略
    Supabase->>Supabase: 创建 auth.users 记录
    Supabase->>Supabase: 触发 user.created 触发器
    Supabase-->>Client: 200 OK + user + session

    Supabase->>Webhook: POST /api/auth/webhook/user-created
    Webhook->>Webhook: 验证 Webhook 签名
    Webhook->>DB: INSERT INTO users (role='free')
    Webhook->>DB: INSERT INTO user_preferences (defaults)
    Webhook->>Email: 发送欢迎邮件
    Email-->>Client: 欢迎邮件已发送

    Webhook-->>Supabase: 200 OK
    Supabase-->>Client: 注册完成
```

### 4.3 前端注册实现

```typescript
// frontend/src/composables/useAuth.ts
import { ref, computed } from 'vue';
import { useSupabaseClient } from '@supabase/supabase-js';
import { useRouter } from 'vue-router';
import type { AuthError, User, Session, Provider } from '@supabase/supabase-js';

export interface SignUpCredentials {
  email: string;
  password: string;
  language?: string;
  timezone?: string;
}

export interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
  error: string | null;
}

export function useAuth() {
  const supabase = useSupabaseClient();
  const router = useRouter();

  const user = ref<User | null>(null);
  const session = ref<Session | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => !!user.value);
  const userRole = computed(() => user.value?.user_metadata?.role ?? 'free');

  /**
   * 邮箱 + 密码注册
   */
  async function signUpWithEmail(credentials: SignUpCredentials): Promise<boolean> {
    loading.value = true;
    error.value = null;

    try {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email: credentials.email,
        password: credentials.password,
        options: {
          data: {
            language: credentials.language || 'en',
            timezone: credentials.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
          },
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });

      if (signUpError) {
        handleAuthError(signUpError);
        return false;
      }

      if (data.user) {
        user.value = data.user;
        session.value = data.session;

        // 显示邮箱确认提示
        if (!data.session) {
          // 需要邮箱验证
          router.push('/auth/verify-email');
        } else {
          router.push('/dashboard');
        }
        return true;
      }

      return false;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Sign up failed';
      console.error('Sign up error:', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  /**
   * OAuth 注册/登录（Google / Apple）
   */
  async function signInWithOAuth(provider: Provider): Promise<boolean> {
    loading.value = true;
    error.value = null;

    try {
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });

      if (oauthError) {
        handleAuthError(oauthError);
        return false;
      }

      // OAuth 重定向后会自动返回
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'OAuth sign in failed';
      console.error('OAuth error:', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 邮箱 + 密码登录
   */
  async function signInWithPassword(email: string, password: string): Promise<boolean> {
    loading.value = true;
    error.value = null;

    try {
      const { data, error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        handleAuthError(signInError);
        return false;
      }

      user.value = data.user;
      session.value = data.session;
      router.push('/dashboard');
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Sign in failed';
      console.error('Sign in error:', e);
      return false;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 登出
   */
  async function signOut(): Promise<void> {
    loading.value = true;
    try {
      const { error: signOutError } = await supabase.auth.signOut();
      if (signOutError) throw signOutError;
      user.value = null;
      session.value = null;
      router.push('/auth/login');
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Sign out failed';
      console.error('Sign out error:', e);
    } finally {
      loading.value = false;
    }
  }

  /**
   * 处理认证回调（OAuth / Magic Link）
   */
  async function handleAuthCallback(): Promise<boolean> {
    loading.value = true;
    try {
      const { data, error: sessionError } = await supabase.auth.getSession();
      if (sessionError) throw sessionError;

      if (data.session) {
        user.value = data.session.user;
        session.value = data.session;
        return true;
      }
      return false;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Auth callback failed';
      return false;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 错误处理与本地化
   */
  function handleAuthError(authError: AuthError): void {
    const errorMap: Record<string, string> = {
      'User already registered': '该邮箱已被注册',
      'Invalid login credentials': '邮箱或密码错误',
      'Email not confirmed': '请先验证您的邮箱地址',
      'Password should be at least 6 characters': '密码长度至少为 6 个字符',
      'Signup is disabled': '注册功能当前已关闭',
      'Too many requests': '请求过于频繁，请稍后重试',
    };

    const localized = errorMap[authError.message];
    error.value = localized || authError.message || '认证失败，请重试';
  }

  /**
   * 初始化：获取当前会话
   */
  async function initialize(): Promise<void> {
    loading.value = true;
    try {
      const { data, error: sessionError } = await supabase.auth.getSession();
      if (sessionError) throw sessionError;

      user.value = data.session?.user ?? null;
      session.value = data.session ?? null;

      // 监听认证状态变化
      supabase.auth.onAuthStateChange((event, newSession) => {
        user.value = newSession?.user ?? null;
        session.value = newSession ?? null;
      });
    } catch (e) {
      console.error('Auth initialization error:', e);
    } finally {
      loading.value = false;
    }
  }

  return {
    user,
    session,
    loading,
    error,
    isAuthenticated,
    userRole,
    signUpWithEmail,
    signInWithPassword,
    signInWithOAuth,
    signOut,
    handleAuthCallback,
    initialize,
  };
}
```

### 4.4 后端用户记录创建

后端通过 Supabase Webhook 自动创建业务侧用户记录。若 Webhook 失败（网络异常、服务宕机等），则通过首次 API 请求时自动创建（lazy creation），确保数据最终一致性。

```python
# backend/services/user_service.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User
from backend.models.user_preferences import UserPreferences

logger = logging.getLogger(__name__)


class UserService:
    """用户业务记录管理服务。"""

    async def get_or_create_user(
        self,
        user_id: UUID,
        email: str | None,
        session: AsyncSession,
    ) -> User:
        """
        获取用户记录，不存在则创建。

        此方法用于 Webhook 失败时的兜底策略。
        当用户首次调用受保护的 API 时，若业务记录不存在，自动创建。

        Args:
            user_id: Supabase auth.users.id
            email: 用户邮箱
            session: 数据库会话

        Returns:
            User ORM 实例
        """
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user is not None:
            return user

        # 创建新用户
        user = User(
            id=user_id,
            email=email,
            role="free",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(user)

        # 创建默认偏好
        preferences = UserPreferences(
            user_id=user_id,
            language="en",
            currency="USD",
            timezone="UTC",
            updated_at=datetime.now(timezone.utc),
        )
        session.add(preferences)

        await session.commit()
        await session.refresh(user)
        logger.info("Lazy-created user and preferences: user_id=%s", user_id)
        return user

    async def get_user_by_id(
        self,
        user_id: UUID,
        session: AsyncSession,
    ) -> User | None:
        """根据 ID 查询用户。"""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_user_role(
        self,
        user_id: UUID,
        new_role: str,
        session: AsyncSession,
    ) -> User | None:
        """
        更新用户角色（通常由 Stripe Webhook 调用）。

        Args:
            user_id: 用户 ID
            new_role: 新角色 (free / pro / premium)
            session: 数据库会话

        Returns:
            更新后的用户实例，或 None（用户不存在）
        """
        valid_roles = {"free", "pro", "premium"}
        if new_role not in valid_roles:
            raise ValueError(f"Invalid role: {new_role}. Must be one of {valid_roles}")

        user = await session.get(User, user_id)
        if user is None:
            logger.warning("User not found for role update: %s", user_id)
            return None

        old_role = user.role
        user.role = new_role
        user.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(user)

        logger.info(
            "User role updated: user_id=%s old_role=%s new_role=%s",
            user_id,
            old_role,
            new_role,
        )
        return user
```

### 4.5 默认角色说明

| 角色 | 标识 | 每日限额 | 功能范围 |
|---|---|---|---|
| Free | `free` | 3 次摘要/天 | 基础视频摘要 |
| Pro | `pro` | 无限 | 摘要 + 思维导图 + SRT 导出 |
| Premium | `premium` | 无限 | Pro 全部功能 + 团队协作 + API 访问 |

---

## 5. 用户登录流程

### 5.1 概述

用户登录流程支持多种认证方式：邮箱密码、OAuth（Google / Apple）、Magic Link。前端通过 Supabase SDK 完成认证，后端通过 JWT 校验识别用户身份并返回完整的用户信息（含偏好与订阅状态）。

### 5.2 流程图

```mermaid
sequenceDiagram
    participant Client as Vue 3 SPA
    participant Supabase as Supabase Auth
    participant API as FastAPI Backend
    participant DB as PostgreSQL
    participant Stripe as Stripe API

    Note over Client: 方式 A: 邮箱密码登录
    Client->>Supabase: sign_in_with_password(email, password)
    Supabase-->>Client: access_token + refresh_token + user

    Note over Client: 方式 B: OAuth 登录
    Client->>Supabase: sign_in_with_oauth(google)
    Supabase-->>Client: 重定向到 Google
    Google-->>Supabase: 授权确认
    Supabase-->>Client: access_token + refresh_token

    Note over Client: 登录后获取完整信息
    Client->>API: GET /api/me (Bearer token)
    API->>API: 校验 JWT
    API->>DB: 查询用户 + 偏好
    API->>Stripe: 查询订阅状态
    Stripe-->>API: subscription_details
    API-->>Client: 用户信息 + 偏好 + 订阅状态
```

### 5.3 前端登录实现

前端登录逻辑已在 `useAuth()` composable 中实现（见第 4.3 节）。本节补充 OAuth 登录后的信息获取流程。

```typescript
// frontend/src/composables/useUser.ts
import { ref, computed } from 'vue';
import { useSupabaseClient } from '@supabase/supabase-js';
import type { User } from '@supabase/supabase-js';

export interface UserProfile {
  id: string;
  email: string;
  role: 'free' | 'pro' | 'premium';
  is_active: boolean;
  created_at: string;
  preferences: {
    language: string;
    currency: string;
    timezone: string;
  };
  subscription: {
    status: 'active' | 'canceled' | 'past_due' | 'unpaid' | 'trialing' | 'none';
    plan: 'free' | 'pro' | 'premium';
    current_period_end: string | null;
    cancel_at_period_end: boolean;
  };
}

export function useUser() {
  const supabase = useSupabaseClient();
  const user = ref<User | null>(null);
  const profile = ref<UserProfile | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => !!user.value);
  const userRole = computed(() => profile.value?.role ?? 'free');
  const subscriptionStatus = computed(() => profile.value?.subscription?.status ?? 'none');
  const isPro = computed(() => userRole.value === 'pro' || userRole.value === 'premium');
  const isPremium = computed(() => userRole.value === 'premium');

  /**
   * 获取完整用户信息（含偏好与订阅）
   */
  async function fetchUserProfile(): Promise<void> {
    loading.value = true;
    error.value = null;

    try {
      const {
        data: { user: authUser },
        error: authError,
      } = await supabase.auth.getUser();

      if (authError) throw authError;
      if (!authUser) {
        user.value = null;
        profile.value = null;
        return;
      }

      user.value = authUser;

      // 调用后端 API 获取完整信息
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) throw new Error('No active session');

      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/me`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.message || 'Failed to fetch profile');
      }

      profile.value = await response.json();
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch user profile';
      console.error('Fetch user profile error:', e);
    } finally {
      loading.value = false;
    }
  }

  /**
   * 登出并清除本地状态
   */
  async function signOut(): Promise<void> {
    const { error: signOutError } = await supabase.auth.signOut();
    if (signOutError) throw signOutError;
    user.value = null;
    profile.value = null;
  }

  /**
   * 刷新 Token
   */
  async function refreshSession(): Promise<boolean> {
    try {
      const { data, error: refreshError } = await supabase.auth.refreshSession();
      if (refreshError) throw refreshError;

      if (data.session) {
        user.value = data.user;
        return true;
      }
      return false;
    } catch (e) {
      console.error('Session refresh error:', e);
      return false;
    }
  }

  return {
    user,
    profile,
    loading,
    error,
    isAuthenticated,
    userRole,
    subscriptionStatus,
    isPro,
    isPremium,
    fetchUserProfile,
    signOut,
    refreshSession,
  };
}
```

### 5.4 后端 `/api/me` 端点

```python
# backend/api/me.py
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_async_session
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.user_preferences import UserPreferences
from backend.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["me"])


class SubscriptionInfo(BaseModel):
    """订阅信息响应。"""

    status: str  # active / canceled / past_due / unpaid / trialing / none
    plan: str  # free / pro / premium
    current_period_end: str | None = None
    cancel_at_period_end: bool = False


class UserProfileResponse(BaseModel):
    """完整用户信息响应。"""

    id: str
    email: str | None
    role: str
    is_active: bool
    created_at: str
    preferences: dict[str, Any]
    subscription: SubscriptionInfo

    class Config:
        from_attributes = True


@router.get(
    "",
    response_model=UserProfileResponse,
    summary="获取当前用户完整信息",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserProfileResponse:
    """
    获取当前用户的完整信息，包括：
    - 基本信息（ID、邮箱、角色、状态）
    - 偏好设置（语言、货币、时区）
    - 订阅状态（来自 Stripe）

    此端点通常在用户登录后首次调用，用于初始化前端状态。
    """
    # 查询用户偏好
    result = await session.execute(
        select(UserPreferences).where(
            UserPreferences.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()

    # 获取订阅信息
    subscription_service = SubscriptionService(session)
    subscription_info = await subscription_service.get_subscription_status(
        current_user.id
    )

    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
        preferences={
            "language": preferences.language if preferences else "en",
            "currency": preferences.currency if preferences else "USD",
            "timezone": preferences.timezone if preferences else "UTC",
        },
        subscription=SubscriptionInfo(
            status=subscription_info["status"],
            plan=subscription_info["plan"],
            current_period_end=subscription_info.get("current_period_end"),
            cancel_at_period_end=subscription_info.get("cancel_at_period_end", False),
        ),
    )
```

---

## 6. 用户账户删除 (GDPR Art. 17)

### 6.1 概述

根据 GDPR 第 17 条（被遗忘权），用户有权要求删除其个人数据。本系统设计为 30 天内完成删除请求处理。删除操作需协调多个子系统：Supabase Auth、业务数据库、Stripe（保留收据 7 年）、AI 摘要缓存、以及第三方服务。

### 6.2 流程图

```mermaid
sequenceDiagram
    participant Client as Vue 3 SPA
    participant API as FastAPI Backend
    participant Supabase as Supabase Auth
    participant DB as PostgreSQL
    participant Stripe as Stripe
    participant Cache as Redis 缓存
    participant Email as Brevo

    Client->>API: DELETE /api/me (Bearer token)
    API->>API: 校验用户身份
    API->>DB: 创建删除请求 (pending, scheduled_at = now + 30d)
    API-->>Client: 202 Accepted (30天内处理)

    Note over API: 30天后或用户确认立即删除

    API->>Stripe: 取消订阅
    Stripe-->>API: subscription.canceled

    API->>DB: 删除视频 + AI 摘要
    API->>Cache: 删除用户缓存
    API->>DB: 删除用户偏好
    API->>DB: 删除用户记录

    API->>Supabase: admin.delete_user(user_id)
    Supabase-->>API: 用户已删除

    API->>Email: 发送删除确认邮件
    Email-->>Client: 账户已删除

    Note over Stripe: Stripe Customer 保留 7 年（仅含交易记录，无个人数据）
```

### 6.3 数据库表定义

```sql
-- migrations/0003_create_deletion_requests.sql

CREATE TABLE IF NOT EXISTS public.deletion_requests (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 申请删除的用户 ID
    user_id UUID NOT NULL,

    -- 请求状态: pending / processing / completed / failed
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

    -- 请求创建时间
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 计划执行时间（默认 30 天后）
    scheduled_at TIMESTAMPTZ NOT NULL,

    -- 实际执行时间
    executed_at TIMESTAMPTZ,

    -- 失败原因
    failure_reason TEXT,

    -- 软删除标记（用于前端显示"删除中"状态）
    is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,

    -- 审计字段
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_deletion_requests_user_id
    ON public.deletion_requests (user_id);
CREATE INDEX IF NOT EXISTS idx_deletion_requests_status
    ON public.deletion_requests (status);
CREATE INDEX IF NOT EXISTS idx_deletion_requests_scheduled_at
    ON public.deletion_requests (scheduled_at);

-- 注释
COMMENT ON TABLE public.deletion_requests IS 'GDPR Art. 17 删除请求记录';
COMMENT ON COLUMN public.deletion_requests.status IS 'pending=待处理, processing=处理中, completed=已完成, failed=失败';
COMMENT ON COLUMN public.deletion_requests.scheduled_at IS '计划执行删除的时间（通常为用户确认后 30 天）';
```

### 6.4 后端删除服务

```python
# backend/services/deletion_service.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import get_settings
from backend.models.user import User
from backend.models.user_preferences import UserPreferences
from backend.models.deletion_request import DeletionRequest
from backend.models.token_blacklist import TokenBlacklist
from backend.models.video import Video
from backend.models.ai_summary import AISummary
from backend.services.token_service import TokenService

logger = logging.getLogger(__name__)

settings = get_settings()


class DeletionService:
    """GDPR Art. 17 账户删除服务。"""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Any,
        supabase_admin: Any,
    ) -> None:
        self.session = session
        self.redis = redis_client
        self.supabase_admin = supabase_admin
        self.token_service = TokenService(redis_client)

    async def request_deletion(
        self,
        user_id: UUID,
        immediate: bool = False,
    ) -> DeletionRequest:
        """
        创建删除请求。

        Args:
            user_id: 申请删除的用户 ID
            immediate: 是否立即执行（跳过 30 天等待期）

        Returns:
            DeletionRequest 实例
        """
        # 检查是否已有待处理的删除请求
        existing = await self.session.execute(
            select(DeletionRequest).where(
                DeletionRequest.user_id == user_id,
                DeletionRequest.status == "pending",
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("A pending deletion request already exists for this user")

        now = datetime.now(timezone.utc)
        scheduled_at = now if immediate else now + timedelta(
            days=settings.GDPR_DELETION_DAYS
        )

        deletion_request = DeletionRequest(
            user_id=user_id,
            status="pending",
            requested_at=now,
            scheduled_at=scheduled_at,
            is_confirmed=immediate,
        )
        self.session.add(deletion_request)

        # 停用用户账户（立即生效，防止继续登录）
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_active=False, updated_at=now)
        )

        # 撤销所有 Token
        await self.token_service.revoke_all_user_tokens(
            user_id=user_id,
            reason="account_deletion",
            session=self.session,
        )

        await self.session.commit()
        await self.session.refresh(deletion_request)

        logger.info(
            "Deletion request created: user_id=%s scheduled_at=%s immediate=%s",
            user_id,
            scheduled_at.isoformat(),
            immediate,
        )
        return deletion_request

    async def execute_deletion(self, user_id: UUID) -> bool:
        """
        执行账户删除（由定时任务调用或立即执行）。

        删除顺序：
        1. 取消 Stripe 订阅（保留 Customer 7 年）
        2. 删除 AI 摘要缓存
        3. 删除视频记录
        4. 删除用户偏好
        5. 删除 Token 黑名单记录
        6. 删除用户记录
        7. 删除 Supabase Auth 用户
        8. 更新删除请求状态

        Args:
            user_id: 要删除的用户 ID

        Returns:
            是否成功
        """
        logger.info("Executing account deletion: user_id=%s", user_id)
        now = datetime.now(timezone.utc)

        try:
            # 1. 取消 Stripe 订阅（保留 Customer 记录 7 年用于收据）
            await self._cancel_stripe_subscriptions(user_id)

            # 2. 删除 AI 摘要缓存
            await self._delete_ai_summary_cache(user_id)

            # 3. 删除视频记录
            await self.session.execute(
                delete(Video).where(Video.user_id == user_id)
            )

            # 4. 删除用户偏好
            await self.session.execute(
                delete(UserPreferences).where(
                    UserPreferences.user_id == user_id
                )
            )

            # 5. 删除 Token 黑名单记录
            await self.session.execute(
                delete(TokenBlacklist).where(
                    TokenBlacklist.user_id == user_id
                )
            )

            # 6. 删除用户记录
            await self.session.execute(
                delete(User).where(User.id == user_id)
            )

            # 7. 删除 Supabase Auth 用户
            try:
                await self.supabase_admin.auth.admin.delete_user(
                    str(user_id)
                )
                logger.info("Supabase user deleted: %s", user_id)
            except Exception as exc:
                logger.error(
                    "Failed to delete Supabase user %s: %s",
                    user_id,
                    exc,
                )
                # 不阻塞流程，记录失败但继续

            # 8. 更新删除请求状态
            await self.session.execute(
                update(DeletionRequest)
                .where(
                    DeletionRequest.user_id == user_id,
                    DeletionRequest.status == "processing",
                )
                .values(
                    status="completed",
                    executed_at=now,
                    updated_at=now,
                )
            )

            await self.session.commit()
            logger.info("Account deletion completed: user_id=%s", user_id)
            return True

        except Exception as exc:
            logger.error(
                "Account deletion failed: user_id=%s error=%s",
                user_id,
                exc,
            )
            await self.session.execute(
                update(DeletionRequest)
                .where(DeletionRequest.user_id == user_id)
                .values(
                    status="failed",
                    failure_reason=str(exc),
                    updated_at=now,
                )
            )
            await self.session.commit()
            return False

    async def _cancel_stripe_subscriptions(self, user_id: UUID) -> None:
        """取消用户所有活跃 Stripe 订阅。"""
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY

        # 查询用户的 Stripe Customer ID
        result = await self.session.execute(
            select(User.stripe_customer_id).where(User.id == user_id)
        )
        customer_id = result.scalar_one_or_none()

        if not customer_id:
            logger.info("No Stripe customer for user: %s", user_id)
            return

        # 列出并取消所有活跃订阅
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="active",
            limit=100,
        )

        for sub in subscriptions.auto_paging_iter():
            try:
                stripe.Subscription.cancel(
                    sub.id,
                    cancellation_reason="customer_request",
                )
                logger.info(
                    "Stripe subscription canceled: %s for customer %s",
                    sub.id,
                    customer_id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to cancel subscription %s: %s",
                    sub.id,
                    exc,
                )

    async def _delete_ai_summary_cache(self, user_id: UUID) -> None:
        """删除用户的 AI 摘要缓存。"""
        try:
            # 查找所有相关缓存键
            pattern = f"ai_summary:user:{user_id}:*"
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break

            logger.info("AI summary cache deleted for user: %s", user_id)
        except Exception as exc:
            logger.error(
                "Failed to delete AI summary cache for %s: %s",
                user_id,
                exc,
            )

    async def process_pending_deletions(self) -> list[UUID]:
        """
        处理所有到期的删除请求（由定时任务调用）。

        Returns:
            已处理的用户 ID 列表
        """
        now = datetime.now(timezone.utc)

        result = await self.session.execute(
            select(DeletionRequest).where(
                DeletionRequest.status == "pending",
                DeletionRequest.scheduled_at <= now,
            )
        )
        pending_requests = result.scalars().all()

        processed = []
        for request in pending_requests:
            # 标记为处理中
            request.status = "processing"
            request.updated_at = now
            await self.session.commit()

            success = await self.execute_deletion(request.user_id)
            if success:
                processed.append(request.user_id)

        return processed
```

### 6.5 前端删除确认

```vue
<!-- frontend/src/views/AccountDeletion.vue -->
<template>
  <div class="deletion-container">
    <h1>账户删除</h1>

    <div v-if="!deletionRequested" class="deletion-warning">
      <h2>警告：此操作不可逆</h2>
      <p>删除您的账户后，以下数据将被永久删除：</p>
      <ul>
        <li>您的账户信息和登录凭据</li>
        <li>所有上传的视频记录</li>
        <li>所有 AI 生成的摘要</li>
        <li>您的偏好设置</li>
        <li>活跃的订阅（将立即取消）</li>
      </ul>
      <p>
        注意：根据法律要求，您的支付收据将保留 7 年，但不会包含任何可识别的个人信息。
      </p>
      <p>
        您的账户将在 <strong>30 天内</strong> 完成删除。在此期间，您可以联系 support@example.com 撤销此请求。
      </p>

      <label class="confirmation-checkbox">
        <input
          type="checkbox"
          v-model="confirmed"
        />
        我确认我了解删除操作的后果，并请求永久删除我的账户。
      </label>

      <button
        :disabled="!confirmed || loading"
        @click="requestDeletion"
        class="delete-button"
      >
        {{ loading ? '处理中...' : '请求删除我的账户' }}
      </button>
    </div>

    <div v-else class="deletion-confirmed">
      <h2>删除请求已提交</h2>
      <p>您的账户删除请求已成功提交。</p>
      <p>计划删除时间：<strong>{{ scheduledAt }}</strong></p>
      <p>您的账户已被停用，无法再登录。</p>
      <p>如需撤销此请求，请在 30 天内联系 support@example.com。</p>
    </div>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useSupabaseClient } from '@supabase/supabase-js';

const router = useRouter();
const supabase = useSupabaseClient();

const confirmed = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);
const deletionRequested = ref(false);
const scheduledAt = ref<string>('');

async function requestDeletion(): Promise<void> {
  loading.value = true;
  error.value = null;

  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session) {
      throw new Error('请先登录');
    }

    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL}/api/me`,
      {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail?.message || '删除请求失败');
    }

    const data = await response.json();
    deletionRequested.value = true;
    scheduledAt.value = new Date(data.scheduled_at).toLocaleDateString(
      'zh-CN',
      { year: 'numeric', month: 'long', day: 'numeric' }
    );
  } catch (e) {
    error.value = e instanceof Error ? e.message : '请求失败，请重试';
    console.error('Deletion request error:', e);
  } finally {
    loading.value = false;
  }
}
</script>
```

---

## 7. 用户数据导出 (GDPR Art. 20)

### 7.1 概述

根据 GDPR 第 20 条（数据可携带权），用户有权以结构化、通用且机器可读的格式获取其个人数据。本系统设计为 45 天内完成数据导出请求。

### 7.2 流程图

```mermaid
sequenceDiagram
    participant Client as Vue 3 SPA
    participant API as FastAPI Backend
    participant DB as PostgreSQL
    participant Worker as 后台任务
    participant Email as Brevo

    Client->>API: POST /api/me/export
    API->>DB: 创建导出请求(pending)
    API-->>Client: 202 Accepted(45天内完成)

    Note over Worker: 后台任务处理
    Worker->>DB: 查询用户全部数据
    Worker->>Worker: 生成 JSON 导出文件
    Worker->>Cache: 上传加密导出文件
    Worker->>DB: 更新导出请求(completed, download_url)
    Worker->>Email: 发送导出就绪通知

    Client->>API: GET /api/me/export/:id/download
    API->>API: 校验用户身份 + 下载令牌
    API->>Cache: 下载加密文件
    API-->>Client: 加密 JSON 文件
```

### 7.3 数据库表定义

```sql
-- migrations/0004_create_export_requests.sql

CREATE TABLE IF NOT EXISTS public.export_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,  -- 下载链接过期时间(通常 7 天)
    download_url TEXT,       -- 临时签名 URL
    file_size BIGINT,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_export_requests_user_id
    ON public.export_requests (user_id);
CREATE INDEX IF NOT EXISTS idx_export_requests_status
    ON public.export_requests (status);

COMMENT ON TABLE public.export_requests IS 'GDPR Art. 20 数据导出请求记录';
```

### 7.4 后端导出服务

```python
# backend/services/export_service.py
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import get_settings
from backend.models.user import User
from backend.models.user_preferences import UserPreferences
from backend.models.video import Video
from backend.models.ai_summary import AISummary
from backend.models.export_request import ExportRequest

logger = logging.getLogger(__name__)

settings = get_settings()


class ExportService:
    """GDPR Art. 20 数据导出服务。"""

    def __init__(self, session: AsyncSession, redis_client: Any) -> None:
        self.session = session
        self.redis = redis_client

    async def request_export(self, user_id: UUID) -> ExportRequest:
        """创建数据导出请求。"""
        now = datetime.now(timezone.utc)

        export_request = ExportRequest(
            user_id=user_id,
            status="pending",
            requested_at=now,
        )
        self.session.add(export_request)
        await self.session.commit()
        await self.session.refresh(export_request)

        logger.info("Export request created: user_id=%s request_id=%s", user_id, export_request.id)
        return export_request

    async def execute_export(self, request_id: UUID) -> bool:
        """
        执行数据导出。

        导出内容:
        - 用户基本信息
        - 用户偏好
        - 视频记录(不含二进制)
        - AI 摘要
        - 订阅状态(不含支付详情)
        """
        now = datetime.now(timezone.utc)
        export_request = await self.session.get(ExportRequest, request_id)
        if not export_request:
            return False

        try:
            export_request.status = "processing"
            export_request.updated_at = now
            await self.session.commit()

            user_id = export_request.user_id

            # 1. 用户基本信息
            user = await self.session.get(User, user_id)
            user_data = {
                "id": str(user.id),
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
            }

            # 2. 用户偏好
            pref_result = await self.session.execute(
                select(UserPreferences).where(UserPreferences.user_id == user_id)
            )
            pref = pref_result.scalar_one_or_none()
            preferences_data = {
                "language": pref.language if pref else "en",
                "currency": pref.currency if pref else "USD",
                "timezone": pref.timezone if pref else "UTC",
            }

            # 3. 视频记录(不含二进制,仅元信息)
            video_result = await self.session.execute(
                select(Video).where(Video.user_id == user_id)
            )
            videos_data = [
                {
                    "id": str(v.id),
                    "title": v.title,
                    "duration": v.duration,
                    "platform": v.platform,
                    "created_at": v.created_at.isoformat(),
                }
                for v in video_result.scalars().all()
            ]

            # 4. AI 摘要
            summary_result = await self.session.execute(
                select(AISummary).where(AISummary.user_id == user_id)
            )
            summaries_data = [
                {
                    "id": str(s.id),
                    "video_id": str(s.video_id),
                    "content": s.content,
                    "created_at": s.created_at.isoformat(),
                }
                for s in summary_result.scalars().all()
            ]

            # 5. 组装导出数据
            export_data = {
                "export_metadata": {
                    "version": "1.0",
                    "generated_at": now.isoformat(),
                    "format": "GDPR-JSON",
                    "user_id": str(user_id),
                },
                "user": user_data,
                "preferences": preferences_data,
                "videos": videos_data,
                "ai_summaries": summaries_data,
            }

            # 6. 上传到临时存储(加密)
            json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
            file_key = f"gdpr-exports/{user_id}/{request_id}.json"

            # 上传加密文件到对象存储(S3 / MinIO)
            # await storage_service.upload_encrypted(file_key, json_content)

            # 7. 生成临时下载令牌(7 天有效)
            download_token = generate_secure_token()
            expires_at = now + timedelta(days=7)
            await self.redis.setex(
                f"export_download:{download_token}",
                60 * 60 * 24 * 7,
                str(request_id),
            )

            # 8. 更新状态
            export_request.status = "completed"
            export_request.completed_at = now
            export_request.expires_at = expires_at
            export_request.download_url = f"/api/me/export/{request_id}/download?token={download_token}"
            export_request.file_size = len(json_content.encode("utf-8"))
            export_request.updated_at = now
            await self.session.commit()

            logger.info("Export completed: request_id=%s user_id=%s", request_id, user_id)
            return True

        except Exception as exc:
            logger.error("Export failed: request_id=%s error=%s", request_id, exc)
            export_request.status = "failed"
            export_request.failure_reason = str(exc)
            export_request.updated_at = now
            await self.session.commit()
            return False

    async def process_pending_exports(self) -> list[UUID]:
        """处理所有待处理的导出请求(由定时任务调用)。"""
        now = datetime.now(timezone.utc)

        result = await self.session.execute(
            select(ExportRequest).where(
                ExportRequest.status == "pending",
            )
        )
        pending_requests = result.scalars().all()

        processed = []
        for request in pending_requests:
            success = await self.execute_export(request.id)
            if success:
                processed.append(request.id)

        return processed
```

### 7.5 前端数据导出

```vue
<!-- frontend/src/views/DataExport.vue -->
<template>
  <div class="export-container">
    <h1>数据导出</h1>
    <p>根据 GDPR 第 20 条,您有权以机器可读的格式获取您的个人数据。</p>

    <div v-if="!exportRequested">
      <p>导出内容包括:</p>
      <ul>
        <li>账户基本信息</li>
        <li>偏好设置(语言、货币、时区)</li>
        <li>视频记录(元信息)</li>
        <li>AI 摘要内容</li>
      </ul>
      <button :disabled="loading" @click="requestExport">
        {{ loading ? '处理中...' : '请求数据导出' }}
      </button>
    </div>

    <div v-else-if="exportStatus === 'pending'">
      <p>您的导出请求已提交,预计 45 天内完成。</p>
      <p>完成后我们将通过邮件通知您。</p>
    </div>

    <div v-else-if="exportStatus === 'completed'">
      <p>您的数据导出已就绪!</p>
      <a :href="downloadUrl" class="download-button">下载数据</a>
      <p>下载链接将在 7 天后过期。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useSupabaseClient } from '@supabase/supabase-js';

const supabase = useSupabaseClient();
const loading = ref(false);
const exportRequested = ref(false);
const exportStatus = ref<string>('none');
const downloadUrl = ref<string>('');

async function requestExport(): Promise<void> {
  loading.value = true;
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) throw new Error('请先登录');

    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL}/api/me/export`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
      }
    );

    if (!response.ok) throw new Error('导出请求失败');

    exportRequested.value = true;
    exportStatus.value = 'pending';
  } catch (e) {
    console.error('Export request error:', e);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  // 查询是否有已完成的导出请求
  // ...
});
</script>
```

---

## 8. 角色与权限 (RBAC)

### 8.1 角色定义

| 角色 | 每日 AI 总结 | 每日下载 | 思维导图 | 团队 | API | 价格 |
|---|---|---|---|---|---|---|
| **Free** | 3 次 | 5 次 | ❌ | ❌ | ❌ | ¥0 |
| **Pro** | 无限 | 100 次 | ✅ | ❌ | ❌ | ¥49/月 |
| **Premium** | 无限 | 无限 | ✅ | ✅ | ✅ | ¥99/月 |

### 8.2 权限检查装饰器

```python
# backend/core/permissions.py
from functools import wraps
from fastapi import HTTPException, status, Depends
from backend.middleware.auth import get_current_user
from backend.models.user import User

# 角色层级定义
ROLE_HIERARCHY = {
    "free": 0,
    "pro": 1,
    "premium": 2,
}

# 功能所需最低角色
FEATURE_REQUIREMENTS = {
    "ai_summary": "free",        # 所有用户(受配额限制)
    "mindmap": "pro",            # Pro 及以上
    "team": "premium",           # 仅 Premium
    "api": "premium",            # 仅 Premium
    "bulk_export": "pro",        # Pro 及以上
}


def requires_role(required_role: str):
    """
    装饰器:要求最低角色等级。

    用法:
        @requires_role("pro")
        async def mindmap_endpoint(...):
            ...
    """
    required_level = ROLE_HIERARCHY.get(required_role, 0)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 或 args 中提取 current_user
            current_user: User = kwargs.get("current_user")
            if not current_user:
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            user_level = ROLE_HIERARCHY.get(current_user.role, 0)

            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "insufficient_role",
                        "message": f"This feature requires {required_role} role or higher",
                        "current_role": current_user.role,
                        "required_role": required_role,
                    },
                    headers={"X-Required-Role": required_role},
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def requires_vip():
    """快捷装饰器:要求 Premium 角色。"""
    return requires_role("premium")


def check_feature_access(feature: str) -> str:
    """查询功能所需的角色等级(供前端动态渲染 UI)。"""
    return FEATURE_REQUIREMENTS.get(feature, "premium")
```

### 8.3 使用示例

```python
# backend/api/v1/endpoints/ai.py
from backend.core.permissions import requires_role, requires_vip
from backend.middleware.auth import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/summarize")
@requires_role("free")  # 所有用户,但受 rate limit 约束
async def summarize_video(
    body: SummarizeRequest,
    current_user: User = Depends(get_current_user),
):
    """生成视频摘要(所有用户可用,Free 受每日 3 次限制)。"""
    # 检查每日配额
    await rate_limit_service.check_limit(current_user.id, "ai_summary", current_user.role)
    ...


@router.post("/mindmap")
@requires_role("pro")  # Pro 及以上
async def generate_mindmap(
    body: MindmapRequest,
    current_user: User = Depends(get_current_user),
):
    """生成思维导图(Pro 及以上)。"""
    ...


@router.get("/team/members")
@requires_vip()  # 仅 Premium
async def list_team_members(
    current_user: User = Depends(get_current_user),
):
    """列出团队成员(仅 Premium)。"""
    ...
```

### 8.4 配额检查服务

```python
# backend/services/rate_limit_service.py
import redis.asyncio as redis
from datetime import datetime
from backend.core.permissions import ROLE_HIERARCHY

# 各角色每日配额
ROLE_QUOTAS = {
    "free": {"ai_summary": 3, "download": 5},
    "pro": {"ai_summary": -1, "download": 100},  # -1 表示无限
    "premium": {"ai_summary": -1, "download": -1},
}


class RateLimitService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    async def check_limit(
        self,
        user_id: str,
        action: str,
        role: str,
    ) -> None:
        """
        检查并扣减配额。

        Raises:
            HTTPException 429: 超出每日限额
        """
        quota = ROLE_QUOTAS.get(role, {}).get(action, 0)
        if quota == -1:
            return  # 无限

        key = f"rate:{action}:{user_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 86400)  # 24h TTL

        if count > quota:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Daily {action} limit exceeded for {role} role",
                    "quota": quota,
                    "used": count,
                    "reset_at": "00:00 UTC",
                },
                headers={
                    "X-RateLimit-Quota": str(quota),
                    "X-RateLimit-Used": str(count),
                    "X-RateLimit-Reset": "00:00 UTC",
                },
            )
```

### 8.5 前端权限指令

```typescript
// frontend/src/directives/permission.ts
import { Directive, DirectiveBinding } from 'vue';
import { useAuthStore } from '@/stores/auth';

// 角色层级
const ROLE_LEVELS: Record<string, number> = {
  free: 0,
  pro: 1,
  premium: 2,
};

// v-permission="'pro'" 或 v-permission="['pro', 'premium']"
export const vPermission: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding;
    const auth = useAuthStore();

    if (!auth.user) {
      el.style.display = 'none';
      return;
    }

    const userLevel = ROLE_LEVELS[auth.user.role] ?? 0;
    const requiredLevels = Array.isArray(value) ? value : [value];
    const minRequired = Math.min(...requiredLevels.map((r) => ROLE_LEVELS[r] ?? 999));

    if (userLevel < minRequired) {
      el.style.display = 'none';
    }
  },
};
```

```vue
<!-- 使用示例 -->
<template>
  <div>
    <button @click="summarize">AI 摘要(所有用户)</button>
    <button v-permission="'pro'" @click="generateMindmap">思维导图(Pro+)</button>
    <button v-permission="'premium'" @click="openTeam">团队管理(Premium)</button>
  </div>
</template>
```

---

## 9. 会话管理

### 9.1 Token 有效期

| Token | 有效期 | 存储位置 | 用途 |
|---|---|---|---|
| Access Token | 1 小时(Supabase 默认) | 内存 / Pinia store | API 请求 Authorization 头 |
| Refresh Token | 30 天 | HttpOnly Cookie(Supabase 管理) | 刷新 Access Token |
| Magic Link Token | 1 小时 | 一次性 | 邮箱验证 / 登录 |
| Export Download Token | 7 天 | Redis | 数据导出下载链接 |

### 9.2 Token 撤销

```python
# backend/services/auth_service.py
class AuthService:
    async def revoke_all_tokens(self, user_id: str) -> None:
        """用户删除 / 密码重置时撤销所有 token"""
        # Supabase Admin API 撤销所有 refresh token
        self.client.auth.admin.sign_out(user_id)
```

```python
# backend/api/v1/endpoints/auth.py
@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
):
    """登出:撤销所有 token"""
    await token_service.revoke_all_user_tokens(
        user_id=current_user.id,
        reason="logout",
        session=session,
    )
    return {"status": "signed_out"}
```

### 9.3 多设备登录支持

```typescript
// 前端:每个设备独立 session,Supabase 支持多 refresh token
supabase.auth.onAuthStateChange((event, session) => {
  console.log(event, /* SESSION_CHANGED | TOKEN_REFRESHED | SIGNED_IN */)
})
```

```python
# 后端:记录设备信息
CREATE TABLE user_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    device_info TEXT,           -- User-Agent 摘要
    ip_address  INET,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    last_seen   TIMESTAMPTZ DEFAULT NOW()
);
```

### 9.4 会话管理 API

```python
# backend/api/v1/endpoints/sessions.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.models.user_session import UserSession

router = APIRouter(prefix="/api/me/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """列出当前用户所有活跃会话。"""
    result = await session.execute(
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .order_by(UserSession.last_seen.desc())
    )
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "id": str(s.id),
                "device_info": s.device_info,
                "ip_address": str(s.ip_address),
                "created_at": s.created_at.isoformat(),
                "last_seen": s.last_seen.isoformat(),
                "is_current": False,  # 由前端根据当前 token 判断
            }
            for s in sessions
        ],
    }


@router.delete("/{session_id}")
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """撤销指定会话(登出其他设备)。"""
    target = await session.get(UserSession, session_id)
    if not target or target.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    await session.delete(target)
    await session.commit()
    # 同时撤销该 session 的 token
    # ...
    return {"status": "revoked"}
```

---

## 10. 安全最佳实践

### 10.1 CSRF 防护

- Supabase Auth 内置 CSRF 防护(state parameter in OAuth flow)。
- 后端敏感操作要求 `X-Requested-With: XMLHttpRequest` 头。

```python
# backend/api/middleware.py
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            requested_with = request.headers.get("X-Requested-With")
            if requested_with != "XMLHttpRequest":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed"},
                )
        return await call_next(request)
```

### 10.2 暴力破解防护

- Supabase 内置 rate limit: 5 次/分钟/IP(magic link)。
- 后端额外限制:

```python
# backend/api/middleware.py
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host
        key = f"rl:{ip}:{int(time.time()) // 60}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        if count > 60:  # 60 req/min
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
            )
        return await call_next(request)
```

### 10.3 Email 验证强制

```python
# backend/middleware/auth.py
async def get_current_user(...):
    payload = decode_access_token(token)
    if payload.get("email_confirmed_at") is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "email_not_verified",
                "message": "Email verification required",
            },
            headers={"X-Email-Verified": "false"},
        )
```

### 10.4 敏感操作二次验证

```python
# 删除账号 / 修改 email 前,要求重新验证
@router.post("/account/verify-sensitive")
async def verify_sensitive(
    current_user: User = Depends(get_current_user),
):
    """发送一次性验证码,敏感操作前调用"""
    code = generate_otp()
    await redis.setex(f"otp:{current_user.id}", 300, code)  # 5 分钟
    await email_service.send_otp(current_user.email, code)
    return {"status": "otp_sent"}


@router.post("/account/confirm-sensitive")
async def confirm_sensitive(
    code: str,
    current_user: User = Depends(get_current_user),
):
    """验证一次性验证码"""
    stored = await redis.get(f"otp:{current_user.id}")
    if not stored or stored.decode() != code:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    # 标记验证通过,允许后续敏感操作
    await redis.setex(f"sensitive_verified:{current_user.id}", 300, "1")
    return {"status": "verified"}
```

### 10.5 其他最佳实践

| 措施 | 实现 |
|---|---|
| HTTPS 强制 | 生产环境 HSTS |
| JWT 不在 localStorage | Supabase SDK 自动存 HttpOnly Cookie |
| 密码策略 | Supabase 内置强度检查 |
| 审计日志 | 所有敏感操作记录 |
| CORS | 仅允许前端域名 |
| 日志脱敏 | 不记录 token / email |

```python
# backend/core/logging.py
import logging

class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "msg"):
            record.msg = str(record.msg).replace("Bearer ", "Bearer ***")
        return True

# 注册过滤器
logging.getLogger().addFilter(SensitiveDataFilter())
```

### 10.6 安全响应头

```python
# backend/api/middleware.py
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://*.supabase.co"
        )
        return response
```

---

## 11. 验证清单

### 功能验证

- [ ] 用户可通过 Email magic link 注册
- [ ] 用户可通过 Google OAuth 注册
- [ ] 用户可通过 Apple OAuth 注册
- [ ] 首次登录自动创建 `user_preferences`
- [ ] 默认语言从 `Accept-Language` 推断
- [ ] `/api/me` 返回用户信息 + 偏好 + 订阅状态
- [ ] Access Token 过期后自动刷新
- [ ] Refresh Token 过期后跳转登录页
- [ ] 用户可删除账号 (GDPR Art. 17)
- [ ] 删除后业务数据清除
- [ ] 删除后 Stripe Customer 删除(保留收据)
- [ ] 删除确认邮件发送
- [ ] 用户可导出数据 (GDPR Art. 20)
- [ ] 数据导出 45 天内完成
- [ ] Free 角色每日 3 次 AI 总结限制生效
- [ ] Pro 角色可使用思维导图
- [ ] Premium 角色可使用团队功能
- [ ] 多设备登录互不影响
- [ ] 用户可查看活跃会话列表
- [ ] 用户可撤销其他设备会话

### 安全验证

- [ ] CSRF 中间件生效
- [ ] Rate limit 生效
- [ ] 未验证邮箱无法访问敏感接口
- [ ] 敏感操作需二次验证(OTP)
- [ ] JWT 签名验证拒绝篡改 token
- [ ] 过期 token 返回 401 + `X-Token-Expired`
- [ ] CORS 仅允许白名单域名
- [ ] 日志不记录 token / email
- [ ] 安全响应头(CSP / HSTS / X-Frame-Options)正确设置
- [ ] Token 撤销后立即生效
- [ ] 账户删除后所有 token 撤销

### 性能验证

- [ ] JWT 验证 < 5ms(纯计算,无 IO)
- [ ] `/api/me` 响应 < 100ms(含 DB 查询)
- [ ] 并发 1000 QPS 下 JWT 验证不瓶颈
- [ ] Token 刷新 < 50ms

### 合规验证

- [ ] GDPR 删除请求 30 天内响应
- [ ] GDPR 导出请求 45 天内响应
- [ ] 用户数据导出功能
- [ ] 审计日志保留 3 年
- [ ] Stripe 收据保留 7 年
- [ ] 隐私政策页面可访问
- [ ] Cookie 同意管理(CMP)正确集成
- [ ] 用户责任声明在注册页展示

---

> **文档维护者**: 工程团队
> **最后更新**: 2026-06-25
> **下次评审**: 上线前安全审计后