"""Prompt 模板管理。

当前版本: v1
- 视频内容总结
- 支持多语言输出
- Markdown 格式
"""
from dataclasses import dataclass


@dataclass
class PromptTemplate:
    version: str
    system: str
    user: str
    max_output_tokens: int = 2000


PROMPT_VERSIONS: dict[str, PromptTemplate] = {
    "v1": PromptTemplate(
        version="v1",
        system="""你是一个专业的视频内容总结助手。
输出语言：{language}
输出格式：Markdown
输出长度：300-500 字
要求：提炼核心观点，分点列出关键信息，给出结论。""",
        user="""请总结以下视频内容：

标题：{title}

转录文本：
{transcript}

请用 {language} 输出总结。""",
        max_output_tokens=2000,
    ),
    "v1_qa": PromptTemplate(
        version="v1_qa",
        system="""你是一个视频内容问答助手。
输出语言：{language}
要求：基于提供的视频转录文本回答用户问题，回答简洁准确，若文本中无相关信息请如实说明。""",
        user="""以下是视频的转录文本：

{transcript}

用户问题：
{question}

请用 {language} 回答。""",
        max_output_tokens=1024,
    ),
    "v1_translate": PromptTemplate(
        version="v1_translate",
        system="""你是一个专业字幕翻译助手。
目标语言：{language}
要求：将输入的 SRT 字幕翻译为目标语言，保留原始时间戳和序号格式，只翻译文本内容。
输出格式：与输入相同的 SRT 格式（序号+时间戳+翻译后文本）。""",
        user="""请将以下 SRT 字幕翻译为 {language}：

{transcript}

只输出 SRT 格式译文，不要解释。""",
        max_output_tokens=4000,
    ),
}


def get_prompt(version: str = "v1") -> PromptTemplate:
    """获取指定版本的 Prompt 模板,不存在则回退到 v1。"""
    return PROMPT_VERSIONS.get(version, PROMPT_VERSIONS["v1"])


def build_messages(
    template: PromptTemplate,
    title: str,
    transcript: str,
    language: str,
    question: str = "",
) -> list[dict]:
    """把模板 + 变量组装成 OpenAI 风格的 messages。"""
    user_content = template.user.format(
        title=title,
        transcript=transcript,
        language=language,
        question=question,
    )
    return [
        {"role": "system", "content": template.system.format(language=language)},
        {"role": "user", "content": user_content},
    ]
