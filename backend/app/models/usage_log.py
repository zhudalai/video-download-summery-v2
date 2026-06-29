import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # video_download / transcript / summary / mindmap / qa_message
    resource_type = Column(String(30), nullable=True)  # video / transcript / summary / mindmap / qa
    resource_id = Column(String(36), nullable=True)
    model = Column(String(100), nullable=True)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    cost = Column(Float, default=0.0)  # 本次调用成本(美元)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(20), default="success", index=True)  # success / failed / timeout
    error_message = Column(Text, nullable=True)
    log_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now(), index=True)
