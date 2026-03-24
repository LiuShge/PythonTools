"""HEAD helper built on top of the shared urllib core."""

from __future__ import annotations

from typing import Any

from _core import Response, request

__all__ = ["RequestHead", "head"]


class RequestHead:
    """Namespace for HEAD requests."""

    @staticmethod
    def head(
        url: str,
        params: Any = None,
        headers: Any = None,
        *,
        timeout: float | None = None,
        encoding: str = "utf-8",
        opener: Any = None,
        context: Any = None,
        raise_for_status: bool = False,
    ) -> Response:
        """Send a HEAD request."""

        return request(
            "HEAD",
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            encoding=encoding,
            opener=opener,
            context=context,
            raise_for_status=raise_for_status,
        )


head = RequestHead.head
