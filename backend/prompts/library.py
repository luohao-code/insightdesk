"""提示词库。

集中管理所有 AI 动作的提示词，便于统一调整与版本化。
变量使用 ``{{variable}}`` 占位，避免与 JSON、代码块中的花括号冲突。
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 单次送入模型的最大字符数，超出部分在服务层截断
MAX_INPUT_CHARS = 12000

_SAFETY_RULES = (
    "你必须严格依据用户提供的原文作答，不得编造原文中不存在的事实。"
    "如果原文信息不足，请明确说明，而不是猜测。"
)

_LANGUAGE_LABELS = {
    "zh": "简体中文",
    "zh-tw": "繁体中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
}


@dataclass(slots=True)
class PromptSpec:
    """一个 AI 动作的提示词定义。"""

    action: str
    label: str
    description: str
    system: str
    template: str
    options: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class PromptBundle:
    """构建完成的提示词。"""

    action: str
    system: str
    user: str
    truncated: bool = False

    @property
    def rendered(self) -> str:
        return f"[system]\n{self.system}\n\n[user]\n{self.user}"


_SPECS: dict[str, PromptSpec] = {
    "translate": PromptSpec(
        action="translate",
        label="翻译",
        description="将原文翻译为目标语言，保留段落与专业术语。",
        system=(
            "你是一位专业翻译，擅长中英日韩等多语种互译，熟悉计算机、工程与学术写作。"
            "翻译要求：忠实原意、术语准确、语句通顺、保留原文的段落结构与列表格式；"
            "不添加解释、不输出原文之外的内容。"
            f"{_SAFETY_RULES}"
        ),
        template=(
            "请将下面的文本翻译为{{target_language}}。\n"
            "风格要求：{{tone}}。\n\n"
            "原文：\n\"\"\"\n{{text}}\n\"\"\"\n\n"
            "只输出译文。"
        ),
        options=("target_language", "tone"),
    ),
    "summarize": PromptSpec(
        action="summarize",
        label="摘要",
        description="提炼核心观点，输出结构化摘要。",
        system=(
            "你是一位严谨的信息分析员，擅长从长文本中提炼结构化的要点。"
            "摘要必须忠于原文，不引入外部知识，不使用夸张表述。"
            f"{_SAFETY_RULES}"
        ),
        template=(
            "请为下面的文本生成摘要，长度要求：{{length}}。\n"
            "输出格式：先给出一句话总述，再用 3–6 条要点列出关键信息；"
            "如有重要数字、时间、结论，请保留。\n\n"
            "原文：\n\"\"\"\n{{text}}\n\"\"\""
        ),
        options=("length",),
    ),
    "keywords": PromptSpec(
        action="keywords",
        label="关键词",
        description="提取主题词与专有名词，便于归档检索。",
        system=(
            "你是一位信息检索专家，擅长提取文本的主题词、专有名词与技术术语。"
            "关键词应具有区分度，避免提取无意义的通用词。"
        ),
        template=(
            "请从下面的文本中提取 {{count}} 个关键词。\n"
            "要求：\n"
            "1. 每个关键词 2–8 个字或 1–3 个英文单词；\n"
            "2. 按重要性从高到低排序；\n"
            "3. 使用 Markdown 无序列表输出，每个关键词后附 6 字以内的理由。\n\n"
            "原文：\n\"\"\"\n{{text}}\n\"\"\""
        ),
        options=("count",),
    ),
    "qa": PromptSpec(
        action="qa",
        label="问答",
        description="基于原文回答问题，答案可溯源。",
        system=(
            "你是一位阅读助手。请仅依据用户提供的原文回答问题，"
            "回答后用「依据」列出所引用的原文片段（可为空）。"
            f"{_SAFETY_RULES}"
        ),
        template=(
            "原文：\n\"\"\"\n{{text}}\n\"\"\"\n\n"
            "问题：{{question}}\n\n"
            "请用简洁的中文回答；若原文无法回答，请直接说明。"
        ),
        options=("question",),
    ),
    "polish": PromptSpec(
        action="polish",
        label="润色",
        description="在不改变原意的前提下优化表达。",
        system=(
            "你是一位中文编辑，擅长在不改变事实与观点的前提下优化表达："
            "消除口语化、修正错别字、调整语序、统一术语。只输出润色后的文本。"
        ),
        template=(
            "请润色下面的文本，风格：{{tone}}。保留原有段落与列表结构。\n\n"
            "原文：\n\"\"\"\n{{text}}\n\"\"\""
        ),
        options=("tone",),
    ),
    "outline": PromptSpec(
        action="outline",
        label="提纲",
        description="把长文本整理为层级提纲。",
        system=(
            "你是一位知识管理专家，擅长把杂乱文本整理为清晰的层级提纲。"
            "提纲层级不超过三级，语言精炼，不添加原文没有的内容。"
        ),
        template=(
            "请把下面的文本整理为 Markdown 层级提纲，最多三级，控制在 {{count}} 个一级条目以内。\n\n"
            "原文：\n\"\"\"\n{{text}}\n\"\"\""
        ),
        options=("count",),
    ),
}


def get_spec(action: str) -> PromptSpec:
    spec = _SPECS.get(action)
    if spec is None:
        raise KeyError(f"未知的 AI 动作：{action}")
    return spec


def list_actions() -> list[dict]:
    return [
        {
            "action": spec.action,
            "label": spec.label,
            "description": spec.description,
            "options": list(spec.options),
        }
        for spec in _SPECS.values()
    ]


def _render(template: str, values: dict[str, object]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def build_prompt(action: str, text: str, options: dict | None = None) -> PromptBundle:
    """构建提示词并做长度保护。

    :param action: 动作标识，见 :data:`_SPECS`
    :param text: 待处理文本
    :param options: 动作选项（目标语言、长度、问题等）
    """

    spec = get_spec(action)
    options = options or {}
    source = (text or "").strip()
    truncated = False
    if len(source) > MAX_INPUT_CHARS:
        source = source[:MAX_INPUT_CHARS] + "\n……（原文过长，已截断）"
        truncated = True

    values: dict[str, object] = {
        "text": source,
        "target_language": _LANGUAGE_LABELS.get(
            str(options.get("target_language", "en")), str(options.get("target_language", "英语"))
        ),
        "tone": options.get("tone") or "正式、准确",
        "length": options.get("length") or "中等（约 200–300 字）",
        "count": options.get("count") or 10,
        "question": options.get("question") or "请概括这段文本的主要内容。",
    }
    user_prompt = _render(spec.template, values)
    return PromptBundle(action=action, system=spec.system, user=user_prompt, truncated=truncated)
