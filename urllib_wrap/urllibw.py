"""Single-file urllib wrapper exposing common HTTP verbs and unified errors.

Exports:
    - request, get, post, put, delete, head, patch, options
    - Response type
    - error hierarchy: HTTPError, URLError, ContentTooShortError, RequestBuildError,
      SerializationError, CompressionError, ResponseDecodeError, UrllibWrapError
"""

from __future__ import annotations

import gzip
import json as _json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, overload

# =========================
# Error hierarchy
# =========================

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

    def __init__(self, response: "Response", original: Exception | None = None):
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
    def from_response(cls, response: "Response", original: Exception | None = None) -> "HTTPError":
        return cls(response, original=original)


class ResponseDecodeError(UrllibWrapError):
    """Raised when a strict text or JSON decode cannot be completed."""

    def __init__(self, message: str, response: "Response" | None = None, original: Exception | None = None):
        self.response = response
        self.original = original
        super().__init__(message)


# =========================
# Helpers
# =========================

def _normalize_headers(headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None) -> dict[str, str]:
    if not headers:
        return {}
    items = headers.items() if isinstance(headers, Mapping) else headers
    return {str(k): str(v) for k, v in items}


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if key.casefold() == target:
            return value
    return None


def _content_type(headers: Mapping[str, str]) -> str | None:
    value = _get_header(headers, "Content-Type")
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower()


def _charset_from_content_type(headers: Mapping[str, str]) -> str | None:
    value = _get_header(headers, "Content-Type")
    if not value:
        return None
    match = re.search(r"charset=([^;]+)", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().strip('"').strip("'")
    return None


def _looks_json(raw: bytes) -> bool:
    sample = raw.lstrip()
    return sample.startswith(b"{") or sample.startswith(b"[")


def _looks_textual(raw: bytes) -> bool:
    sample = raw[:512]
    if not sample:
        return True
    if b"\x00" in sample:
        return False
    control = sum(1 for byte in sample if byte < 32 and byte not in (9, 10, 13))
    return control <= max(1, len(sample) // 10)


def _decompress(raw: bytes, encoding: str | None) -> bytes:
    if not encoding:
        return raw
    encodings = [part.strip().lower() for part in encoding.split(",") if part.strip()]
    payload = raw
    for item in encodings:
        if item in {"gzip", "x-gzip"}:
            try:
                payload = gzip.decompress(payload)
            except Exception as exc:
                raise CompressionError(f"failed to decompress gzip payload: {exc}") from exc
        elif item == "deflate":
            try:
                payload = zlib.decompress(payload)
            except zlib.error:
                try:
                    payload = zlib.decompress(payload, -zlib.MAX_WBITS)
                except Exception as exc:
                    raise CompressionError(f"failed to decompress deflate payload: {exc}") from exc
        else:
            return raw
    return payload


def _auto_parse(raw: bytes, headers: Mapping[str, str], default_encoding: str) -> tuple[Any, bytes, str | None, str | None]:
    content_encoding = _get_header(headers, "Content-Encoding")
    content_type = _content_type(headers)
    charset = _charset_from_content_type(headers) or default_encoding

    payload = raw
    if content_encoding:
        try:
            payload = _decompress(payload, content_encoding)
        except CompressionError:
            payload = raw
    elif len(payload) >= 2 and payload[:2] == b"\x1f\x8b":
        try:
            payload = gzip.decompress(payload)
            content_encoding = "gzip"
        except Exception:
            payload = raw

    if not payload:
        return None, payload, charset, content_type

    textual_types = {
        "application/json",
        "application/javascript",
        "application/xml",
        "application/x-www-form-urlencoded",
        "application/xhtml+xml",
    }

    if content_type in textual_types or (content_type and content_type.endswith("+json")):
        try:
            return _json.loads(payload.decode(charset)), payload, charset, content_type
        except Exception:
            pass

    if _looks_json(payload):
        try:
            return _json.loads(payload.decode(charset)), payload, charset, content_type
        except Exception:
            pass

    if content_type and content_type.startswith("text/"):
        try:
            return payload.decode(charset), payload, charset, content_type
        except Exception:
            pass

    if _looks_textual(payload):
        try:
            return payload.decode(charset), payload, charset, content_type
        except Exception:
            try:
                return payload.decode("utf-8"), payload, "utf-8", content_type
            except Exception:
                pass

    return payload, payload, charset, content_type


def _encode_params(params: Mapping[str, Any] | Sequence[tuple[str, Any]] | str | bytes | None, encoding: str) -> str | None:
    if params is None:
        return None
    if isinstance(params, bytes):
        return params.decode(encoding, errors="ignore")
    if isinstance(params, str):
        return params[1:] if params.startswith("?") else params
    return urllib.parse.urlencode(params, doseq=True)


def _merge_url(url: str, params: Mapping[str, Any] | Sequence[tuple[str, Any]] | str | bytes | None, encoding: str) -> str:
    query = _encode_params(params, encoding)
    if not query:
        return url
    parsed = urllib.parse.urlsplit(url)
    combined = "&".join(part for part in [parsed.query, query] if part)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, combined, parsed.fragment))


