"""AI 路由。

提供 AI 相关 API:
- GET  /api/ai/health    — 模块就绪检查
- POST /api/ai/summary   — 生成视频总结 (SSE 流式)
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.services.summary_service import generate_summary_stream

router = APIRouter(prefix="/api/ai", tags=["ai"])


class SummaryRequest(BaseModel):
    title: str
    transcript: str
    language: str = "en"


@router.get("/health")
async def ai_health():
    """AI 模块健康检查。"""
    return {"status": "ai module ready"}


@router.post("/summary")
async def create_summary(request: SummaryRequest, fastapi_request: Request):
    """
    生成 AI 总结(SSE 流式)。

    前端消费方式:
    - EventSource(不支持 POST,需要改为 GET 或用 fetch)
    - 推荐: fetch + ReadableStream 读取 SSE
    """
    if not request.transcript:
        raise HTTPException(status_code=400, detail="转录文本不能为空")

    return await generate_summary_stream(
        title=request.title,
        transcript=request.transcript,
        language=request.language,
        request=fastapi_request,
    )


class QARequest(BaseModel):
    transcript: str
    question: str
    language: str = "en"


@router.post("/qa")
async def ask_question(request: QARequest, fastapi_request: Request):
    """
    基于视频内容的 AI 问答(SSE 流式)。
    """
    if not request.transcript:
        raise HTTPException(status_code=400, detail="转录文本不能为空")
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    return await generate_summary_stream(
        title="问答",
        transcript=request.transcript,
        language=request.language,
        question=request.question,
        request=fastapi_request,
    )
