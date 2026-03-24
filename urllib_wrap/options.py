"""OPTIONS helper built on top of the shared urllib core."""

from __future__ import annotations

from typing import Any

from _core import Response, request

__all__ = ["RequestOptions", "options"]


class RequestOptions:
    """Namespace for OPTIONS requests."""

    @staticmethod
    def options(
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
        """Send an OPTIONS request."""

        return request(
            "OPTIONS",
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            encoding=encoding,
            opener=opener,
            context=context,
            raise_for_status=raise_for_status,
        )


options = RequestOptions.options
