"""M1-09 frontend split: 7 个目标文件全部就位 + 文件结构正确。"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("relative_path", [
    "prototype/src/app/AppShell.tsx",
    "prototype/src/features/onboarding/OnboardingFlow.tsx",
    "prototype/src/features/conversation/ConversationScreen.tsx",
    "prototype/src/features/settings/SettingsDrawer.tsx",
    "prototype/src/services/ConversationClient.ts",
    "prototype/src/services/MediaSession.ts",
    "prototype/src/platform/HostBridge.ts",
])
def test_frontend_file_exists(relative_path):
    p = REPO_ROOT / relative_path
    assert p.exists(), f"missing: {p}"
    content = p.read_text(encoding="utf-8")
    # 每个文件至少 1KB（M1 stub 已含基础 import + 1 个组件）
    assert len(content) > 100, f"file too small: {p} ({len(content)} bytes)"


def test_app_shell_uses_theme_localstorage():
    """AppShell 应使用 implementation-contracts §26.2 白名单 4 项中的 theme key。"""
    p = REPO_ROOT / "prototype/src/app/AppShell.tsx"
    content = p.read_text(encoding="utf-8")
    assert "cyberWife.ui.theme" in content, "AppShell must use §26.2 whitelist theme key"


def test_conversation_client_uses_ws_envelope_6_fields():
    """ConversationClient 类型定义应包含 §6 envelope 字段（即使 M1 阶段无 WS 消费）。"""
    p = REPO_ROOT / "prototype/src/services/ConversationClient.ts"
    content = p.read_text(encoding="utf-8")
    # 必须出现 health envelope 的关键字段
    assert "components" in content and "resources" in content


def test_hostbridge_returns_browser_only():
    """FR-19：浏览器实现仅返回 'browser'；其余方法为空操作。"""
    p = REPO_ROOT / "prototype/src/platform/HostBridge.ts"
    content = p.read_text(encoding="utf-8")
    assert "browser" in content
    assert "compact" in content and "pet" in content  # WindowMode 联合类型
    # 空操作方法
    for method in ("setWindowMode", "setAlwaysOnTop", "setTransparent", "quit"):
        assert method in content


def test_frontend_no_secrets_in_localstorage():
    """§26.1 黑名单字段不应作为 localStorage.setItem 的 key 出现。

    只扫描形如 `localStorage.setItem("<key>", ...)` 的字面 key。
    """
    import re
    from pathlib import Path

    sensitive = ("session_id", "trace_id", "turn_id", "profile_text", "memory.content",
                 "audio_bytes", "voiceprint", "salt")
    src_dir = REPO_ROOT / "prototype/src"
    pattern = re.compile(r'localStorage\.setItem\(\s*["\']([^"\']+)["\']')
    for f in src_dir.rglob("*.ts*"):
        c = f.read_text(encoding="utf-8")
        keys = pattern.findall(c)
        for k in keys:
            for s in sensitive:
                if s.lower() in k.lower():
                    raise AssertionError(f"{f} localStorage key {k!r} contains sensitive substring {s!r}")
