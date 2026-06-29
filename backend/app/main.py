from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import video, ai, payment, auth

settings = get_settings()

app = FastAPI(title="AI Video Summary API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
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
