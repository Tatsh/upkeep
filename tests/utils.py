# SPDX-License-Identifier: MIT
# pylint: disable=too-few-public-methods,import-outside-toplevel
from typing import Any, BinaryIO, Dict, Optional, TextIO, Type, overload
import io
import json
import subprocess as sp

from Levenshtein import distance

__all__ = ('SubprocessMocker', )


def _make_key(*args: list[Any], **kwargs: dict[str, Any]) -> str:
    return json.dumps({**kwargs, **{'args': args}}, sort_keys=True)


class SubprocessMocker:

    def __init__(self) -> None:
        self._outputs: Dict[str, Any] = {}
        self.history: list[str] = []

    def get_output(self, *args: Any, **kwargs: Any) -> Any:
        self.history.append(' '.join(args[0]))
        key = _make_key(*args, **kwargs)
        try:
            val = self._outputs[key]
        except KeyError:
            print(f'Failed to find key:\n{key}')
            existing_keys = list(self._outputs.keys())
            if existing_keys:
                possible_keys: list[tuple[int, int]] = []
                for i, existing_key in enumerate(self._outputs.keys()):
                    possible_keys.append((distance(existing_key, key), i))
                possible_keys = sorted(possible_keys)
                print(f'Closest match:\n{existing_keys[possible_keys[0][1]]}')
                print(f'Distance: {possible_keys[0][0]}')
            return None
        if isinstance(val, BaseException):
            raise val
        return val

    def reset_output(self) -> None:
        self._outputs = {}

    class _FakeCompletedProcess:

        @overload
        def __init__(self,
                     io_cls: Type[BinaryIO],
                     stdout_output: Optional[bytes] = ...,
                     stderr_output: Optional[bytes] = ...,
                     returncode: int = 0,
                     **kwargs: Any):
            pass

        @overload
        def __init__(self,
                     io_cls: Type[TextIO],
                     stdout_output: Optional[str] = ...,
                     stderr_output: Optional[str] = ...,
                     returncode: int = 0,
                     **kwargs: Any):
            pass

        def __init__(self,
                     io_cls: Any,
                     stdout_output: Any = None,
                     stderr_output: Any = None,
                     returncode: int = 0,
                     **kwargs: Any):
            if kwargs.pop('universal_newlines', False):
                self.stdout = (stdout_output
                               if stdout_output is not None else None)
                self.stderr = (stderr_output
                               if stderr_output is not None else None)
            else:
                self.stdout = (io_cls(stdout_output)
                               if stdout_output is not None else None)
                self.stderr = (io_cls(stderr_output)
                               if stderr_output is not None else None)
            self.returncode = returncode
            self.kwargs = kwargs

    def add_output(self, *args: Any, **kwargs: Any) -> None:
        stdout_output = kwargs.pop('stdout_output', None)
        stderr_output = kwargs.pop('stderr_output', None)
        returncode = kwargs.pop('returncode', 0)
        assert isinstance(returncode, int), 'returncode must be an integer'
        raise_ = kwargs.pop('raise_', False)
        raise_cls = kwargs.pop('raise_cls', sp.CalledProcessError)
        raise_message = kwargs.pop('raise_message', 'test exception')
        cls: Type[BinaryIO] | Type[TextIO] = io.StringIO
        if (isinstance(stdout_output, bytes)
                or isinstance(stderr_output, bytes)):
            if (isinstance(stdout_output, bytes)
                    and not isinstance(stderr_output, bytes)) or (
                        isinstance(stderr_output, bytes)
                        and not isinstance(stdout_output, bytes)):
                raise TypeError(
                    'stderr_output and stdout_output must be of the same type')
            cls = io.BytesIO
        key = _make_key(*args, **kwargs)
        if not raise_:
            self._outputs[key] = self._FakeCompletedProcess(
                cls, stdout_output, stderr_output, returncode, **kwargs)
        else:
            if raise_cls == sp.CalledProcessError:
                self._outputs[key] = sp.CalledProcessError(
                    returncode or 255, args[0], stdout_output, stderr_output)
            else:
                self._outputs[key] = raise_cls(raise_message)

    def add_output2(self, *args: Any, **kwargs: Any) -> None:
        from upkeep.utils import minenv

        kwargs.pop('check', None)
        kwargs.pop('env', None)
        self.add_output(check=True, env=minenv(), *args, **kwargs)

    def add_output3(self, *args: Any, **kwargs: Any) -> None:
        from upkeep.utils import minenv

        kwargs.pop('check', None)
        kwargs.pop('env', None)
        kwargs.pop('universal_newlines', None)
        self.add_output(check=True,
                        universal_newlines=True,
                        stdout=sp.PIPE,
                        stderr=sp.PIPE,
                        env=minenv(),
                        *args,
                        **kwargs)

    def add_output4(self, *args: Any, **kwargs: Any) -> None:
        from upkeep.utils import minenv

        kwargs.pop('env', None)
        kwargs.pop('universal_newlines', None)
        self.add_output(universal_newlines=True, env=minenv(), *args, **kwargs)
