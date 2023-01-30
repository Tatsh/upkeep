# SPDX-License-Identifier: MIT
from functools import wraps
from os import umask as set_umask
from typing import Callable, ParamSpec, TypeVar

__all__ = ('umask', )

P = ParamSpec('P')
T = TypeVar('T')


def umask(new_umask: int,
          restore: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Sets the umask before calling the decorated function."""

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
