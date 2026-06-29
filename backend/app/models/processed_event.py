import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class ProcessedEvent(Base):
    """已处理事件模型 一 用于 Webhook 幂等性去重"""
    __tablename__ = "processed_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False, index=True)  # stripe_webhook / callback / task
    event_key = Column(String(255), nullable=False, unique=True)  # 幂等键 (如 stripe event id)
    source = Column(String(50), nullable=True)  # stripe / internal / youtube
    payload = Column(JSON, nullable=True)  # 原始事件数据摘要
    processed_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # 过期清理时间

    __table_args__ = (
        # 联合索引: 按类型查找最近处理的事件
        {"sqlite_autoincrement": True},
    )
