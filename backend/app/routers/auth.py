from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/health")
async def auth_health():
    return {"status": "auth module ready"}


@router.get("/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
):
    """获取当前登录用户的资料(从 JWT token 读取)"""
    return current_user


@router.get("/me/role")
async def get_user_role(
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户的角色(从 JWT token 读取)"""
    role = current_user.get("app_metadata", {}).get("role", "authenticated")
    return {"role": role}
