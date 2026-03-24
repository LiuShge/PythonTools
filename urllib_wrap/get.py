"""GET helper built on top of the shared urllib core."""

from __future__ import annotations

from typing import Any

from _core import Response, request

__all__ = ["RequestGet", "get"]


class RequestGet:
    """Namespace for GET requests."""

    @staticmethod
    def get(
        url: str,
        params: Any = None,
        headers: Any = None,
        *,
        timeout: float | None = None,
        encoding: str = "utf-8",
        compress: str | None = None,
        compress_level: int = 9,
        opener: Any = None,
        context: Any = None,
        raise_for_status: bool = False,
    ) -> Response:
        """Send a GET request."""

        return request(
            "GET",
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            encoding=encoding,
            compress=compress,
            compress_level=compress_level,
            opener=opener,
            context=context,
            raise_for_status=raise_for_status,
        )


get = RequestGet.get
