from __future__ import annotations

from multiprocessing import cpu_count
from typing import TYPE_CHECKING

import click

from upkeep.decorators import umask
from upkeep.exceptions import KernelError
from upkeep.utils.kernel import rebuild_kernel, upgrade_kernel

if TYPE_CHECKING:
    from collections.abc import Callable


def kernel_command(func: Callable[[int | None], None]) -> click.BaseCommand:
    """
    CLI entry point for the ``upgrade-kernel`` and ``rebuild-kernel`` commands.

    Parameters
    ----------
    func : callable
        A callable that accepts an optional integer representing number of CPUs.

    Returns
    -------
    click.BaseCommand
        Callable that takes no parameters and returns ``None``.
    """
    @click.command(func.__name__)
    @click.option('-j',
                  '--number-of-jobs',
                  type=int,
                  default=cpu_count() + 1,
                  help='Number of tasks to run simultaneously')
    @umask(new_umask=0o022)
    def ret(number_of_jobs: int = 0) -> None:
        try:
            return func(number_of_jobs)
        except KernelError as e:
            click.echo(f'Kernel configuration error: {str(e) or "unknown"}', err=True)
            raise click.Abort from e

    return ret


upgrade_kernel_command = kernel_command(upgrade_kernel)
"""
Entry point for the ``upgrade-kernel`` command.

See Also
--------
upgrade_kernel
"""
rebuild_kernel_command = kernel_command(rebuild_kernel)
"""
Entry point for the ``rebuild-kernel`` command.

See Also
--------
rebuild_kernel
"""
