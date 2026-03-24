"""Flexible public API with overloads and argument normalization."""

from __future__ import annotations

from typing import Any, overload

from _core import Response, request as _request
from delete import RequestDelete
from errors import RequestBuildError
from get import RequestGet
from head import RequestHead
from options import RequestOptions
from patch import RequestPatch
from post import RequestPost
from put import RequestPut

__all__ = [
    "request",
    "get",
    "post",
    "put",
    "delete",
    "head",
    "patch",
    "options",
    "Rollup",
]


_BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
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


def request(method: str, url: str, *args: Any, **kwargs: Any) -> Response:
    """Dispatch an arbitrary HTTP method.

    Positional forms:
    - ``request("GET", url, params)``
    - ``request("POST", url, data)``
    - ``request("POST", url, data, headers)``
    """

    params, headers, data, json_data, options = _normalize_args(method, args, kwargs)
    return _request(
        method,
        url,
        params=params,
        headers=headers,
        data=data,
        json=json_data,
        **options,
    )


@overload
def get(url: str, /) -> Response: ...


@overload
def get(url: str, params: Any, /) -> Response: ...


@overload
def get(url: str, params: Any, headers: Any, /) -> Response: ...


@overload
def get(
    url: str,
    /,
    *,
    params: Any = ...,
    headers: Any = ...,
    timeout: float | None = ...,
    encoding: str = ...,
    compress: str | None = ...,
    compress_level: int = ...,
    opener: Any = ...,
    context: Any = ...,
    raise_for_status: bool = ...,
) -> Response: ...


