# pylint: disable=too-few-public-methods
from typing import Any, Dict, Optional, Tuple, Type, Union
import io
import json
import subprocess as sp

from typing_extensions import overload

__all__ = ('add_output', 'get_output')

_outputs: Dict[Tuple[Any, ...], Any] = {}  # pylint: disable=invalid-name


def _make_key(*args: Any, **kwargs: Any) -> Any:
    return args + (json.dumps(kwargs, sort_keys=True), )


def get_output(*args: Any, **kwargs: Any) -> Any:
    key = _make_key(*args, **kwargs)
    try:
        val = _outputs[key]
    except KeyError:
        return None
    if isinstance(val, Exception):
        raise val
    return val


def reset_output() -> None:
    global _outputs  # pylint: disable=global-statement,invalid-name
    _outputs = {}


class _FakeCompletedProcess:
    @overload
    def __init__(self,
                 io_cls: Type[io.BytesIO],
                 *args: Any,
                 stdout_output: Optional[bytes] = ...,
                 stderr_output: Optional[bytes] = ...,
                 returncode: int = 0,
                 **kwargs: Any):
        pass

    @overload
    def __init__(self,
                 io_cls: Type[io.StringIO],
                 *args: Any,
                 stdout_output: Optional[str] = ...,
                 stderr_output: Optional[str] = ...,
                 returncode: int = 0,
                 **kwargs: Any):
        pass

    def __init__(self,
                 io_cls: Any,
                 *args: Any,
                 stdout_output: Any = None,
                 stderr_output: Any = None,
                 returncode: int = 0,
                 **kwargs: Any):
        self.stdout = io_cls(stdout_output) if stdout_output else None
        self.stderr = io_cls(stderr_output) if stderr_output else None
        self.returncode = returncode
        self.args = args
        self.kwargs = kwargs


def add_output(*args: Any, **kwargs: Any) -> None:
    stdout_output = kwargs.pop('stdout_output', None)
    stderr_output = kwargs.pop('stderr_output', None)
    returncode = kwargs.pop('returncode', 0)
    assert isinstance(returncode, int), 'returncode must be an integer'
    raise_ = kwargs.pop('raise_', False)
    raise_cls = kwargs.pop('raise_cls', sp.CalledProcessError)
    raise_message = kwargs.pop('raise_message', 'test exception')
    cls: Union[Type[io.StringIO], Type[io.BytesIO]] = io.StringIO
    if isinstance(stdout_output, bytes) or isinstance(stderr_output, bytes):
        if (isinstance(stdout_output, bytes)
                and not isinstance(stderr_output, bytes)) or (
                    isinstance(stderr_output, bytes)
                    and not isinstance(stdout_output, bytes)):
            raise TypeError(
                'stderr_output and stdout_ouptut must be of the same type')
        cls = io.BytesIO
    key = _make_key(*args, **kwargs)
    if not raise_:
        _outputs[key] = _FakeCompletedProcess(cls, stdout_output,
                                              stderr_output, returncode, *args,
                                              **kwargs)
    else:
        if raise_cls == sp.CalledProcessError:
            _outputs[key] = sp.CalledProcessError(returncode or 255, args[0],
                                                  stdout_output, stderr_output)
        else:
            _outputs[key] = raise_cls(raise_message)
