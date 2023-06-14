# SPDX-License-Identifier: MIT
from inspect import isfunction
from typing import cast

from click.testing import CliRunner
import click

from upkeep.commands.kernel import kernel_command
from upkeep.decorators import umask


def test_umask_with_function() -> None:
    umasker = umask(new_umask=0o022, restore=True)(lambda: None)
    assert isfunction(umasker)
    assert umasker() is None  # pylint: disable=no-value-for-parameter


def test_kernel_command() -> None:
    assert CliRunner().invoke(
        cast(click.BaseCommand,
             kernel_command(lambda x, y: None))).exit_code == 0


def test_kernel_command_raise() -> None:
    def raise_(_x: int | None, _y: str | None) -> None:
        raise click.Abort()

    assert CliRunner().invoke(cast(click.BaseCommand,
                                   kernel_command(raise_))).exit_code != 0
