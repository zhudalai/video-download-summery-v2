import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan = Column(String(30), nullable=False)  # free / pro / premium
    status = Column(String(20), default="active", index=True)  # active / canceled / expired / past_due
    stripe_subscription_id = Column(String(255), nullable=True, unique=True)
    stripe_price_id = Column(String(255), nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(String(1), default="0")  # 0 / 1 (SQLite 兼容)
    quota_daily = Column(Integer, default=10)  # 每日配额
    quota_monthly = Column(Integer, default=100)  # 每月配额
    used_today = Column(Integer, default=0)
    used_this_month = Column(Integer, default=0)
    reset_date = Column(DateTime, nullable=True)  # 下次配额重置时间
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
