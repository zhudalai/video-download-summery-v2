"""AI 总结服务。

提供两个入口:
- ``generate_summary_stream``  —— SSE 流式(前端 EventSource / fetch + ReadableStream)
- ``generate_summary_sync``   —— 同步阻塞(测试 / 脚本调用)
"""
import asyncio
import json

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.config.router import get_route
from app.prompts.templates import build_messages, get_prompt
from app.services.llm_client import LLMClient


# ----------------------------------------------------------------------
# 流式总结
# ----------------------------------------------------------------------

async def generate_summary_stream(
    title: str,
    transcript: str,
    language: str,
    request: Request,
    question: str = "",
) -> StreamingResponse:
    """
    生成 AI 总结(SSE 流式),或基于字幕的 AI 问答(question 非空时)。

    协议:
    - Content-Type: text/event-stream
    - 每 30 秒发 ``: ping\\n\\n`` 心跳保活
    - 每个 chunk ``data: {...}\\n\\n``
    - 流结束 ``data: [DONE]\\n\\n``
    """
    settings = get_settings()
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OpenRouter API key not configured")

    route = get_route(language)
    # question 非空则走 QA 模板,否则走总结模板
    prompt = get_prompt("v1_qa" if question else "v1")
    messages = build_messages(prompt, title, transcript, language, question)

    llm = LLMClient(settings.OPENROUTER_API_KEY)

    async def generate():
        HEARTBEAT_INTERVAL = 30  # 秒
        last_event = asyncio.get_event_loop().time()
        content_parts: list[str] = []

        try:
            async for raw in llm.stream_with_fallback(messages, route, request):
                # 心跳保活
                now = asyncio.get_event_loop().time()
                if now - last_event > HEARTBEAT_INTERVAL:
                    yield ": ping\n\n"
                    last_event = now

                # 检查是否是错误 payload
                try:
                    data = json.loads(raw)
                    if "error" in data:
                        yield f"data: {raw}\n\n"
                        return
                except json.JSONDecodeError:
                    pass

                # 透传 OpenRouter chunk
                yield f"data: {raw}\n\n"
                last_event = now

                # 收集内容(后续可存入数据库)
                try:
                    data = json.loads(raw)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        content_parts.append(content)
                except Exception:
                    pass

            # 流结束
            yield "data: [DONE]\n\n"

        except asyncio.CancelledError:
            # 客户端主动断开,静默处理
            pass
        except Exception as e:
            error_msg = json.dumps({"error": str(e), "code": "STREAM_ERROR"})
            yield f"data: {error_msg}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 关闭 Nginx 缓冲
        },
    )


# ----------------------------------------------------------------------
# 同步总结(测试用)
# ----------------------------------------------------------------------

def generate_summary_sync(title: str, transcript: str, language: str) -> str:
    """
    生成 AI 总结(非流式)。

    主要用于单元测试或 CLI 脚本。
    """
    import httpx

    settings = get_settings()
    route = get_route(language)
    prompt = get_prompt("v1")
    messages = build_messages(prompt, title, transcript, language)

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://your-app.com",
            },
            json={
                "model": route.primary,
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
