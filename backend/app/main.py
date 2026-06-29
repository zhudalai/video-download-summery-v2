from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import video, ai, payment, auth

settings = get_settings()

app = FastAPI(title="AI Video Summary API", version="0.1.0")

# CORS:允许前端域名 + 本地开发
allowed_origins = [settings.FRONTEND_URL]
if settings.APP_ENV == "development":
    allowed_origins += ["http://localhost:5173", "http://127.0.0.1:5173"]
# 也允许 Cloudflare Pages 默认域名
if ".pages.dev" not in settings.FRONTEND_URL:
    allowed_origins.append("https://*.pages.dev")

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
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    return {
        "app": "AI Video Summary API",
        "version": "0.1.0",
        "docs": "/docs",
    }
