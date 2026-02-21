"""Utility functions and classes."""
from __future__ import annotations

from functools import lru_cache
from os import environ
from shlex import quote
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, cast
import logging
import subprocess as sp

from upkeep.constants import SPECIAL_ENV

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

logger = logging.getLogger(__name__)


@lru_cache
def minenv() -> Mapping[str, str]:
    """Minimal environment dictionary for subprocesses."""
    env: dict[str, str] = {}
    for key in SPECIAL_ENV:
        if environ.get(key):
            env[key] = environ[key]
    return env


class CommandRunner:
    """Helper class to run commands."""
    @staticmethod
    def run(args: Sequence[str],
            *,
            check: bool = True,
            env: Mapping[str, str] | None = None,
            stdout: int | None = None,
            stderr: int | None = None) -> CompletedProcess[str]:
        """
        Run a command with logging and error handling.

        Raises
        ------
        subprocess.CalledProcessError
            If the command returns a non-zero exit code and `check` is `True`.
        """
        try:
            return sp.run(args,
                          check=check,
                          stdout=stdout,
                          stderr=stderr,
                          text=True,
                          env=env or minenv())
        except sp.CalledProcessError as e:
            logger.exception('`%s` failed.', ' '.join(
                quote(x) for x in cast('Sequence[str]', e.cmd)))
            logger.exception('STDOUT: %s', cast('str', e.stdout))
            logger.exception('STDERR: %s', cast('str', e.stderr))
            raise

    @staticmethod
    def check_call(args: Sequence[str],
                   env: Mapping[str, str] | None = None,
                   stdout: int | None = None,
                   stderr: int | None = None) -> int:
        """Run a command and return its exit code."""
        return CommandRunner.run(args, check=True, env=env, stdout=stdout, stderr=stderr).returncode

    @staticmethod
    def suppress_output(args: Sequence[str],
                        env: Mapping[str, str] | None = None,
                        *,
                        check: bool = True) -> int:
        """Run a command, suppressing its output."""
        return CommandRunner.run(args, stdout=sp.DEVNULL, stderr=sp.DEVNULL, env=env,
                                 check=check).returncode
