"""PromptCompiler — M3-05 prompt 拼装。

按 implementation-contracts §6 Prompt 预算：
- 注入上下文总 token 上限 4096（默认）
- Profile 段 ≤ 600 token
- 短期会话摘要 3 条 × ≤300 token
- 向量召回 top-k=4 × 阈值 0.55
- FTS top-k=6
- 记忆预算总 token ≤ 800

M3 阶段：仅做 prompt 拼装与 token 估算（不实际调 BGE）；真实嵌入留 M3-stretch。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# 字符粗估 token：中文 ~1.5 char/token，英文 ~4 char/token
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # 简化：1 字符 ≈ 0.5 token
    return max(1, len(text) // 2)


@dataclass
class PromptBudget:
    max_context_tokens: int = 4096
    profile_max_tokens: int = 600
    short_term_count: int = 3
    short_term_max_tokens: int = 300
    vector_top_k: int = 4
    vector_score_min: float = 0.55
    fts_top_k: int = 6
    memory_budget_tokens: int = 800

    def clamp_profile(self, text: str) -> str:
        if estimate_tokens(text) <= self.profile_max_tokens:
            return text
        # 截断
        limit_chars = self.profile_max_tokens * 2
        return text[:limit_chars] + "..."

    def clamp_memory(self, memories: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """memories: [(content, score), ...]；按 score 排序后裁剪到 token 预算。"""
        sorted_mems = sorted(memories, key=lambda x: -x[1])
        result = []
        used = 0
        for content, score in sorted_mems:
            t = estimate_tokens(content)
            if used + t > self.memory_budget_tokens:
                continue
            if score < self.vector_score_min:
                continue
            result.append((content, score))
            used += t
            if len(result) >= self.vector_top_k + self.fts_top_k:
                break
        return result


@dataclass
class CompiledPrompt:
    system: str
    history: str = ""
    memories: str = ""
    user_input: str = ""
    estimated_tokens: int = 0

    def total_tokens(self) -> int:
        return (
            estimate_tokens(self.system)
            + estimate_tokens(self.history)
            + estimate_tokens(self.memories)
            + estimate_tokens(self.user_input)
        )


class PromptCompiler:
    """Qwen3 Instruct ChatML 格式 prompt 拼装。"""

    SYSTEM_PROMPT_TEMPLATE = (
        "你是{character_name}，用户的{relationship}。\n"
        "性格关键词：{persona}\n"
        "你与用户的关系背景：{relationship_context}\n"
        "直接回应用户，不复述问题，不展示思考、推理过程或任何think标签。\n"
        "每次只回复一句完整自然的短句，总共不超过十八个汉字；使用日常口语，不使用 Markdown、列表、emoji 或动作括号。\n"
        "数字使用中文表达；你仅使用简体中文回复。\n"
        "/no_think"
    )

    def __init__(self, budget: Optional[PromptBudget] = None) -> None:
        self._budget = budget or PromptBudget()

    def compile(
        self,
        *,
        profile: dict,
        history: list[dict] | None = None,
        memories: list[tuple[str, float]] | None = None,
        user_input: str = "",
    ) -> CompiledPrompt:
        """拼装 prompt。

        profile = {name, user_nickname, persona, relationship_context, ...}
        history = [{"role": "user"|"assistant", "text": "..."}, ...]
        memories = [(content, score), ...] 已通过 FTS + 向量检索
        """
        # 1. system
        profile_clamped = {
            **profile,
            "persona": self._budget.clamp_profile(profile.get("persona", "")),
            "relationship_context": self._budget.clamp_profile(profile.get("relationship_context", "")),
        }
        system = self.SYSTEM_PROMPT_TEMPLATE.format(
            character_name=profile_clamped.get("name", "数字伴侣"),
            relationship=profile_clamped.get("relationship", "亲密伙伴"),
            persona=profile_clamped.get("persona", ""),
            relationship_context=profile_clamped.get("relationship_context", ""),
        )
        # 2. history（最近 N 条；M3 占位）
        history_text = ""
        if history:
            lines = []
            for h in history[-(self._budget.short_term_count * 2):]:
                role = "用户" if h.get("role") == "user" else "你"
                text = h.get("text", "")
                lines.append(f"{role}：{text}")
            history_text = "\n".join(lines)
        # 3. memories（已裁剪到 budget）
        mem_clamped = self._budget.clamp_memory(memories or [])
        mem_text = ""
        if mem_clamped:
            mem_lines = [f"- {c}" for c, _ in mem_clamped]
            mem_text = "以下是你记得的与用户相关的事实：\n" + "\n".join(mem_lines)
        # 4. 组装 + 校验总 token
        compiled = CompiledPrompt(
            system=system,
            history=history_text,
            memories=mem_text,
            user_input=user_input,
        )
        # 超 budget 截断 history（保留 system + memories + user_input）
        while compiled.total_tokens() > self._budget.max_context_tokens and history:
            history = history[1:]
            history_text = "\n".join(
                f"{'用户' if h.get('role') == 'user' else '你'}：{h.get('text', '')}"
                for h in history[-(self._budget.short_term_count * 2):]
            )
            compiled.history = history_text
        compiled.estimated_tokens = compiled.total_tokens()
        return compiled

    def to_chatml(self, compiled: CompiledPrompt) -> str:
        """Qwen3 Instruct ChatML：<|im_start|>system ... <|im_end|> 等。"""
        parts = []
        if compiled.system:
            parts.append(f"<|im_start|>system\n{compiled.system}<|im_end|>")
        if compiled.memories:
            parts.append(f"<|im_start|>system\n{compiled.memories}<|im_end|>")
        if compiled.history:
            for line in compiled.history.split("\n"):
                if line.startswith("用户："):
                    parts.append(f"<|im_start|>user\n{line[len('用户：'):]}<|im_end|>")
                elif line.startswith("你："):
                    parts.append(f"<|im_start|>assistant\n{line[len('你：'):]}<|im_end|>")
        if compiled.user_input:
            parts.append(f"<|im_start|>user\n{compiled.user_input}\n/no_think<|im_end|>")
        # 末尾：等待 assistant
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)
