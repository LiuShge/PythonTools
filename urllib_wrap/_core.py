"""Internal request/response primitives for :mod:`urllib-wrap`."""

from __future__ import annotations

import gzip
import json as jsonlib
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from errors import CompressionError, ContentTooShortError, HTTPError, RequestBuildError, ResponseDecodeError, SerializationError, URLError

__all__ = ["Response", "request", "normalize_headers"]

_TEXTUAL_TYPES = {
    "application/json",
    "application/javascript",
    "application/xml",
    "application/x-www-form-urlencoded",
    "application/xhtml+xml",
}


def normalize_headers(headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None) -> dict[str, str]:
    """Return a plain string dictionary suitable for ``urllib`` requests."""

    if not headers:
        return {}
    if isinstance(headers, Mapping):
        items = headers.items()
    else:
        items = headers
    normalized: dict[str, str] = {}
    for key, value in items:
        normalized[str(key)] = str(value)
    return normalized


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

    if content_type in _TEXTUAL_TYPES or (content_type and content_type.endswith("+json")):
        try:
            return jsonlib.loads(payload.decode(charset)), payload, charset, content_type
        except Exception:
            pass

    if _looks_json(payload):
        try:
            return jsonlib.loads(payload.decode(charset)), payload, charset, content_type
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

    payload: bytes
    if json_data is not None:
        try:
            payload = jsonlib.dumps(json_data, ensure_ascii=False, separators=(",", ":")).encode(encoding)
        except Exception as exc:
            raise SerializationError(f"failed to serialize json payload: {exc}") from exc
        headers.setdefault("Content-Type", f"application/json; charset={encoding}")
    elif isinstance(data, bytes):
        payload = data
    elif isinstance(data, bytearray | memoryview):
        payload = bytes(data)
    elif isinstance(data, str):
        payload = data.encode(encoding)
    elif isinstance(data, Mapping | Sequence):
        try:
            payload = urllib.parse.urlencode(data, doseq=True).encode(encoding)
        except Exception as exc:
            raise SerializationError(f"failed to serialize form payload: {exc}") from exc
        headers.setdefault("Content-Type", f"application/x-www-form-urlencoded; charset={encoding}")
    else:
        try:
            payload = jsonlib.dumps(data, ensure_ascii=False).encode(encoding)
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


@dataclass(slots=True)
class Response:
    """A parsed HTTP response.

    The raw bytes are available on :attr:`raw`, while :attr:`data` contains the
    best-effort decoded payload. Use :meth:`json` or :meth:`text` for strict
    extraction when needed.
    """

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
    def content(self) -> bytes:
        return self.raw

    @property
    def body(self) -> Any:
        return self.data

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
        """Return the payload as text."""

        if isinstance(self.data, str) and encoding is None:
            return self.data
        chosen = encoding or self.charset or "utf-8"
        try:
            return self.raw.decode(chosen, errors=errors)
        except Exception as exc:
            raise ResponseDecodeError(f"failed to decode response body using {chosen}", response=self, original=exc) from exc

    def json(self) -> Any:
        """Return the payload parsed as JSON."""

        if isinstance(self.data, (dict, list)):
            return self.data
        if isinstance(self.data, str):
            candidate = self.data
        else:
            candidate = self.text()
        try:
            return jsonlib.loads(candidate)
        except Exception as exc:
            raise ResponseDecodeError("response body is not valid JSON", response=self, original=exc) from exc

    def raise_for_status(self) -> None:
        """Raise :class:`errors.HTTPError` for non-2xx/3xx responses."""

        if not self.ok:
            raise HTTPError(self)


def _read_source(source: Any) -> tuple[bytes, int, str | None, dict[str, str], str]:
    if hasattr(source, "read"):
        raw = source.read()
    else:
        raw = b""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw)

    status = int(getattr(source, "status", getattr(source, "code", 200)))
    reason = getattr(source, "reason", getattr(source, "msg", None))
    if reason is not None:
        reason = str(reason)
    headers_obj = getattr(source, "headers", getattr(source, "header", {}))
    if hasattr(headers_obj, "items"):
        headers = {str(key): str(value) for key, value in headers_obj.items()}
    else:
        headers = normalize_headers(headers_obj)
    url = getattr(source, "geturl", lambda: getattr(source, "url", ""))()
    return bytes(raw), status, reason, headers, str(url)


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
    """Execute a request and return a parsed :class:`Response`."""

    method = method.upper()
    request_headers = normalize_headers(headers)
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
