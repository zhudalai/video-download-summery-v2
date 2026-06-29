"""App routers package."""
from app.routers.video import router as video_router
from app.routers.ai import router as ai_router
from app.routers.payment import router as payment_router
from app.routers.auth import router as auth_router

__all__ = ["video_router", "ai_router", "payment_router", "auth_router"]
