from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict
import json
import subprocess as sp

from Levenshtein import distance
from typing_extensions import Unpack
import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ('SubprocessMocker',)


class MakeKeyKwargsOptional(TypedDict, total=False):
    check: bool
    stderr: int | None
    stdout: int | None
    text: bool


class MakeKeyKwargs(MakeKeyKwargsOptional):
    pass


def _make_key(args: Sequence[str], **kwargs: Unpack[MakeKeyKwargs]) -> str:
    kwargs.pop('text', None)
    return json.dumps({**kwargs, 'args': args}, sort_keys=True)


@dataclass
class _FakeCompletedProcess:
    stdout: str | None = None
    stderr: str | None = None
    returncode: int = 0


class SubprocessMocker:
    def __init__(self) -> None:
        self._outputs: dict[str, _FakeCompletedProcess | BaseException] = {}
        self.history: list[str] = []

    def get_output(
            self, args: Sequence[str], **kwargs: Unpack[MakeKeyKwargs]
    ) -> _FakeCompletedProcess | sp.CalledProcessError | None:
        self.history.append(' '.join(args))
        key = _make_key(args,
                        check=kwargs.get('check', False),
                        stdout=kwargs.get('stdout'),
                        stderr=kwargs.get('stderr'),
                        text=kwargs.get('text', True))
        try:
            val = self._outputs[key]
        except KeyError:  # pragma: no cover
            existing_keys = list(self._outputs.keys())
            closest = '\n'
            if existing_keys:
                possible_keys: list[tuple[int, int]] = []
                for i, existing_key in enumerate(self._outputs.keys()):
                    possible_keys.append((distance(existing_key, key), i))
                possible_keys = sorted(possible_keys)
                closest += f'Closest match:\n{existing_keys[possible_keys[0][1]]}'
                closest += f'\nDistance: {possible_keys[0][0]}'
                pytest.fail(f'Failed to find key:\n{key}{closest}')
            else:
                pytest.fail(f'Failed to find key:\n{key}. No keys were set!')
        if isinstance(val, BaseException):
            raise val
        return val

    def reset_output(self) -> None:
        self._outputs = {}

    def add_output(self,
                   args: Sequence[str],
                   stderr_output: str | None = None,
                   stdout_output: str | None = None,
                   stdout: int | None = None,
                   stderr: int | None = None,
                   returncode: int = 0,
                   *,
                   check: bool = False,
                   raise_: bool = False) -> None:
        key = _make_key(args, check=check, stderr=stderr, stdout=stdout)
        if not raise_:
            self._outputs[key] = _FakeCompletedProcess(stdout_output, stderr_output, returncode)
        else:
            self._outputs[key] = sp.CalledProcessError(returncode or 255, args, stdout_output,
                                                       stderr_output)

    def add_output3(self,
                    args: Sequence[str],
                    stdout_output: str | None = None,
                    stdout: int | None = sp.PIPE,
                    stderr: int | None = None,
                    returncode: int = 0,
                    *,
                    raise_: bool = False) -> None:
        self.add_output(args,
                        check=True,
                        stdout=stdout,
                        stderr=stderr,
                        stdout_output=stdout_output,
                        raise_=raise_,
                        returncode=returncode)

    def add_output4(self,
                    args: Sequence[str],
                    stdout: int | None = None,
                    stderr: int | None = None,
                    *,
                    check: bool = False,
                    raise_: bool = False) -> None:
        self.add_output(args, raise_=raise_, stdout=stdout, stderr=stderr, check=check)
