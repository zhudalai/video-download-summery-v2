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
    # 优先从环境变量读取,如果没有则使用内置 Cookie
    YOUTUBE_COOKIE_PATH: str = "data/youtube_cookie.txt"
    YOUTUBE_COOKIE: str = (
        ".youtube.com\tTRUE\t/\tTRUE\t1817345173\tPREF\ttz=Asia.Tokyo&f4=4000000&f6=40000000&f7=100; "
        ".youtube.com\tTRUE\t/\tTRUE\t1791622062\t__Secure-BUCKET\tCNQE; "
        ".youtube.com\tTRUE\t/\tTRUE\t1812524846\t__Secure-YENID\t15.YT; "
        ".youtube.com\tTRUE\t/\tFALSE\t1817344727\tHSID\tAvrRnJYvJeaXCLzSr; "
        ".youtube.com\tTRUE\t/\tTRUE\t1817344727\tSSID\tALB7Sac1ROZePOjjC; "
        ".youtube.com\tTRUE\t/\tFALSE\t1817344727\tAPISID\tIxUEDx5FA-ivxVaX/AiY15pca3NTpol2cG; "
        ".youtube.com\tTRUE\t/\tTRUE\t1817344727\tSAPISID\tZmZHY1TPdUhoNfBP/AHKZXGZLvb0jq0ANv; "
        ".youtube.com\tTRUE\t/\tTRUE\t1817344727\t__Secure-1PAPISID\tZmZHY1TPdUhoNfBP/AHKZXGZLvb0jq0ANv; "
        ".youtube.com\tTRUE\t/\tTRUE\t1817344727\t__Secure-3PAPISID\tZmZHY1TPdUhoNfBP/AHKZXGZLvb0jq0ANv; "
        ".youtube.com\tTRUE\t/\tTRUE\t1782786526\tGPS\t1; "
        ".youtube.com\tTRUE\t/\tFALSE\t1817344727\tSID\tg.a000_ggdqf4ItEcP1sj0fzQDqdds6XXv1LmxGTEq3RghMiVkPgwpcoDzVAGRBpb9iwvT6QS-wgACgYKAc8SARQSFQHGX2MiPj7M8krYHycdyEcpsEqhRRoVAUF8yKot3Zc8XRQa17kw5ehMUwan0076; "
        ".youtube.com\tTRUE\t/\tTRUE\t1817344727\t__Secure-1PSID\tg.a000_ggdqf4ItEcP1sj0fzQDqdds6XXv1LmxGTEq3RghMiVkPgwpUCEDOjhpk7yLHWxCYSNG1gACgYKAQESARQSFQHGX2MiHzxc-0ui-hsMqaMzyPpdmRoVAUF8yKoZq4qbAbRdO6xLVn9tzxO70076; "
        ".youtube.com\tTRUE\t/\tTRUE\t1817344727\t__Secure-3PSID\tg.a000_ggdqf4ItEcP1sj0fzQDqdds6XXv1LmxGTEq3RghMiVkPgwplqhZ-41meHOpiDsIaTFzQQACgYKAf4SARQSFQHGX2Mi6tc42w_89RHMflBrciK6JBoVAUF8yKoWFr0YuxATe04VeZXaSfss0076; "
        ".youtube.com\tTRUE\t/\tTRUE\t1814321162\t__Secure-1PSIDTS\tsidts-CjUByojQU82Jh6TMbQlyOXwEhJFsqbTvD_ZIfrRWg0YPCpquTr9Kekddyi4OwqtPreiLUaVKkBAA; "
        ".youtube.com\tTRUE\t/\tTRUE\t1814321162\t__Secure-3PSIDTS\tsidts-CjUByojQU82Jh6TMbQlyOXwEhJFsqbTvD_ZIfrRWg0YPCpquTr9Kekddyi4OwqtPreiLUaVKkBAA; "
        ".youtube.com\tTRUE\t/\tTRUE\t1817345167\tLOGIN_INFO\tAFmmF2swRgIhAOQzwPE7dE8l79Q5a84U-iTGPA4R7P-h3f5J56CgccC4AiEAnjtK9BytIuQoqouG1IZinKCDpx9rSe-Mn257SOOHly4:QUQ3MjNmenZ1VEVRbWxDV0Mzalg4SUZHMVBjc3lSNGdTTHgzYngtTmcwa0VYUlk0dWI3eHhRX1dZT09fWXFFc3NkSnhlck9jU2xldl80SU4wd1hQTV9kd2VpREhIUGc5a2hfaXdOS040R1JuQ2lBbGticnlhaUVueW0xMERuV2hBcE9kdFRGMmlzbEtiRkd2YmZsWk1vOWtTck8yR2hzU2dR"
    )

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
