from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # Supabase auth.users.id
    email = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    # 用户偏好
    language = Column(String, default="en")  # BCP-47: en, zh-CN, ja
    currency = Column(String, default="USD")  # ISO 4217
    timezone = Column(String, default="UTC")  # IANA timezone

    # 权限与订阅
    role = Column(String, default="free")  # free / pro / premium / admin
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)

    # 状态
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)
