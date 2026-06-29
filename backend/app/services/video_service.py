import asyncio
import re
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import yt_dlp

# 敏感站点黑名单
BLACKLISTED_DOMAINS = [
    'netflix.com', 'spotify.com', 'music.apple.com',
    'hulu.com', 'disneyplus.com', 'hbomax.com', 'primevideo.com',
    'udemy.com', 'coursera.org', 'skillshare.com',
]


def is_blacklisted(url: str) -> bool:
    """检查 URL 是否在黑名单中"""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    return any(blacklisted in domain for blacklisted in BLACKLISTED_DOMAINS)


def extract_video_info(url: str) -> dict:
    """
    快速解析视频信息(不下载视频)
    返回: title, duration, description, thumbnail, formats, subtitles
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail'),
            'platform': info.get('extractor', 'unknown'),
            'platform_video_id': info.get('id', ''),
            'formats': _filter_formats(info.get('formats', [])),
            'subtitles': _extract_subtitle_info(info),
        }


def _filter_formats(formats: list) -> list:
    """
    过滤 + 排序 + 去重:
    - 保留有视频或音频的格式
    - 按分辨率降序(高的在前)
    - 同 resolution+ext 只保留第一个(最佳)
    - 标记 has_audio(音视频已合并) vs video_only(需 ffmpeg 合并音频)
    """
    import re

    def parse_height(resolution: str) -> int:
        m = re.search(r'(\d+)x(\d+)', resolution or '')
        return int(m.group(2)) if m else 0

    seen = set()
    result = []
    for f in formats:
        vcodec = f.get('vcodec', 'none')
        acodec = f.get('acodec', 'none')
        if vcodec == 'none' and acodec == 'none':
            continue
        resolution = f.get('resolution', '')
        ext = f.get('ext', '')
        # 去重:同 resolution+ext 只留第一个
        dedup_key = (resolution, ext)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        has_audio = acodec != 'none'
        # 构造友好标签: "1080p", "720p MP4", "480p MP4 含音频"
        height = parse_height(resolution)
        label = f"{height}p" if height else resolution
        if not has_audio:
            label += " 仅视频"
        result.append({
            'format_id': f.get('format_id'),
            'ext': ext,
            'resolution': resolution,
            'label': label,  # 友好显示名
            'filesize': f.get('filesize') or f.get('filesize_approx'),
            'vcodec': vcodec,
            'acodec': acodec,
            'has_audio': has_audio,
            'url': f.get('url'),
        })
    # 按分辨率降序
    result.sort(key=lambda f: parse_height(f['resolution']), reverse=True)
    return result


def _extract_subtitle_info(info: dict) -> dict:
    """提取字幕信息"""
    subtitles = {}
    for lang, subs in info.get('subtitles', {}).items():
        subtitles[lang] = [{'ext': s.get('ext'), 'url': s.get('url')} for s in subs]
    automatic_captions = {}
    for lang, subs in info.get('automatic_captions', {}).items():
        automatic_captions[lang] = [{'ext': s.get('ext'), 'url': s.get('url')} for s in subs]
    return {'subtitles': subtitles, 'automatic_captions': automatic_captions}


def download_subtitles(url: str, language: str = 'en', output_dir: str = None) -> Optional[str]:
    """
    下载字幕文件
    返回: 字幕文件路径,失败返回 None
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="vds_sub_")

    ydl_opts: dict = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'srt',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'impersonate': 'chrome',
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    if language and language.lower() not in ('auto', 'all', ''):
        ydl_opts['subtitleslangs'] = [language]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # 查找下载的字幕文件
        for f in Path(output_dir).glob(f'*.{language}.srt'):
            return str(f)
        # 如果没有找到,尝试任何 srt 文件
        for f in Path(output_dir).glob('*.srt'):
            return str(f)
    except Exception as e:
        print(f"Subtitle download error: {e}")
    finally:
        # 清理临时目录
        shutil.rmtree(output_dir, ignore_errors=True)
    return None


async def extract_video_info_async(url: str) -> dict:
    """异步解析视频信息(在线程池中执行)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_video_info, url)


async def download_subtitles_async(url: str, language: str = 'en') -> Optional[str]:
    """异步下载字幕"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, download_subtitles, url, language)


