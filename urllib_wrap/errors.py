"""Error hierarchy for :mod:`urllib-wrap`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from _core import Response

__all__ = [
    "UrllibWrapError",
    "RequestBuildError",
    "SerializationError",
    "TransportError",
    "URLError",
    "ContentTooShortError",
    "HTTPError",
    "ResponseDecodeError",
    "CompressionError",
]


class UrllibWrapError(Exception):
    """Base class for every exception raised by this wrapper."""


class RequestBuildError(UrllibWrapError):
    """Raised when request arguments cannot be normalized."""


class SerializationError(RequestBuildError):
    """Raised when request payload serialization fails."""


class CompressionError(RequestBuildError):
    """Raised when compression or decompression fails."""


class TransportError(UrllibWrapError):
    """Base class for transport-level failures."""


class URLError(TransportError):
    """Normalized wrapper for :class:`urllib.error.URLError`."""

    def __init__(self, reason: Any, url: str | None = None, original: Exception | None = None):
        self.reason = reason
        self.url = url
        self.original = original
        message = str(reason)
        if url:
            message = f"{message} ({url})"
        super().__init__(message)


class ContentTooShortError(TransportError):
    """Normalized wrapper for :class:`urllib.error.ContentTooShortError`."""

    def __init__(self, content: Any, original: Exception | None = None):
        self.content = content
        self.original = original
        super().__init__("downloaded content is shorter than expected")


class HTTPError(TransportError):
    """HTTP status failure enriched with the parsed response."""

    def __init__(self, response: Response, original: Exception | None = None):
        self.response = response
        self.original = original
        self.status_code = response.status_code
        self.reason = response.reason
        self.url = response.url
        self.headers = response.headers
        message = f"HTTP {self.status_code}"
        if self.reason:
            message += f" {self.reason}"
        if self.url:
            message += f" for {self.url}"
        super().__init__(message)

    @classmethod
    def from_response(cls, response: Response, original: Exception | None = None) -> "HTTPError":
        return cls(response, original=original)


class ResponseDecodeError(UrllibWrapError):
    """Raised when a strict text or JSON decode cannot be completed."""

    def __init__(self, message: str, response: Response | None = None, original: Exception | None = None):
        self.response = response
        self.original = original
        super().__init__(message)
