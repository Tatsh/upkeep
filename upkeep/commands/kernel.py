# SPDX-License-Identifier: MIT
from collections.abc import Callable
from multiprocessing import cpu_count

from loguru import logger
import click

from ..decorators import umask
from ..exceptions import KernelError
from ..utils.kernel import rebuild_kernel, upgrade_kernel


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
            logger.error(f'Kernel configuration error: {e}')
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