def download_video_to_temp(url: str, format_id: str) -> Optional[str]:
    """
    下载视频到临时目录,返回文件路径。调用方负责清理临时文件。

    format_id 支持:
    - 具体 id(如 "137"):下载该精确格式
    - "best":自动选最佳视频 + 最佳音频,用 ffmpeg 合并为 mp4(需 ffmpeg)
    """
    output_dir = tempfile.mkdtemp(prefix="vds_vid_")

    if format_id == "best":
        # 最佳质量:视频流 + 音频流,ffmpeg 合并
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        }
    else:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': format_id,
            'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # 找下载的文件(优先 mp4)
        for ext in ['mp4', 'webm', 'mkv', 'flv']:
            for f in Path(output_dir).glob(f'*.{ext}'):
                if f.is_file():
                    return str(f)
        # fallback:任意文件
        for f in Path(output_dir).glob('*.*'):
            if f.is_file():
                return str(f)
        return None
    except Exception as e:
        print(f"Video download error: {e}")
        shutil.rmtree(output_dir, ignore_errors=True)
        return None


async def download_video_to_temp_async(url: str, format_id: str) -> Optional[str]:
    """异步下载视频到临时目录"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, download_video_to_temp, url, format_id)


def _parse_srt_to_text(srt_content: str) -> str:
    """
    将 SRT 字幕内容解析为纯文本。
    去掉序号行、时间戳行(-->)、空行,只保留台词文本。
    """
    lines = srt_content.splitlines()
    text_lines = []
    for line in lines:
        stripped = line.strip()
        # 跳过空行
        if not stripped:
            continue
        # 跳过序号行(纯数字)
        if stripped.isdigit():
            continue
        # 跳过时间戳行(含 -->)
        if '-->' in stripped:
            continue
        text_lines.append(stripped)
    return '\n'.join(text_lines)


def download_subtitles_text(url: str, language: str = 'en') -> Optional[str]:
    """
    下载字幕并返回纯文本内容。
    返回: 字幕纯文本(SRT 已解析),失败返回 None。
    language="auto" 时不指定语言,下载所有可用字幕。
    """
    output_dir = tempfile.mkdtemp(prefix="vds_sub_")

    ydl_opts: dict = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'srt',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        # 绕过 YouTube 反爬:使用 impersonate + 客户端伪装
        'impersonate': 'chrome',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
    }
    # 只有指定了具体语言时才过滤;auto/空 → 下载所有可用字幕
    if language and language.lower() not in ('auto', 'all', ''):
        ydl_opts['subtitleslangs'] = [language]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 查找下载的字幕文件(优先精确匹配语言code)
        srt_path = None
        for f in Path(output_dir).glob(f'*.{language}.srt'):
            srt_path = f
            break
        if srt_path is None:
            for f in Path(output_dir).glob('*.srt'):
                srt_path = f
                break

        if srt_path is None:
            return None

        # 返回原始 SRT 内容(前端负责解析和展示)
        return srt_path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"Subtitle download/parse error: {e}")
        return None
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


async def download_subtitles_text_async(url: str, language: str = 'en') -> Optional[str]:
    """异步下载字幕并返回纯文本内容。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, download_subtitles_text, url, language)


async def translate_srt_async(srt_content: str, target_language: str) -> str:
    """调用 LLM 翻译 SRT 字幕。"""
    import json
    from app.config import get_settings
    from app.config.router import get_route
    from app.prompts.templates import get_prompt, build_messages
    from app.services.llm_client import LLMClient

    settings = get_settings()
    prompt = get_prompt("v1_translate")
    messages = build_messages(prompt, title="", transcript=srt_content, language=target_language)
    llm = LLMClient(settings.OPENROUTER_API_KEY)
    route = get_route(target_language)
    result = ""
    async for raw in llm.stream_with_fallback(messages, route, request=None):
        # 解析 OpenAI 兼容的 SSE chunk
        try:
            data = json.loads(raw)
            delta = data.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                result += content
        except (json.JSONDecodeError, KeyError):
            result += raw
    return result


async def translate_srt_async(srt_content: str, target_language: str) -> str:
    """调用 LLM 翻译 SRT 字幕。"""
    import json
    from app.config import get_settings
    from app.config.router import get_route
    from app.prompts.templates import get_prompt, build_messages
    from app.services.llm_client import LLMClient

    settings = get_settings()
    prompt = get_prompt("v1_translate")
    messages = build_messages(prompt, title="", transcript=srt_content, language=target_language)
    llm = LLMClient(settings.OPENROUTER_API_KEY)
    route = get_route(target_language)
    result = ""
    async for raw in llm.stream_with_fallback(messages, route, request=None):
        # 解析 OpenAI 兼容的 SSE chunk
        try:
            data = json.loads(raw)
            delta = data.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                result += content
        except (json.JSONDecodeError, KeyError):
            result += raw
    return result
