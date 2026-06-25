"""Patch slowapi to preserve function signatures for FastAPI compatibility.

slowapi uses functools.wraps but inspect.signature() sees the wrapper's
(*args, **kwargs) signature. FastAPI uses inspect.signature() to determine
endpoint parameters. This patch preserves the original signature.
"""

import inspect
import slowapi.extension

_original_limit = slowapi.extension.Limiter.limit


def _patched_limit(self, limit_value, key_func=None, per_method=False,
                   methods=None, error_message=None, cost=1,
                   override_defaults=True):
    decorator = _original_limit(self, limit_value, key_func, per_method,
                                methods, error_message, cost,
                                override_defaults)
    def patched_decorator(func):
        wrapped = decorator(func)
        # Preserve the original function signature for FastAPI
        if hasattr(wrapped, '__wrapped__'):
            wrapped.__signature__ = inspect.signature(func)
        return wrapped
    return patched_decorator


slowapi.extension.Limiter.limit = _patched_limit

print("slowapi patched successfully for FastAPI compatibility")
