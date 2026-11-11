"""AI 演示引擎。

在没有配置大模型密钥时，使用确定性的本地算法完成翻译、摘要、
关键词、问答与润色，保证功能流程可以完整演示。

所有输出均带有「演示」标记，避免与真实模型结果混淆。
"""

from __future__ import annotations

import time

from ...utils.text import (
    clean_text,
    demo_answer,
    demo_translate,
    extractive_summary,
    split_sentences,
    truncate,
    word_frequency,
)
from ..base import AIProvider, AIResult, ChatMessage


class MockAIProvider(AIProvider):
    name = "mock"
    label = "演示引擎（无需密钥）"
    description = "内置的本地文本处理引擎：词典翻译、抽取式摘要、词频关键词，用于无密钥演示。"
    requires_credentials = False
    models = ("demo-local",)

    def available(self, settings: dict) -> tuple[bool, str]:
        return True, "内置引擎，始终可用"

    # ------------------------------------------------------------------
    def process(
        self,
        action: str,
        text: str,
        system_prompt: str,
        user_prompt: str,
        settings: dict,
        *,
        model: str | None = None,
        options: dict | None = None,
    ) -> AIResult:
        started = time.perf_counter()
        options = options or {}
        source = clean_text(text)

        if action == "translate":
            output = demo_translate(source, str(options.get("target_language", "en")))
        elif action == "summarize":
            summary = extractive_summary(source, max_sentences=5)
            output = f"【演示摘要】\n一句话总述：{truncate(summary, 90)}\n\n要点：\n" + "\n".join(
                f"- {sentence}" for sentence in split_sentences(summary)[:6]
            )
        elif action == "keywords":
            count = int(options.get("count") or 10)
            keywords = word_frequency(source, limit=count)
            if keywords:
                reasons = ["出现频率高", "主题相关", "语义集中", "专有表达", "结构关键"]
                output = "【演示关键词】\n" + "\n".join(
                    f"- {word}（{reasons[index % len(reasons)]}，出现 {freq} 次）"
                    for index, (word, freq) in enumerate(keywords)
                )
            else:
                output = "【演示关键词】原文较短，未提取到稳定的关键词。"
        elif action == "qa":
            output = demo_answer(str(options.get("question") or ""), source)
        elif action == "polish":
            polished = (
                source.replace("然后", "随后")
                .replace("但是", "然而")
                .replace("非常", "较为")
                .replace("好多", "许多")
            )
            output = f"【演示润色】\n{polished}"
        elif action == "outline":
            limit = int(options.get("count") or 6)
            sentences = split_sentences(source)[:limit]
            output = "【演示提纲】\n" + "\n".join(
                f"{index + 1}. {truncate(sentence, 40)}" for index, sentence in enumerate(sentences)
            )
        else:
            output = f"【演示结果】\n{truncate(source, 600)}"

        elapsed = (time.perf_counter() - started) * 1000
        return AIResult(
            text=output,
            provider=self.name,
            model="demo-local",
            tokens_in=max(1, len(source) // 2),
            tokens_out=max(1, len(output) // 2),
            latency_ms=round(elapsed, 1),
            meta={
                "demo": True,
                "notice": "当前使用演示引擎，结果由本地规则生成。配置大模型密钥后可获得更高质量的结果。",
                "action": action,
            },
        )

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[ChatMessage],
        settings: dict,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResult:
        started = time.perf_counter()
        user_messages = [message.content for message in messages if message.role == "user"]
        question = user_messages[-1] if user_messages else ""
        context = "\n".join(message.content for message in messages if message.role != "user")
        answer = demo_answer(question, context)
        elapsed = (time.perf_counter() - started) * 1000
        return AIResult(
            text=answer,
            provider=self.name,
            model="demo-local",
            tokens_in=max(1, len(question) // 2),
            tokens_out=max(1, len(answer) // 2),
            latency_ms=round(elapsed, 1),
            meta={"demo": True, "notice": "演示对话：回答基于原文句子检索，未调用真实模型。"},
        )


provider = MockAIProvider()
