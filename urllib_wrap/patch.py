"""PATCH helper built on top of the shared urllib core."""

from __future__ import annotations

from typing import Any

from _core import Response, request

__all__ = ["RequestPatch", "patch"]


class RequestPatch:
    """Namespace for PATCH requests."""

    @staticmethod
    def patch(
        url: str,
        data: Any = None,
        headers: Any = None,
        *,
        params: Any = None,
        json: Any = None,
        timeout: float | None = None,
        encoding: str = "utf-8",
        compress: str | None = None,
        compress_level: int = 9,
        opener: Any = None,
        context: Any = None,
        raise_for_status: bool = False,
    ) -> Response:
        """Send a PATCH request."""

        return request(
            "PATCH",
            url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
            encoding=encoding,
            compress=compress,
            compress_level=compress_level,
            opener=opener,
            context=context,
            raise_for_status=raise_for_status,
        )


patch = RequestPatch.patch
