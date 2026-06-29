from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Any
from datetime import datetime


class VideoCreate(BaseModel):
    """视频下载请求"""
    url: HttpUrl = Field(..., description="视频 URL")
    language: Optional[str] = Field(default="auto", description="首选转录语言 (BCP-47)")


class VideoResponse(BaseModel):
    """视频响应"""
    id: str
    url: str
    platform: str
    platform_video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    thumbnail_url: Optional[str] = None
    metadata: Optional[dict] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VideoListResponse(BaseModel):
    """视频列表响应"""
    items: list["VideoResponse"]
    total: int
    page: int
    page_size: int
