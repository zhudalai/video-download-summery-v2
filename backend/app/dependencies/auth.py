import time
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

from app.config import get_settings

security = HTTPBearer()

# ---- JWKS 缓存 ----
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """获取或创建 JWKS 客户端(带缓存)"""
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url,
            headers={"apikey": settings.SUPABASE_ANON_KEY},
        )
    return _jwks_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    验证 Supabase JWT,返回 token payload。
    使用 PyJWKClient 自动获取公钥并验证。
    """
    settings = get_settings()
    token = credentials.credentials
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            issuer=f"{settings.SUPABASE_URL}/auth/v1",
            options={
                "verify_aud": False,
                "verify_exp": True,
            },
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期,请刷新",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"认证失败: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    token_payload: dict = Depends(get_current_user),
) -> dict:
    """
    验证 JWT,返回用户数据。
    """
    return token_payload


def require_role(*roles: str):
    """
    角色权限检查装饰器工厂。
    """
    async def role_checker(
        current_user: dict = Depends(get_current_user),
    ):
        token_role = current_user.get("app_metadata", {}).get("role", "authenticated")
        if token_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user
    return role_checker
