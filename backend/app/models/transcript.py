import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(String(10), default="auto")  # BCP-47 或 auto
    model = Column(String(100), nullable=False)  # 转录模型名称
    content = Column(Text)  # 完整转录文本
    segments = Column(JSON, default=list)  # 分段信息 [{start, end, text}, ...]
    word_count = Column(Integer, default=0)
    confidence = Column(Float, nullable=True)  # 平均置信度 0-1
    processing_time_ms = Column(Integer, nullable=True)
    status = Column(String(30), default="pending", index=True)  # pending / processing / completed / failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
