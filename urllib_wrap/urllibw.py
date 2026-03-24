"""Public entry point for urllib-wrap.

Import this module to get the full API surface:

* request helpers: ``get``, ``post``, ``put``, ``delete``, ``head``, ``patch``, ``options``
* transport helper: ``request``
* response type: ``Response``
* error hierarchy: everything from :mod:`errors`
"""

from __future__ import annotations

from errors import *  # noqa: F401,F403
from errors import __all__ as _error_all
from _core import Response
from rollup import *  # noqa: F401,F403
from rollup import __all__ as _rollup_all

__all__ = ["Response", *_rollup_all, *_error_all]
