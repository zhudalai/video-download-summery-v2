import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class QaSession(Base):
    __tablename__ = "qa_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_id = Column(String(36), ForeignKey("summaries.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=True)  # 自动生成或用户编辑
    model = Column(String(100), nullable=False)
    language = Column(String(10), default="zh-CN")
    message_count = Column(Integer, default=0)
    total_tokens_input = Column(Integer, default=0)
    total_tokens_output = Column(Integer, default=0)
    status = Column(String(20), default="active", index=True)  # active / archived / deleted
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class QaMessage(Base):
    __tablename__ = "qa_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("qa_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    msg_metadata = Column("metadata", JSON, default=dict)  # 引用来源、上下文片段等
    created_at = Column(DateTime, server_default=func.now())
