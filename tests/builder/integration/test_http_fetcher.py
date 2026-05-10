from unittest.mock import patch, MagicMock

import pytest

from builder.integration.http_fetcher import UrllibFetcher


def test_fetcher_returns_response_body():
    fake_response = MagicMock()
    fake_response.read.return_value = b"<html>body</html>"
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None
    fake_response.headers.get_content_charset.return_value = "utf-8"

    with patch("builder.integration.http_fetcher.urllib.request.urlopen",
                return_value=fake_response):
        f = UrllibFetcher()
        text = f.fetch("https://example.com/x")
    assert text == "<html>body</html>"


def test_fetcher_handles_non_utf8():
    fake = MagicMock()
    fake.read.return_value = "héllo".encode("latin-1")
    fake.__enter__ = lambda s: s
    fake.__exit__ = lambda *a: None
    fake.headers.get_content_charset.return_value = "latin-1"

    with patch("builder.integration.http_fetcher.urllib.request.urlopen",
                return_value=fake):
        f = UrllibFetcher()
        text = f.fetch("https://x")
    assert text == "héllo"


def test_fetcher_uses_default_user_agent():
    """Requests include a User-Agent header (some servers reject default Python UA)."""
    fake_response = MagicMock()
    fake_response.read.return_value = b"ok"
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None
    fake_response.headers.get_content_charset.return_value = "utf-8"

    captured = {}
    def capture_open(req, **kw):
        captured["headers"] = dict(req.headers)
        return fake_response

    with patch("builder.integration.http_fetcher.urllib.request.urlopen",
                side_effect=capture_open):
        UrllibFetcher().fetch("https://x")

    assert any("User-agent" in k or "User-Agent" in k for k in captured["headers"])
