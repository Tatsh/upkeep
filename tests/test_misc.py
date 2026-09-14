from __future__ import annotations

from inspect import isfunction
from typing import TYPE_CHECKING

import click

from upkeep.commands.kernel import kernel_command
from upkeep.decorators import umask

if TYPE_CHECKING:
    from click.testing import CliRunner


def test_umask_with_function() -> None:
    umasker = umask(new_umask=0o022, restore=True)(lambda: None)
    assert isfunction(umasker)
    assert umasker() is None


def test_kernel_command(runner: CliRunner) -> None:
    assert runner.invoke(kernel_command('test-kernel', lambda _: None)).exit_code == 0


def test_kernel_command_raise(runner: CliRunner) -> None:
    def raise_(_x: int | None) -> None:
        raise click.Abort

    assert runner.invoke(kernel_command('test-kernel', raise_)).exit_code != 0
