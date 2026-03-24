# urllib-wrap

`urllib_wrap` is a lightweight wrapper on top of Python's `urllib`, now condensed into a single implementation file `urllibw.py` while keeping the public API unchanged.

## Features

- Seven HTTP verbs implemented in separate files: `get`, `post`, `put`, `delete`, `head`, `patch`, and `options`.
- A robust `_core.py` handles request normalization, compression, JSON detection, and response parsing.
- `rollup.py` overloads the helpers and supports positional and keyword argument styles without unnecessary `Optional`s.
- Automatic gzip/deflate decompression plus text/JSON detection for responses.
- Centralized error hierarchy in `errors.py`.
- No third-party dependencies; pure standard library.

## Usage

```python
import urllibw

resp = urllibw.get("https://httpbin.org/json")
print(resp.status)
print(resp.data)
```

Or import only what you need:

```python
from urllibw import post, HTTPError
```

## Parameter Styles

`rollup.py` accepts the following forms:

```python
get(url)
get(url, params)
get(url, params, headers)
get(url, params=params, headers=headers)

post(url, data)
post(url, data, headers)
post(url, data=data, json={"a": 1}, headers=headers)
post(url, params={"q": 1}, json={"a": 1})
```

## Response API

- `response.status`
- `response.ok`
- `response.headers`
- `response.raw`
- `response.data`
- `response.text()`
- `response.json()`
- `response.raise_for_status()`

## Errors (`errors.py`)

- `HTTPError`
- `URLError`
- `ContentTooShortError`
- `RequestBuildError`
- `SerializationError`
- `CompressionError`
- `ResponseDecodeError`

## Repository Structure

```
urllib_wrap/
  urllibw.py   # single-file implementation and public API
  README.md
```

## Notes

- `urllibw.py` now contains transport plumbing, verb helpers, overloads, and the error hierarchy in one place.
