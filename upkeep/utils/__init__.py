# SPDX-License-Identifier: MIT
from collections.abc import Mapping, Sequence
from functools import lru_cache
from os import environ
from shlex import quote
from subprocess import CompletedProcess
from typing import cast
import subprocess as sp

from loguru import logger

from ..constants import SPECIAL_ENV


@lru_cache
def minenv() -> Mapping[str, str]:
    env: dict[str, str] = {}
    for key in SPECIAL_ENV:
        if environ.get(key):
            env[key] = environ[key]
    return env


class CommandRunner:
    def run(self,
            args: Sequence[str],
            *,
            check: bool = True,
            env: Mapping[str, str] | None = None,
            stdout: int | None = None,
            stderr: int | None = None) -> CompletedProcess[str]:
        try:
            return sp.run(args,
                          check=check,
                          stdout=stdout,
                          stderr=stderr,
                          text=True,
                          env=env or minenv())
        except sp.CalledProcessError as e:
            logger.error(f'`{" ".join(quote(x) for x in cast(Sequence[str], e.cmd))}` '
                         'failed')
            logger.error(f'STDOUT: {cast(str, e.stdout)}')
            logger.error(f'STDERR: {cast(str, e.stderr)}')
            raise

    def check_call(self,
                   args: Sequence[str],
                   env: Mapping[str, str] | None = None,
                   stdout: int | None = None,
                   stderr: int | None = None) -> int:
        return self.run(args, check=True, env=env, stdout=stdout, stderr=stderr).returncode

    def suppress_output(self,
                        args: Sequence[str],
                        env: Mapping[str, str] | None = None,
                        check: bool = True) -> int:
        return self.run(args, stdout=sp.DEVNULL, stderr=sp.DEVNULL, env=env, check=check).returncode
