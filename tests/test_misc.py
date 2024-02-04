# SPDX-License-Identifier: MIT
from inspect import isfunction

from click.testing import CliRunner
import click

from upkeep.commands.kernel import kernel_command
from upkeep.decorators import umask


def test_umask_with_function() -> None:
    umasker = umask(new_umask=0o022, restore=True)(lambda: None)
    assert isfunction(umasker)
    assert umasker() is None


def test_kernel_command() -> None:
    assert CliRunner().invoke(kernel_command(lambda x: None)).exit_code == 0


def test_kernel_command_raise() -> None:
    def raise_(_x: int | None) -> None:
        raise click.Abort

    assert CliRunner().invoke(kernel_command(raise_)).exit_code != 0
