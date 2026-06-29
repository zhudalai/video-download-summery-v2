import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Float, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    platform = Column(String(50), nullable=False, index=True)
    platform_video_id = Column(String(255), nullable=False)
    title = Column(String(500))
    description = Column(Text)
    duration = Column(Integer)
    thumbnail_url = Column(Text)
    video_metadata = Column("metadata", JSON, default=dict)
    status = Column(String(30), default="pending", index=True)  # pending / processing / completed / failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联关系
    __table_args__ = (
        # 联合唯一索引: 同一用户同一平台同一视频不重复
        {"sqlite_autoincrement": True},
    )
