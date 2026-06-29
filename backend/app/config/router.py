"""OpenRouter AI 总结模块 - 路由配置

使用单一模型: openrouter/owl-alpha
"""

from dataclasses import dataclass


@dataclass
class RouteRule:
    primary: str
    fallbacks: list[str]
    max_tokens: int = 4096
    temperature: float = 0.7


MODEL = "openrouter/owl-alpha"

ROUTING_TABLE: dict[str, RouteRule] = {
    "zh": RouteRule(primary=MODEL, fallbacks=[], max_tokens=4096),
    "zh-CN": RouteRule(primary=MODEL, fallbacks=[], max_tokens=4096),
    "en": RouteRule(primary=MODEL, fallbacks=[], max_tokens=4096),
    "ja": RouteRule(primary=MODEL, fallbacks=[], max_tokens=4096),
    "default": RouteRule(primary=MODEL, fallbacks=[], max_tokens=4096),
}


def get_route(language: str) -> RouteRule:
    """根据语言代码获取路由规则,找不到则返回 default。"""
    return ROUTING_TABLE.get(language, ROUTING_TABLE["default"])
