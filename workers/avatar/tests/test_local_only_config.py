"""V1 configuration must not expose upstream cloud services."""

import sys

from config import parse_args


def test_cli_and_yaml_cannot_reenable_external_services(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "tts: edgetts\n"
        "llm_provider: dashscope\n"
        "stun: stun:public.example.test\n"
        "push_url: https://upload.example.test/live\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["avatar", "--config", str(config), "--tts", "doubao"],
    )

    options = parse_args()

    assert options.allow_external_services is False
    assert options.tts == "external"
    assert options.llm_provider == ""
    assert options.stun == ""
    assert options.push_url == ""


def test_external_services_switch_does_not_exist(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["avatar", "--allow-external-services"])
    try:
        parse_args()
    except SystemExit as error:
        assert error.code == 2
    else:  # pragma: no cover - assertion explains the security invariant
        raise AssertionError("external services switch unexpectedly accepted")
