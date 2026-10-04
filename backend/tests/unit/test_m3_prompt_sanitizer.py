"""M3-05 PromptCompiler + OutputSanitizer 单元测试。"""
import pytest

from cyberwife.application.prompt_compiler import PromptCompiler, PromptBudget, estimate_tokens
from cyberwife.application.output_sanitizer import (
    OutputSanitizer,
    remove_markdown,
    remove_emoji,
    remove_action_brackets,
)


# ── PromptCompiler ────────────────────────────────────────────────────
class TestPromptCompiler:
    def test_basic_compile(self):
        c = PromptCompiler()
        p = c.compile(
            profile={"name": "小芸", "relationship": "亲密伴侣", "persona": "温柔、健谈", "relationship_context": "已经相处三年"},
            user_input="今天过得怎么样？",
        )
        assert "小芸" in p.system
        assert "温柔" in p.system
        assert p.user_input == "今天过得怎么样？"
        assert p.total_tokens() < 4096

    def test_profile_clamped_to_budget(self):
        c = PromptCompiler()
        long_persona = "温柔、" * 1000  # 3000 字符 ≈ 1500 tokens（超过 600 token 预算）
        p = c.compile(
            profile={"name": "X", "persona": long_persona},
        )
        # persona 应被截断到 profile_max_tokens * 2 = 1200 字符 + "..."
        assert "..." in p.system
        # system 全量 token 仍 ≤ max_context_tokens
        assert p.total_tokens() <= 4096

    def test_memory_clamp_by_score(self):
        c = PromptCompiler()
        p = c.compile(
            profile={"name": "X"},
            memories=[
                ("低分记忆", 0.1),  # 应被阈值过滤
                ("高分记忆", 0.9),  # 保留
            ],
        )
        assert "高分记忆" in p.memories
        assert "低分记忆" not in p.memories

    def test_history_truncation_by_budget(self):
        c = PromptCompiler(PromptBudget(max_context_tokens=200))
        p = c.compile(
            profile={"name": "X", "persona": ""},
            history=[
                {"role": "user", "text": "a" * 500},
                {"role": "user", "text": "b" * 500},
                {"role": "user", "text": "c" * 500},
            ],
            user_input="Q",
        )
        assert p.total_tokens() <= 200 + 50  # 留 buffer

    def test_chatml_format(self):
        c = PromptCompiler()
        p = c.compile(
            profile={"name": "小芸", "relationship": "伴侣"},
            history=[{"role": "user", "text": "你好"}, {"role": "assistant", "text": "嗯嗯"}],
            user_input="今天呢？",
        )
        ml = c.to_chatml(p)
        assert ml.startswith("<|im_start|>system")
        assert "<|im_end|>" in ml
        assert "<|im_start|>user\n你好<|im_end|>" in ml
        assert "<|im_start|>assistant\n嗯嗯<|im_end|>" in ml
        assert ml.endswith("<|im_start|>assistant\n")


# ── OutputSanitizer ────────────────────────────────────────────────────
class TestOutputSanitizer:
    def test_chinese_text_is_not_mistaken_for_emoji(self):
        assert OutputSanitizer().clean("是呀，很适合聊聊天。") == "是呀，很适合聊聊天。"

    def test_reasoning_blocks_never_reach_spoken_text(self):
        sanitizer = OutputSanitizer()
        assert sanitizer.clean("<think>内部推理</think>你好呀。") == "你好呀。"
        assert sanitizer.clean("<think>还没有闭合的内部推理") == ""

    def test_clean_removes_markdown_bold(self):
        assert remove_markdown("**hello** world") == "hello world"

    def test_clean_removes_markdown_italic(self):
        assert remove_markdown("*hi* there") == "hi there"

    def test_clean_removes_markdown_heading(self):
        assert remove_markdown("## Title\nbody").strip() == "Title\nbody"

    def test_clean_removes_markdown_code(self):
        assert remove_markdown("Use `print()` here") == "Use print() here"

    def test_clean_removes_markdown_link(self):
        assert remove_markdown("[click](http://x)") == "click"

    def test_clean_removes_action_brackets(self):
        assert remove_action_brackets("你好*微笑*（挥手）[开心]") == "你好"

    def test_clean_removes_emoji(self):
        assert remove_emoji("hello 😀 world") == "hello  world"

    def test_clean_removes_chatml_residue(self):
        assert "<|im_start|>" not in OutputSanitizer().clean("<|im_start|>system hi<|im_end|>")

    def test_clean_collapses_whitespace(self):
        s = OutputSanitizer()
        assert s.clean("a\n\n\nb   c") == "a b c"

    def test_clean_full_pipeline(self):
        s = OutputSanitizer()
        out = s.clean("**你好** *微笑*（挥手）\n## 标题\n`code` [link](url)")
        assert "**" not in out
        assert "*" not in out
        assert "（" not in out
        assert "#" not in out
        assert "`" not in out
        assert "[" not in out

    def test_split_sentences_chinese(self):
        s = OutputSanitizer()
        out = s.split("你好。今天怎么样？我很好。")
        assert out == ["你好。", "今天怎么样？", "我很好。"]

    def test_split_preserves_question_and_exclamation(self):
        s = OutputSanitizer()
        out = s.split("真的吗？太好了！")
        assert out == ["真的吗？", "太好了！"]


# ── estimate_tokens ──────────────────────────────────────────────────
class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_short(self):
        assert estimate_tokens("hi") == 1

    def test_long(self):
        t = estimate_tokens("a" * 100)
        assert t == 50
