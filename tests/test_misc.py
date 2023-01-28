# SPDX-License-Identifier: MIT
from inspect import isfunction

from upkeep import KernelConfigError, graceful_interrupt, kernel_command, umask


def test_graceful_interrupt_no_function():
    assert isfunction(graceful_interrupt())


def test_umask_with_function():
    umasker = umask(lambda: None, new_umask=0o022, restore=True)
    assert isfunction(umasker)
    assert umasker() is None  # pylint: disable=no-value-for-parameter


def test_kernel_command():
    assert kernel_command(lambda x, y: 2)() == 2


def test_kernel_command_raise() -> None:
    def raise_(_x: int | None, _y: str | None) -> int:
        raise KernelConfigError()

    assert kernel_command(raise_)() == 1