def _serialize_body(
    data: Any,
    json_data: Any,
    headers: dict[str, str],
    encoding: str,
    compress: str | None,
    compress_level: int,
) -> bytes | None:
    if data is None and json_data is None:
        return None

    if json_data is not None:
        try:
            payload = _json.dumps(json_data, ensure_ascii=False, separators=(",", ":")).encode(encoding)
        except Exception as exc:
            raise SerializationError(f"failed to serialize json payload: {exc}") from exc
        headers.setdefault("Content-Type", f"application/json; charset={encoding}")
    elif isinstance(data, bytes):
        payload = data
    elif isinstance(data, (bytearray, memoryview)):
        payload = bytes(data)
    elif isinstance(data, str):
        payload = data.encode(encoding)
    elif isinstance(data, (Mapping, Sequence)):
        try:
            payload = urllib.parse.urlencode(data, doseq=True).encode(encoding)
        except Exception as exc:
            raise SerializationError(f"failed to serialize form payload: {exc}") from exc
        headers.setdefault("Content-Type", f"application/x-www-form-urlencoded; charset={encoding}")
    else:
        try:
            payload = _json.dumps(data, ensure_ascii=False).encode(encoding)
        except Exception as exc:
            raise SerializationError(f"unsupported payload type: {type(data).__name__}") from exc
        headers.setdefault("Content-Type", f"application/json; charset={encoding}")

    selected = (compress or _get_header(headers, "Content-Encoding") or "").strip().lower()
    if selected in {"gzip", "x-gzip"}:
        try:
            payload = gzip.compress(payload, compresslevel=compress_level)
        except Exception as exc:
            raise CompressionError(f"failed to gzip-compress payload: {exc}") from exc
        headers["Content-Encoding"] = "gzip"
    elif selected:
        raise CompressionError(f"unsupported compression type: {selected}")

    return payload


def _read_source(source: Any) -> tuple[bytes, int, str | None, dict[str, str], str]:
    raw = source.read() if hasattr(source, "read") else b""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw)

    status = int(getattr(source, "status", getattr(source, "code", 200)))
    reason = getattr(source, "reason", getattr(source, "msg", None))
    reason = str(reason) if reason is not None else None
    headers_obj = getattr(source, "headers", getattr(source, "header", {}))
    headers = {str(k): str(v) for k, v in headers_obj.items()} if hasattr(headers_obj, "items") else _normalize_headers(headers_obj)
    url = getattr(source, "geturl", lambda: getattr(source, "url", ""))()
    return bytes(raw), status, reason, headers, str(url)


# =========================
# Response type
# =========================

