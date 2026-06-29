import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import httpx


async def extract_subtitles_from_video(
    video_url: str,
    language: str = 'en',
) -> Optional[str]:
    """
    从视频中提取字幕文本
    1. 先尝试 yt-dlp 下载 YouTube 自动字幕
    2. 如果没有,下载音频并用 whisper 转录
    返回: 纯文本字幕
    """
    from app.services.video_service import download_subtitles_async

    # 方法1: 下载 YouTube 自动字幕
    subtitle_path = await download_subtitles_async(video_url, language)
    if subtitle_path and os.path.exists(subtitle_path):
        return _parse_srt(subtitle_path)

    # 方法2: 下载视频 → 提取音频 → whisper 转录
    # TODO: 实现 whisper 转录(后续)

    return None


def _parse_srt(srt_path: str) -> str:
    """解析 SRT 文件,返回纯文本"""
    import re
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 移除时间戳和序号
    lines = []
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.isdigit() or '-->' in line:
            continue
        lines.append(line)
    return ' '.join(lines)


def split_into_segments(text: str, max_chars: int = 5000) -> list[dict]:
    """将长文本分割成带时间戳的段落(MVP 简化版,无实际时间戳)"""
    segments = []
    paragraphs = text.split('\n\n')
    current_segment = {"start": 0, "end": 0, "text": ""}
    current_chars = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_chars + len(para) > max_chars and current_segment["text"]:
            segments.append(current_segment)
            current_segment = {"start": 0, "end": 0, "text": para}
            current_chars = len(para)
        else:
            if current_segment["text"]:
                current_segment["text"] += "\n" + para
            else:
                current_segment["text"] = para
            current_chars += len(para)

    if current_segment["text"]:
        segments.append(current_segment)

    return segments
