"""通用工具：文本处理。

包含 OCR 后处理、语言检测、字数统计、句子切分以及演示引擎所需的
轻量文本分析能力（关键词、摘要、示例翻译）。
"""

from __future__ import annotations

import math
import re
from collections import Counter

# 控制字符（保留换行与制表符）
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE_RE = re.compile(r"[ \t\u3000]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_SENTENCE_END = "。！？!?；;….．"
_CLAUSE_END = _SENTENCE_END + "，,、：:）)》】\"'"

#: 中英文停用词（演示引擎使用，覆盖常见虚词）
STOPWORDS: set[str] = {
    "的", "了", "和", "是", "在", "我", "有", "就", "不", "人", "都", "一", "一个", "上", "也",
    "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
    "与", "及", "或", "而", "被", "把", "对", "从", "为", "以", "于", "中", "等", "将", "并",
    "可以", "进行", "通过", "我们", "他们", "它", "这个", "那个", "以及", "但是", "因为",
    "所以", "如果", "已经", "还是", "这些", "那些", "什么", "怎么", "如何", "一个", "一种",
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "been", "being", "it", "this", "that", "these", "those", "as", "at",
    "by", "from", "has", "have", "had", "not", "no", "you", "we", "they", "he", "she", "i",
    "can", "will", "would", "should", "could", "do", "does", "did", "so", "if", "then", "than",
    "there", "their", "our", "your", "its", "into", "about", "more", "most", "such", "also",
}

#: 演示翻译词典（仅用于无密钥时展示流程，不追求翻译质量）
_DEMO_DICTIONARY = {
    "software": "软件",
    "engineering": "工程",
    "requirements": "需求",
    "design": "设计",
    "development": "开发",
    "testing": "测试",
    "system": "系统",
    "application": "应用",
    "analysis": "分析",
    "project": "项目",
    "team": "团队",
    "user": "用户",
    "data": "数据",
    "document": "文档",
    "quality": "质量",
    "model": "模型",
    "interface": "接口",
    "service": "服务",
    "image": "图像",
    "text": "文本",
    "language": "语言",
    "translation": "翻译",
    "summary": "摘要",
    "keyword": "关键词",
    "workflow": "工作流",
    "performance": "性能",
    "security": "安全",
    "batch": "批量",
    "history": "历史",
    "export": "导出",
}


def clean_text(text: str | None) -> str:
    """基础清洗：去控制字符、统一空白、压缩空行。"""

    if not text:
        return ""
    value = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    value = _CONTROL_RE.sub("", value)
    value = _MULTI_SPACE_RE.sub(" ", value)
    value = "\n".join(line.strip() for line in value.split("\n"))
    value = _MULTI_NEWLINE_RE.sub("\n\n", value)
    return value.strip()


def merge_soft_wraps(text: str) -> str:
    """合并 OCR 结果中的"软换行"。

    OCR 常把同一段落按视觉宽度切成多行。规则：
    * 空行视为段落分隔，保留；
    * 上一行以句末标点 / 冒号 / 右括号结尾时保留换行；
    * 下一行以列表符号、编号、标题符号开头时保留换行；
    * 其余情况把下一行接到上一行（中文直接拼接，英文补空格）。
    """

    lines = clean_text(text).split("\n")
    merged: list[str] = []
    list_prefix = re.compile(r"^(\d+[.、)]|[•·▪◦\-*]|[一二三四五六七八九十]+[、.]|第[一二三四五六七八九十]+[章节])")
    heading_prefix = re.compile(r"^(#{1,6}\s|【|\[)")

    for line in lines:
        if not line:
            merged.append("")
            continue
        if not merged or not merged[-1]:
            merged.append(line)
            continue
        previous = merged[-1]
        if previous.endswith(tuple(_SENTENCE_END)) or previous.endswith((":", "：", ")", "）", "】")):
            merged.append(line)
            continue
        if list_prefix.match(line) or heading_prefix.match(line):
            merged.append(line)
            continue
        if previous.endswith("-"):
            merged[-1] = previous[:-1] + line
            continue

        previous_length = len(re.sub(r"\s", "", previous))

        # 短行通常是标题、署名或独立信息，保留换行以免结构被破坏
        if previous_length < 12 and not previous.endswith(("，", ",", "、", "：", ":")):
            merged.append(line)
            continue

        # 仅当上一行明显是"被宽度截断的正文"时才合并
        should_merge = (
            previous.endswith(("，", ",", "、", "：", ":", "（", "("))
            or previous_length >= 24
            or bool(re.match(r"[a-z]", line))
        )
        if not should_merge:
            merged.append(line)
            continue

        needs_space = bool(re.search(r"[A-Za-z0-9,]$", previous)) and bool(re.match(r"[A-Za-z0-9]", line))
        merged[-1] = previous + (" " if needs_space else "") + line

    return "\n".join(merged).strip()


def paragraphize(text: str, max_chars: int = 800) -> str:
    """按句号与长度切分段落，便于阅读与导出。"""

    value = clean_text(text)
    if len(value) <= max_chars:
        return value
    sentences = split_sentences(value)
    paragraphs: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(buffer) + len(sentence) > max_chars and buffer:
            paragraphs.append(buffer.strip())
            buffer = sentence
        else:
            buffer += sentence
    if buffer.strip():
        paragraphs.append(buffer.strip())
    return "\n\n".join(paragraphs)


def split_sentences(text: str) -> list[str]:
    """中英文混合句子切分（保留标点）。"""

    if not text:
        return []
    pattern = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
    return [match.group(0).strip() for match in pattern.finditer(text) if match.group(0).strip()]


def count_chars(text: str | None) -> int:
    """统计有效字符数（不含空白）。"""

    if not text:
        return 0
    return len(re.sub(r"\s", "", text))


def detect_language(text: str | None) -> str:
    """粗略判断语言：``zh`` / ``en`` / ``mixed`` / ``unknown``。"""

    if not text:
        return "unknown"
    cjk = len(_CJK_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if cjk == 0 and latin == 0:
        return "unknown"
    if cjk and latin and min(cjk, latin) / max(cjk, latin) > 0.1:
        return "mixed"
    return "zh" if cjk >= latin else "en"


def truncate(text: str | None, limit: int = 120, suffix: str = "…") -> str:
    """截断文本用于列表摘要。"""

    if not text:
        return ""
    value = re.sub(r"\s+", " ", text).strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + suffix


def slugify(text: str, fallback: str = "untitled", limit: int = 48) -> str:
    """生成安全的文件名片段（保留中文与字母数字）。"""

    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (text or "").strip(), flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return (value[:limit] or fallback)


def csv_safe(value: str | None) -> str:
    """防止 CSV 公式注入：对 ``= + - @`` 开头的值加单引号前缀。"""

    if not value:
        return ""
    if value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def strip_markdown(text: str) -> str:
    """移除常见 Markdown 标记，用于导出纯文本。"""

    value = re.sub(r"```.*?```", "", text or "", flags=re.DOTALL)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"!\[[^\]]*]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]*)]\([^)]*\)", r"\1", value)
    value = re.sub(r"^#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^[>*+-]\s+", "", value, flags=re.MULTILINE)
    return clean_text(value)


def word_frequency(text: str, limit: int = 12) -> list[tuple[str, int]]:
    """基于词频与简单 n-gram 的关键词提取（演示引擎使用）。

    中文按 2–4 字滑窗统计并过滤停用词，英文按单词统计。
    """

    value = clean_text(text)
    counter: Counter[str] = Counter()

    for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", value.lower()):
        if word not in STOPWORDS and len(word) > 2:
            counter[word] += 1

    segments = re.findall(r"[\u4e00-\u9fff]+", value)
    for segment in segments:
        for size in (2, 3, 4):
            for index in range(0, max(0, len(segment) - size + 1)):
                token = segment[index : index + size]
                if token in STOPWORDS:
                    continue
                if any(token in stop for stop in STOPWORDS if len(stop) >= 2):
                    continue
                counter[token] += 1

    # 去除被更长高频词包含的短词，减少冗余
    ranked = counter.most_common(limit * 4)
    filtered: list[tuple[str, int]] = []
    for token, count in ranked:
        if count < 2:
            continue
        if any(token != other and token in other and count <= other_count for other, other_count in filtered):
            continue
        filtered.append((token, count))
        if len(filtered) >= limit:
            break
    return filtered


def extractive_summary(text: str, max_sentences: int = 5) -> str:
    """抽取式摘要：按句子位置与关键词密度打分。"""

    sentences = [s for s in split_sentences(clean_text(text)) if len(s) >= 8]
    if not sentences:
        return truncate(text, 200)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    frequencies = Counter()
    for sentence in sentences:
        for word, count in word_frequency(sentence, limit=20):
            frequencies[word] += count

    scored: list[tuple[float, int, str]] = []
    total = len(sentences)
    for index, sentence in enumerate(sentences):
        score = sum(frequencies[word] for word, _ in word_frequency(sentence, limit=20))
        score = score / math.sqrt(max(1, len(sentence)))
        # 开头与结尾的句子通常更重要
        if index < 2:
            score *= 1.25
        if index == total - 1:
            score *= 1.1
        scored.append((score, index, sentence))

    best = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    best.sort(key=lambda item: item[1])
    return " ".join(item[2] for item in best)


def demo_translate(text: str, target: str = "en") -> str:
    """演示翻译：英译中按词典替换，中译英输出结构化占位结果。

    该函数仅用于没有配置大模型密钥时的流程演示，界面会明确标注"演示结果"。
    """

    source = clean_text(text)
    if target.lower().startswith("zh"):
        def replace(match: re.Match[str]) -> str:
            word = match.group(0)
            return _DEMO_DICTIONARY.get(word.lower(), word)

        translated = re.sub(r"[A-Za-z]+", replace, source)
        return f"【演示翻译·英译中】\n{translated}"

    lines = []
    for sentence in split_sentences(source)[:20]:
        lines.append(f"[DEMO] {sentence}")
    return "【演示翻译·中译英】\n" + "\n".join(lines)


def demo_answer(question: str, context: str) -> str:
    """演示问答：在原文中检索与问题最相关的句子并组织回答。"""

    question_terms = {term for term, _ in word_frequency(question, limit=8)}
    question_terms.update(re.findall(r"[\u4e00-\u9fff]{2,4}", question))
    candidates = []
    for sentence in split_sentences(clean_text(context)):
        hits = sum(1 for term in question_terms if term and term in sentence)
        if hits:
            candidates.append((hits, len(sentence), sentence))
    if not candidates:
        return "【演示问答】原文中未找到与问题直接相关的内容，请尝试更换问法，或配置大模型以获得更好的回答。"
    candidates.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    picked = [item[2] for item in candidates[:3]]
    return "【演示问答】根据原文，可能的答案如下：\n\n" + "\n".join(f"- {item}" for item in picked)
