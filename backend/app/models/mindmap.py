import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Mindmap(Base):
    __tablename__ = "mindmaps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_id = Column(String(36), ForeignKey("summaries.id", ondelete="SET NULL"), nullable=True, index=True)
    model = Column(String(100), nullable=False)
    content = Column(JSON, nullable=False)  # 思维导图 JSON 结构
    content_text = Column(Text)  # 纯文本格式 (用于导出)
    language = Column(String(10), default="zh-CN")
    node_count = Column(Integer, default=0)
    processing_time_ms = Column(Integer, nullable=True)
    status = Column(String(30), default="pending", index=True)  # pending / generating / completed / failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
