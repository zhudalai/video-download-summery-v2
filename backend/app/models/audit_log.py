import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class AuditLog(Base):
    """审计日志模型 一 记录关键操作"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)  # login / update_profile / delete / export / admin_action
    resource_type = Column(String(30), nullable=True)  # user / video / subscription / system
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    user_agent = Column(Text, nullable=True)
    detail = Column(JSON, default=dict)  # 变更前后值、额外上下文
    severity = Column(String(10), default="info", index=True)  # info / warning / critical
    created_at = Column(DateTime, server_default=func.now(), index=True)
