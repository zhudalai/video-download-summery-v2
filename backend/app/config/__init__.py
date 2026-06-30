from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"

    # Supabase Auth
    SUPABASE_URL: str = "https://xxxxxxxx.supabase.co"
    SUPABASE_JWT_SECRET: str = "your-jwt-secret-here"
    SUPABASE_ANON_KEY: str = ""

    # OpenRouter
    OPENROUTER_API_KEY: str = "sk-or-xxxxxxxx"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Stripe
    STRIPE_SECRET_KEY: str = "sk_test_xxxxxxxx"
    STRIPE_WEBHOOK_SECRET: str = "whsec_xxxxxxxx"

    # YouTube Cookie(解决 429 限流)
    YOUTUBE_COOKIE_PATH: str = ""
    YOUTUBE_COOKIE: str = ""

    # App
    APP_ENV: str = "development"
    APP_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
