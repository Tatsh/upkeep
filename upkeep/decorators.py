from __future__ import annotations

from functools import wraps
from os import umask as set_umask
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ('umask',)

P = ParamSpec('P')
T = TypeVar('T')


def umask(new_umask: int, *, restore: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Set the umask before calling the decorated function."""
    def decorator_umask(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            old_umask = set_umask(new_umask)
            ret = func(*args, **kwargs)
            if restore:
                set_umask(old_umask)
            return ret

        return inner

    return decorator_umask
