"""OutputSanitizer — M3-05 LLM 输出清洗。

按 implementation-contracts §5 第 5 步 + §6 reply.text.final payload：
- 移除 Markdown（** * # ` 等）
- 移除 emoji（基本 unicode 范围）
- 移除动作括号（*微笑*、（挥手） 等）
- 移除 LLM 异常 marker（如 "<|im_start|>" 残留）
- 按语义切句（实现-contracts §5 第 6 步）
"""
from __future__ import annotations

import re
from typing import List


# Markdown 字符：粗体/斜体/标题/列表/代码/链接/图片
# 每个模式保留 capture group 用于替换；非删除类用 \1 替换
_MARKDOWN_PATTERNS = [
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),                  # **bold** → bold
    (re.compile(r"\*([^*]+)\*"), r"\1"),                       # *italic* → italic
    (re.compile(r"^#{1,6}\s*", re.MULTILINE), ""),              # # heading → 删除
    (re.compile(r"`([^`]+)`"), r"\1"),                          # `code` → code
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),               # [text](url) → text
    (re.compile(r"!\[([^\]]*)\]\([^)]+\)"), r"\1"),              # ![alt](url) → alt
    (re.compile(r"^\s*[-*]\s+", re.MULTILINE), ""),             # - list / * list → 删除
    (re.compile(r"^\s*\d+\.\s+", re.MULTILINE), ""),             # 1. list → 删除
]

# 动作括号：中文/英文 方括号/星号/圆括号 内容（1-20 字）
_ACTION_BRACKETS = [
    re.compile(r"\*[^*]{1,20}\*"),          # *微笑*
    re.compile(r"\([^)]{1,20}\)"),         # (挥手)
    re.compile(r"（[^）]{1,20}）"),       # （微笑）
    re.compile(r"\[[^\]]{1,20}\]"),        # [笑]
]

# emoji（基本 unicode emoji 范围）
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA70-\U0001FAFF"  # extended symbols
    "\u2600-\u26FF"          # miscellaneous symbols
    "\u2700-\u27BF"          # dingbats
    "]+",
    flags=re.UNICODE,
)

# ChatML 残留 marker
_CHATML_RESIDUE = re.compile(r"<\|im_(?:start|end)\|>")
_REASONING_BLOCK = re.compile(r"<(?:think|analysis)>.*?</(?:think|analysis)>", re.DOTALL | re.IGNORECASE)
_UNCLOSED_REASONING = re.compile(r"<(?:think|analysis)>.*$", re.DOTALL | re.IGNORECASE)
_REASONING_TAG = re.compile(r"</?(?:think|analysis)>", re.IGNORECASE)


def remove_markdown(text: str) -> str:
    """移除 Markdown 标记；保留文本内容。"""
    for pat, repl in _MARKDOWN_PATTERNS:
        text = pat.sub(repl, text)
    return text


def remove_action_brackets(text: str) -> str:
    """移除 *微笑*、 (挥手) 等动作括号。"""
    for pat in _ACTION_BRACKETS:
        text = pat.sub("", text)
    return text


def remove_emoji(text: str) -> str:
    return _EMOJI_PATTERN.sub("", text)


def remove_chatml_residue(text: str) -> str:
    text = _REASONING_BLOCK.sub("", text)
    text = _UNCLOSED_REASONING.sub("", text)
    text = _REASONING_TAG.sub("", text)
    return _CHATML_RESIDUE.sub("", text)


def split_sentences(text: str) -> List[str]:
    """按中文/英文/日文句号、问号、感叹号切句；保留标点。"""
    # 在标点后切分；保留逗号
    parts = re.split(r"(?<=[。！？!?])\s*", text)
    return [p.strip() for p in parts if p.strip()]


class OutputSanitizer:
    """LLM 输出清洗 + 切句。"""

    def clean(self, text: str) -> str:
        """完整清洗：去除 Markdown / emoji / 动作括号 / ChatML 残留。"""
        text = remove_chatml_residue(text)
        text = remove_markdown(text)
        text = remove_emoji(text)
        text = remove_action_brackets(text)
        # 多余空白折叠
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def split(self, text: str) -> List[str]:
        return split_sentences(text)