@dataclass(slots=True)
class Response:
    method: str
    url: str
    status_code: int
    reason: str | None
    headers: dict[str, str]
    raw: bytes
    data: Any
    request_headers: dict[str, str]
    charset: str | None
    content_type: str | None
    content_encoding: str | None

    @property
    def status(self) -> int:
        return self.status_code

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def __bool__(self) -> bool:
        return self.ok

    def __len__(self) -> int:
        return len(self.raw)

    def __bytes__(self) -> bytes:
        return self.raw

    def __repr__(self) -> str:
        return f"Response(status={self.status_code}, url={self.url!r}, body_type={type(self.data).__name__})"

    def __str__(self) -> str:
        if isinstance(self.data, str):
            return self.data
        return self.text()

    def text(self, encoding: str | None = None, errors: str = "replace") -> str:
        if isinstance(self.data, str) and encoding is None:
            return self.data
        chosen = encoding or self.charset or "utf-8"
        try:
            return self.raw.decode(chosen, errors=errors)
        except Exception as exc:
            raise ResponseDecodeError(f"failed to decode response body using {chosen}", response=self, original=exc) from exc

    def json(self) -> Any:
        if isinstance(self.data, (dict, list)):
            return self.data
        candidate = self.data if isinstance(self.data, str) else self.text()
        try:
            return _json.loads(candidate)
        except Exception as exc:
            raise ResponseDecodeError("response body is not valid JSON", response=self, original=exc) from exc

    def raise_for_status(self) -> None:
        if not self.ok:
            raise HTTPError(self)


# =========================
# Core request
# =========================

def request(
    method: str,
    url: str,
    *,
    params: Mapping[str, Any] | Sequence[tuple[str, Any]] | str | bytes | None = None,
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
    data: Any = None,
    json: Any = None,
    timeout: float | None = None,
    encoding: str = "utf-8",
    compress: str | None = None,
    compress_level: int = 9,
    opener: urllib.request.OpenerDirector | None = None,
    context: ssl.SSLContext | None = None,
    raise_for_status: bool = False,
) -> Response:
    method = method.upper()
    request_headers = _normalize_headers(headers)
    final_url = _merge_url(url, params, encoding)
    body = _serialize_body(data, json, request_headers, encoding, compress, compress_level)
    req = urllib.request.Request(final_url, data=body, headers=request_headers, method=method)

    try:
        if opener is not None:
            source = opener.open(req, timeout=timeout)
        elif context is not None:
            source = urllib.request.urlopen(req, timeout=timeout, context=context)
        else:
            source = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = _build_response(method, exc, request_headers)
        if raise_for_status:
            raise HTTPError(response, original=exc) from exc
        return response
    except urllib.error.URLError as exc:
        raise URLError(getattr(exc, "reason", exc), url=final_url, original=exc) from exc
    except urllib.error.ContentTooShortError as exc:
        raise ContentTooShortError(getattr(exc, "content", None), original=exc) from exc

    response = _build_response(method, source, request_headers)
    if raise_for_status and not response.ok:
        raise HTTPError(response)
    return response


def _build_response(method: str, source: Any, request_headers: dict[str, str]) -> Response:
    raw, status, reason, headers, url = _read_source(source)
    data, payload, charset, content_type = _auto_parse(raw, headers, "utf-8")
    content_encoding = _get_header(headers, "Content-Encoding")
    return Response(
        method=method,
        url=url,
        status_code=status,
        reason=reason,
        headers=headers,
        raw=payload,
        data=data,
        request_headers=request_headers,
        charset=charset,
        content_type=content_type,
        content_encoding=content_encoding,
    )


# =========================
# Rollup helpers with flexible args
# =========================

_QUERY_METHODS = {"GET", "HEAD", "OPTIONS"}
_OPTION_KEYS = {"timeout", "encoding", "compress", "compress_level", "opener", "context", "raise_for_status"}


