# SPDX-License-Identifier: MIT
from configparser import ConfigParser
from functools import lru_cache
from os import close, environ
from shlex import quote
from subprocess import CompletedProcess
from tempfile import mkstemp
from typing import Mapping, Sequence, cast
import subprocess as sp

from loguru import logger

from ..constants import DEFAULT_USER_CONFIG, SPECIAL_ENV


def get_temp_filename(suffix: str | None = None,
                      prefix: str | None = None,
                      dir: str | None = None,
                      text: bool = False) -> str:
    fd, tmp_name = mkstemp(suffix=suffix, prefix=prefix, dir=dir, text=text)
    close(fd)
    return tmp_name


@lru_cache()
def get_config(config_path: str) -> ConfigParser:
    config = ConfigParser()
    config.read(config_path or DEFAULT_USER_CONFIG)
    return config


@lru_cache()
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
            logger.error(
                f'`{" ".join(quote(x) for x in cast(Sequence[str], e.cmd))}` '
                'failed')
            logger.error(f'STDOUT: {cast(str, e.stdout)}')
            logger.error(f'STDERR: {cast(str, e.stderr)}')
            raise e

    def check_call(self,
                   args: Sequence[str],
                   env: Mapping[str, str] | None = None,
                   stdout: int | None = None,
                   stderr: int | None = None) -> int:
        return self.run(args,
                        check=True,
                        env=env,
                        stdout=stdout,
                        stderr=stderr).returncode

    def suppress_output(self,
                        args: Sequence[str],
                        env: Mapping[str, str] | None = None,
                        check: bool = True) -> int:
        return self.run(args,
                        stdout=sp.DEVNULL,
                        stderr=sp.DEVNULL,
                        env=env,
                        check=check).returncode