def get(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("GET", args, kwargs)
    return RequestGet.get(url, params=params, headers=headers, timeout=options.get("timeout"), encoding=options.get("encoding", "utf-8"), compress=options.get("compress"), compress_level=options.get("compress_level", 9), opener=options.get("opener"), context=options.get("context"), raise_for_status=options.get("raise_for_status", False))


@overload
def post(url: str, /) -> Response: ...


@overload
def post(url: str, data: Any, /) -> Response: ...


@overload
def post(url: str, data: Any, headers: Any, /) -> Response: ...


@overload
def post(
    url: str,
    /,
    *,
    params: Any = ...,
    headers: Any = ...,
    data: Any = ...,
    json: Any = ...,
    timeout: float | None = ...,
    encoding: str = ...,
    compress: str | None = ...,
    compress_level: int = ...,
    opener: Any = ...,
    context: Any = ...,
    raise_for_status: bool = ...,
) -> Response: ...


def post(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("POST", args, kwargs)
    return RequestPost.post(
        url,
        data=data,
        headers=headers,
        params=params,
        json=json_data,
        timeout=options.get("timeout"),
        encoding=options.get("encoding", "utf-8"),
        compress=options.get("compress"),
        compress_level=options.get("compress_level", 9),
        opener=options.get("opener"),
        context=options.get("context"),
        raise_for_status=options.get("raise_for_status", False),
    )


@overload
def put(url: str, /) -> Response: ...


@overload
def put(url: str, data: Any, /) -> Response: ...


@overload
def put(url: str, data: Any, headers: Any, /) -> Response: ...


@overload
def put(
    url: str,
    /,
    *,
    params: Any = ...,
    headers: Any = ...,
    data: Any = ...,
    json: Any = ...,
    timeout: float | None = ...,
    encoding: str = ...,
    compress: str | None = ...,
    compress_level: int = ...,
    opener: Any = ...,
    context: Any = ...,
    raise_for_status: bool = ...,
) -> Response: ...


def put(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("PUT", args, kwargs)
    return RequestPut.put(
        url,
        data=data,
        headers=headers,
        params=params,
        json=json_data,
        timeout=options.get("timeout"),
        encoding=options.get("encoding", "utf-8"),
        compress=options.get("compress"),
        compress_level=options.get("compress_level", 9),
        opener=options.get("opener"),
        context=options.get("context"),
        raise_for_status=options.get("raise_for_status", False),
    )


@overload
def delete(url: str, /) -> Response: ...


@overload
def delete(url: str, data: Any, /) -> Response: ...


@overload
def delete(url: str, data: Any, headers: Any, /) -> Response: ...


@overload
def delete(
    url: str,
    /,
    *,
    params: Any = ...,
    headers: Any = ...,
    data: Any = ...,
    json: Any = ...,
    timeout: float | None = ...,
    encoding: str = ...,
    compress: str | None = ...,
    compress_level: int = ...,
    opener: Any = ...,
    context: Any = ...,
    raise_for_status: bool = ...,
) -> Response: ...


def delete(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("DELETE", args, kwargs)
    return RequestDelete.delete(
        url,
        data=data,
        headers=headers,
        params=params,
        json=json_data,
        timeout=options.get("timeout"),
        encoding=options.get("encoding", "utf-8"),
        compress=options.get("compress"),
        compress_level=options.get("compress_level", 9),
        opener=options.get("opener"),
        context=options.get("context"),
        raise_for_status=options.get("raise_for_status", False),
    )


@overload
def head(url: str, /) -> Response: ...


@overload
def head(url: str, params: Any, /) -> Response: ...


@overload
def head(url: str, params: Any, headers: Any, /) -> Response: ...


@overload
def head(
    url: str,
    /,
    *,
    params: Any = ...,
    headers: Any = ...,
    timeout: float | None = ...,
    encoding: str = ...,
    opener: Any = ...,
    context: Any = ...,
    raise_for_status: bool = ...,
) -> Response: ...


def head(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, _, _, options = _normalize_args("HEAD", args, kwargs)
    return RequestHead.head(
        url,
        params=params,
        headers=headers,
        timeout=options.get("timeout"),
        encoding=options.get("encoding", "utf-8"),
        opener=options.get("opener"),
        context=options.get("context"),
        raise_for_status=options.get("raise_for_status", False),
    )


@overload
def patch(url: str, /) -> Response: ...


@overload
def patch(url: str, data: Any, /) -> Response: ...


@overload
def patch(url: str, data: Any, headers: Any, /) -> Response: ...


@overload
def patch(
    url: str,
    /,
    *,
    params: Any = ...,
    headers: Any = ...,
    data: Any = ...,
    json: Any = ...,
    timeout: float | None = ...,
    encoding: str = ...,
    compress: str | None = ...,
    compress_level: int = ...,
    opener: Any = ...,
    context: Any = ...,
    raise_for_status: bool = ...,
) -> Response: ...


def patch(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, data, json_data, options = _normalize_args("PATCH", args, kwargs)
    return RequestPatch.patch(
        url,
        data=data,
        headers=headers,
        params=params,
        json=json_data,
        timeout=options.get("timeout"),
        encoding=options.get("encoding", "utf-8"),
        compress=options.get("compress"),
        compress_level=options.get("compress_level", 9),
        opener=options.get("opener"),
        context=options.get("context"),
        raise_for_status=options.get("raise_for_status", False),
    )


@overload
def options(url: str, /) -> Response: ...


@overload
def options(url: str, params: Any, /) -> Response: ...


@overload
def options(url: str, params: Any, headers: Any, /) -> Response: ...


@overload
def options(
    url: str,
    /,
    *,
    params: Any = ...,
    headers: Any = ...,
    timeout: float | None = ...,
    encoding: str = ...,
    opener: Any = ...,
    context: Any = ...,
    raise_for_status: bool = ...,
) -> Response: ...


def options(url: str, *args: Any, **kwargs: Any) -> Response:
    params, headers, _, _, options_kwargs = _normalize_args("OPTIONS", args, kwargs)
    return RequestOptions.options(
        url,
        params=params,
        headers=headers,
        timeout=options_kwargs.get("timeout"),
        encoding=options_kwargs.get("encoding", "utf-8"),
        opener=options_kwargs.get("opener"),
        context=options_kwargs.get("context"),
        raise_for_status=options_kwargs.get("raise_for_status", False),
    )


class Rollup:
    """Convenience namespace mirroring the module-level functions."""

    request = staticmethod(request)
    get = staticmethod(get)
    post = staticmethod(post)
    put = staticmethod(put)
    delete = staticmethod(delete)
    head = staticmethod(head)
    patch = staticmethod(patch)
    options = staticmethod(options)