def _normalize_args(method: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    method = method.upper()
    params = kwargs.pop("params", None)
    headers = kwargs.pop("headers", None)
    data = kwargs.pop("data", None)
    json_data = kwargs.pop("json", None)
    options = {key: kwargs.pop(key) for key in list(kwargs.keys()) if key in _OPTION_KEYS}

    if kwargs:
        raise RequestBuildError(f"unexpected keyword arguments: {', '.join(sorted(kwargs))}")
    if len(args) > 2:
        raise RequestBuildError("at most two positional arguments are supported after url")

    if len(args) == 2:
        primary, extra_headers = args
        if method in _QUERY_METHODS and params is None:
            params = primary
        elif data is None and json_data is None:
            data = primary
        else:
            raise RequestBuildError("positional arguments conflict with explicit payload arguments")
        if headers is None:
            headers = extra_headers
        else:
            raise RequestBuildError("headers were provided both positionally and by keyword")
    elif len(args) == 1:
        primary = args[0]
        if method in _QUERY_METHODS and params is None:
            params = primary
        elif method in _QUERY_METHODS and headers is None:
            headers = primary
        elif data is None and json_data is None:
            data = primary
        elif headers is None:
            headers = primary
        else:
            raise RequestBuildError("positional argument conflicts with explicit arguments")

    return params, headers, data, json_data, options


def _options_to_kwargs(options: dict[str, Any]) -> dict[str, Any]:
    return {
        "timeout": options.get("timeout"),
        "encoding": options.get("encoding", "utf-8"),
        "compress": options.get("compress"),
        "compress_level": options.get("compress_level", 9),
        "opener": options.get("opener"),
        "context": options.get("context"),
        "raise_for_status": options.get("raise_for_status", False),
    }


# ========================
# Public verbs
# ========================

@overload
def get(url: str, /) -> Response: ...
@overload
def get(url: str, params: Any, /) -> Response: ...
@overload
def get(url: str, params: Any, headers: Any, /) -> Response: ...
def get(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, _, _, options = _normalize_args("GET", args, kwargs)
    opts = _options_to_kwargs(options)
    return request("GET", url, params=params, headers=headers, **opts)


@overload
def post(url: str, /) -> Response: ...
@overload
def post(url: str, data: Any, /) -> Response: ...
@overload
def post(url: str, data: Any, headers: Any, /) -> Response: ...
def post(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("POST", args, kwargs)
    opts = _options_to_kwargs(options)
    return request("POST", url, params=params, headers=headers, data=data, json=json_data, **opts)


@overload
def put(url: str, /) -> Response: ...
@overload
def put(url: str, data: Any, /) -> Response: ...
@overload
def put(url: str, data: Any, headers: Any, /) -> Response: ...
def put(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("PUT", args, kwargs)
    opts = _options_to_kwargs(options)
    return request("PUT", url, params=params, headers=headers, data=data, json=json_data, **opts)


@overload
def delete(url: str, /) -> Response: ...
@overload
def delete(url: str, data: Any, /) -> Response: ...
@overload
def delete(url: str, data: Any, headers: Any, /) -> Response: ...
def delete(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("DELETE", args, kwargs)
    opts = _options_to_kwargs(options)
    return request("DELETE", url, params=params, headers=headers, data=data, json=json_data, **opts)


@overload
def head(url: str, /) -> Response: ...
@overload
def head(url: str, params: Any, /) -> Response: ...
@overload
def head(url: str, params: Any, headers: Any, /) -> Response: ...
def head(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, _, _, options = _normalize_args("HEAD", args, kwargs)
    opts = _options_to_kwargs(options)
    return request("HEAD", url, params=params, headers=headers, **opts)


@overload
def patch(url: str, /) -> Response: ...
@overload
def patch(url: str, data: Any, /) -> Response: ...
@overload
def patch(url: str, data: Any, headers: Any, /) -> Response: ...
def patch(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("PATCH", args, kwargs)
    opts = _options_to_kwargs(options)
    return request("PATCH", url, params=params, headers=headers, data=data, json=json_data, **opts)


@overload
def options(url: str, /) -> Response: ...
@overload
def options(url: str, params: Any, /) -> Response: ...
@overload
def options(url: str, params: Any, headers: Any, /) -> Response: ...
def options(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, _, _, options_kwargs = _normalize_args("OPTIONS", args, kwargs)
    opts = _options_to_kwargs(options_kwargs)
    return request("OPTIONS", url, params=params, headers=headers, **opts)


__all__ = [
    "request",
    "get",
    "post",
    "put",
    "delete",
    "head",
    "patch",
    "options",
    "Response",
    "HTTPError",
    "URLError",
    "ContentTooShortError",
    "RequestBuildError",
    "SerializationError",
    "CompressionError",
    "ResponseDecodeError",
    "UrllibWrapError",
]
