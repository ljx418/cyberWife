"""M3-04 LLM adapter smoke（不启动 llama-server，测 HTTP 错误处理）。"""
import socket
import pytest
from unittest.mock import patch, MagicMock

from cyberwife.adapters.llama_cpp_adapter import LlamaCppAdapter


class TestLlamaHealth:
    @pytest.mark.parametrize("host", ["example.com", "8.8.8.8", "192.168.1.9"])
    def test_non_loopback_endpoint_is_rejected(self, host):
        with pytest.raises(ValueError, match="loopback"):
            LlamaCppAdapter(host=host)

    def test_health_when_server_down(self):
        # Never assume the product's real 8090 service is down during a full
        # target-machine regression. Reserve then release an ephemeral port.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            unused_port = sock.getsockname()[1]
        adapter = LlamaCppAdapter(host="127.0.0.1", port=unused_port)
        h = adapter.health()
        assert h["status"] == "error"
        assert "error" in h

    def test_health_endpoint_format(self):
        adapter = LlamaCppAdapter()
        assert adapter._base == "http://127.0.0.1:8090"


class TestLlamaCancel:
    def test_cancel_unknown_returns_false(self):
        adapter = LlamaCppAdapter()
        assert adapter.cancel("nonexistent") is False

    def test_cancel_active_returns_true(self):
        adapter = LlamaCppAdapter()
        fake_resp = MagicMock()
        adapter._inflight["test-id"] = fake_resp
        assert adapter.cancel("test-id") is True
        assert "test-id" not in adapter._inflight
        fake_resp.close.assert_called_once()


class TestLlamaGenerateBlocking:
    """HTTP mock 测 generate_blocking 不实际启动 llama-server。"""

    @patch("cyberwife.adapters.llama_cpp_adapter.httpx.post")
    def test_blocking_extracts_content(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": "你好，世界"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        adapter = LlamaCppAdapter()
        out = adapter.generate_blocking("测试 prompt", max_tokens=64)
        assert out == "你好，世界"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "completion" in call_args.args[0]
        assert call_args.kwargs["json"]["prompt"] == "测试 prompt"
