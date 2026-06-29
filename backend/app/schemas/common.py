from pydantic import BaseModel
from typing import Optional


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str = "0.1.0"
    environment: str = "development"
