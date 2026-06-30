import os
import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.services.video_service import (
    download_subtitles_text_async,
    download_video_to_temp_async,
    extract_video_info_async,
    is_blacklisted,
    translate_srt_async,
)


def _schedule_delete(path: str, delay: int = 600):
    """delay 秒后删除文件(后台线程)"""
    def _delete():
        import time
        time.sleep(delay)
        try:
            os.remove(path)
        except OSError:
            pass
    threading.Thread(target=_delete, daemon=True).start()

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("/health")
async def video_health():
    return {"status": "video module ready"}


class VideoParseRequest(BaseModel):
    url: str


@router.post("/parse")
async def parse_video(req: VideoParseRequest):
    """解析视频信息(不下载视频)。"""
    if is_blacklisted(req.url):
        raise HTTPException(status_code=403, detail="该平台暂不支持")

    try:
        info = await extract_video_info_async(req.url)
        subtitle_info = info.get("subtitles", {})
        return {
            "title": info.get("title", ""),
            "duration": info.get("duration"),
            "platform": info.get("platform", "unknown"),
            "thumbnail": info.get("thumbnail", ""),
            "channel": info.get("channel", ""),
            "formats": [
                {
                    "format_id": f.get("format_id", ""),
                    "ext": f.get("ext", ""),
                    "resolution": f.get("resolution", ""),
                    "filesize": f.get("filesize"),
                    "vcodec": f.get("vcodec", "none"),
                    "acodec": f.get("acodec", "none"),
                    "has_audio": f.get("has_audio", False),
                }
                for f in info.get("formats", [])
            ],
            "subtitle_languages": list(subtitle_info.get("subtitles", {}).keys())[:10],
            "has_automatic_captions": bool(subtitle_info.get("automatic_captions")),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"视频解析失败: {str(e)}")


class SubtitlesRequest(BaseModel):
    url: str
    language: str = "en"


class TranslateRequest(BaseModel):
    content: str
    target_language: str = "en"


@router.post("/translate")
async def translate_subtitles(req: TranslateRequest):
    """将字幕翻译为目标语言。"""
    if not req.content:
        raise HTTPException(status_code=400, detail="字幕内容不能为空")
    try:
        translated = await translate_srt_async(req.content, req.target_language)
        return {"content": translated, "language": req.target_language}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")


@router.post("/subtitles")
async def get_subtitles(req: SubtitlesRequest):
    """获取视频字幕文本。"""
    if is_blacklisted(req.url):
        raise HTTPException(status_code=403, detail="该平台暂不支持")
    try:
        result = await download_subtitles_text_async(req.url, req.language)
        if result is None:
            # 区分"真的无字幕"和"429 限流"
            return {"content": None, "language": req.language or "auto", "length": 0, "error": "no_subtitles"}
        return {"content": result, "language": req.language or "auto", "length": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        # 429 限流时返回特定错误码
        if "429" in str(e):
            return {"content": None, "language": req.language or "auto", "length": 0, "error": "rate_limited"}
        raise HTTPException(status_code=500, detail=f"字幕获取失败: {str(e)}")


@router.get("/download/subtitles")
async def download_subtitles_file(url: str, lang: str = "auto", fmt: str = "srt"):
    """下载字幕文件(SRT/VTT/TXT)。"""
    if is_blacklisted(url):
        raise HTTPException(status_code=403, detail="该平台暂不支持")
    try:
        # 获取字幕文本
        result = await download_subtitles_text_async(url, lang)
        if not result:
            raise HTTPException(status_code=404, detail="该视频无可用字幕")
        # 格式转换
        content = _convert_subtitle_format(result, fmt)
        # 返回文件
        from fastapi.responses import PlainTextResponse
        media_type = "text/plain" if fmt == "txt" else "text/srt" if fmt == "srt" else "text/vtt"
        filename = f"subtitle.{fmt}"
        return PlainTextResponse(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"字幕下载失败: {str(e)}")


def _convert_subtitle_format(text: str, fmt: str) -> str:
    """将字幕文本转换为指定格式(SRT/VTT/TXT)。"""
    import re
    # 解析字幕文本(假设是空格或换行分隔的纯文本)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if fmt == "txt":
        return "\n".join(lines)
    # SRT 格式
    if fmt == "srt":
        srt_content = ""
        for i, line in enumerate(lines, 1):
            start = _seconds_to_srt_time((i - 1) * 5)
            end = _seconds_to_srt_time(i * 5)
            srt_content += f"{i}\n{start} --> {end}\n{line}\n\n"
        return srt_content
    # VTT 格式
    if fmt == "vtt":
        vtt_content = "WEBVTT\n\n"
        for i, line in enumerate(lines, 1):
            start = _seconds_to_vtt_time((i - 1) * 5)
            end = _seconds_to_vtt_time(i * 5)
            vtt_content += f"{start} --> {end}\n{line}\n\n"
        return vtt_content
    return "\n".join(lines)


def _seconds_to_srt_time(seconds: float) -> str:
    """秒数转 SRT 时间格式 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_vtt_time(seconds: float) -> str:
    """秒数转 VTT 时间格式 HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


class VideoDownloadRequest(BaseModel):
    url: str
    format_id: str = "best"


@router.post("/download")
async def download_video(req: VideoDownloadRequest, background_tasks: BackgroundTasks):
    """下载视频文件到本地并返回(临时文件,下载后自动清理)。"""
    if is_blacklisted(req.url):
        raise HTTPException(status_code=403, detail="该平台暂不支持")
    try:
        path = await download_video_to_temp_async(req.url, req.format_id)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=400, detail="视频下载失败")
        background_tasks.add_task(os.remove, path)
        filename = os.path.basename(path)
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"视频下载失败: {str(e)}")
