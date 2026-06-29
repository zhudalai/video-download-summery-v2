from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class TranscriptSegment(BaseModel):
    """转录分段"""
    start: float = Field(..., description="开始时间 (秒)")
    end: float = Field(..., description="结束时间 (秒)")
    text: str = Field(..., description="分段文本")


class TranscriptResponse(BaseModel):
    """转录响应"""
    id: str
    video_id: str
    language: str = "auto"
    model: str
    content: Optional[str] = None
    segments: Optional[list[TranscriptSegment]] = None
    word_count: int = 0
    confidence: Optional[float] = None
    processing_time_ms: Optional[int] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
