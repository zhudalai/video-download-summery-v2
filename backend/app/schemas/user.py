from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    """用户资料响应"""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    language: str = "en"
    currency: str = "USD"
    timezone: str = "UTC"
    role: str = "free"
    stripe_customer_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """用户资料更新请求"""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    language: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None


class UserPreferences(BaseModel):
    """用户偏好"""
    language: str = "en"
    currency: str = "USD"
    timezone: str = "UTC"
