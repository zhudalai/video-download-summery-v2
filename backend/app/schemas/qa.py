from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class QaSessionCreate(BaseModel):
    """创建问答会话"""
    video_id: str
    model: Optional[str] = Field(default=None, description="AI 模型 (可选)")
    language: Optional[str] = Field(default="zh-CN")
    title: Optional[str] = Field(default=None, description="会话标题 (可选,自动从视频生成)")


class QaMessageCreate(BaseModel):
    """发送问答消息"""
    content: str = Field(..., min_length=1, max_length=10000, description="问题内容")


class QaMessageResponse(BaseModel):
    """问答消息响应"""
    id: str
    session_id: str
    role: str  # user / assistant / system
    content: str
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    latency_ms: Optional[int] = None
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QaSessionResponse(BaseModel):
    """问答会话详情"""
    id: str
    user_id: str
    video_id: str
    summary_id: Optional[str] = None
    title: Optional[str] = None
    model: str
    language: str = "zh-CN"
    message_count: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    status: str = "active"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
