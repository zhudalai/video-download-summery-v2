"""SQLAlchemy 模型注册中心 — 在此导入所有模型供 Alembic 自动发现。"""

from app.database import Base
from app.models.user import User
from app.models.video import Video
from app.models.transcript import Transcript
from app.models.summary import Summary
from app.models.mindmap import Mindmap
from app.models.qa import QaSession, QaMessage
from app.models.subscription import Subscription
from app.models.usage_log import UsageLog
from app.models.processed_event import ProcessedEvent
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "User",
    "Video",
    "Transcript",
    "Summary",
    "Mindmap",
    "QaSession",
    "QaMessage",
    "Subscription",
    "UsageLog",
    "ProcessedEvent",
    "AuditLog",
]
