import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_id = Column(String(36), ForeignKey("transcripts.id", ondelete="SET NULL"), nullable=True, index=True)
    model = Column(String(100), nullable=False)  # AI 模型名称
    prompt_version = Column(String(20), default="v1")  # 提示词版本
    content = Column(Text)  # 总结内容 (Markdown)
    content_type = Column(String(30), default="markdown")  # markdown / plain / structured
    language = Column(String(10), default="zh-CN")
    word_count = Column(Integer, default=0)
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    status = Column(String(30), default="pending", index=True)  # pending / streaming / completed / failed
    error_message = Column(Text, nullable=True)
    extra_data = Column(JSON, default=dict)  # 额外数据 (章节列表、关键帧等)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
