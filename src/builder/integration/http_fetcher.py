"""Production HTTPFetcher using stdlib urllib (no third-party HTTP client)."""
from __future__ import annotations

import urllib.request


DEFAULT_USER_AGENT = "matter-expert-builder/0.0.1"
DEFAULT_TIMEOUT_SECONDS = 30


class UrllibFetcher:
    """Fetch a URL and return the decoded text body."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._user_agent = user_agent
        self._timeout = timeout

    def fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self._user_agent},
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            data: bytes = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace")
