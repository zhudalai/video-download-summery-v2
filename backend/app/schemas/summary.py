from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class SummaryCreate(BaseModel):
    """AI 总结创建请求"""
    video_id: str
    model: Optional[str] = Field(default=None, description="AI 模型 (可选,默认用服务端配置)")
    language: Optional[str] = Field(default="zh-CN", description="总结语言")
    prompt_version: Optional[str] = Field(default="v1", description="提示词版本")


class SummaryResponse(BaseModel):
    """AI 总结响应"""
    id: str
    video_id: str
    transcript_id: Optional[str] = None
    model: str
    prompt_version: str = "v1"
    content: Optional[str] = None
    content_type: str = "markdown"
    language: str = "zh-CN"
    word_count: int = 0
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    processing_time_ms: Optional[int] = None
    status: str = "pending"
    error_message: Optional[str] = None
    extra_data: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SummaryStream(BaseModel):
    """SSE 流式总结响应块"""
    type: str = Field(..., description="chunk / done / error")
    content: Optional[str] = Field(default=None, description="增量内容块")
    full_content: Optional[str] = Field(default=None, description="完整内容 (done 时)")
    error: Optional[str] = Field(default=None, description="错误信息 (error 时)")
