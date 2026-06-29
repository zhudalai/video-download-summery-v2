"""OpenRouter LLM 客户端。

特性:
- SSE 流式请求 (stream=True)
- 指数退避重试 (2**attempt + jitter)
- 主模型 → 备模型自动 Fallback
- 客户端断开检测
"""
import asyncio
import json
import random
from typing import AsyncGenerator

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMClient:
    """基于 httpx 的异步 OpenRouter 客户端。"""

    def __init__(self, api_key: str, referer: str = "https://your-app.com") -> None:
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": referer,
                "X-Title": "Video Summary",
            },
            timeout=httpx.Timeout(10.0, read=300.0),
        )

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def stream_with_fallback(
        self,
        messages: list[dict],
        route,  # RouteRule
        request=None,  # FastAPI Request,用于检测客户端是否断开
    ) -> AsyncGenerator[str, None]:
        """
        按路由规则流式调用 LLM,主模型失败自动切备模型。

        Yields:
            原始 JSON chunk 字符串 (不含 ``data:`` 前缀)
        """
        models = [route.primary] + route.fallbacks
        max_retries = 3

        for model in models:
            for attempt in range(max_retries):
                try:
                    async for chunk in self._stream_one(model, messages, request):
                        yield chunk
                    return  # 整个模型调用成功,退出
                except httpx.TimeoutException:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait)
                    continue
                except httpx.HTTPStatusError as e:
                    # 429 / 5xx → 重试
                    if e.response.status_code in (429, 502, 503, 504):
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        await asyncio.sleep(wait)
                        continue
                    raise
                except Exception:
                    if attempt == max_retries - 1:
                        break  # 换下一个模型
                    await asyncio.sleep(2 ** attempt)
                    continue

        # 所有模型都失败
        yield json.dumps({"error": "所有模型均不可用", "code": "ALL_MODELS_FAILED"})

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    async def _stream_one(
        self,
        model: str,
        messages: list[dict],
        request,
    ) -> AsyncGenerator[str, None]:
        """对单个模型发起 SSE 流请求。"""
        async with self.client.stream(
            "POST",
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.7,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                # 客户端已断开 → 提前退出
                if request and await request.is_disconnected():
                    return
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        return
                    yield raw
