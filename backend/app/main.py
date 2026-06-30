from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import video, ai, payment, auth

settings = get_settings()

app = FastAPI(title="AI Video Summary API", version="0.1.0")

# CORS:允许所有前端域名(生产 + 开发)
allowed_origins = [
    "https://video-download-summery.vercel.app",
    "https://video-download-summery-k9tos3dgq-zhu-yanjun-s-projects.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# 也允许用户配置的 FRONTEND_URL
if settings.FRONTEND_URL and settings.FRONTEND_URL not in allowed_origins:
    allowed_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video.router)
app.include_router(ai.router)
app.include_router(payment.router)
app.include_router(auth.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0", "commit": "c033da5"}


@app.get("/")
async def root():
    return {
        "app": "AI Video Summary API",
        "version": "0.1.0",
        "docs": "/docs",
    }
