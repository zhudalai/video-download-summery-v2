from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class MindmapNode(BaseModel):
    """思维导图节点"""
    id: str
    label: str
    children: Optional[list["MindmapNode"]] = None


class MindmapResponse(BaseModel):
    """思维导图响应"""
    id: str
    video_id: str
    summary_id: Optional[str] = None
    model: str
    content: dict
    content_text: Optional[str] = None
    language: str = "zh-CN"
    node_count: int = 0
    processing_time_ms: Optional[int] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
