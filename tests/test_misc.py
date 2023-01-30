# SPDX-License-Identifier: MIT
from inspect import isfunction

import click
import pytest

from upkeep.commands.kernel import kernel_command
from upkeep.decorators import umask
from upkeep.exceptions import KernelConfigError


def test_umask_with_function() -> None:
    umasker = umask(new_umask=0o022, restore=True)(lambda: None)
    assert isfunction(umasker)
    assert umasker() is None  # pylint: disable=no-value-for-parameter


def test_kernel_command() -> None:
    assert kernel_command(lambda x, y: None)() is None


def test_kernel_command_raise() -> None:

    def raise_(_x: int | None, _y: str | None) -> None:
        raise KernelConfigError()

    with pytest.raises(click.Abort):
        kernel_command(raise_)()
