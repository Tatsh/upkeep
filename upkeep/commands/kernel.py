# SPDX-License-Identifier: MIT
from multiprocessing import cpu_count
from typing import Callable

from loguru import logger
import click

from ..constants import DEFAULT_USER_CONFIG
from ..decorators import umask
from ..exceptions import KernelConfigError
from ..utils.kernel import rebuild_kernel, upgrade_kernel


def kernel_command(
        func: Callable[[int | None, str | None], None]) -> Callable[[], None]:
    """
    CLI entry point for the ``upgrade-kernel`` and ``rebuild-kernel`` commands.

    Parameters
    ----------
    func : callable
        A callable that accepts an integer representing number of CPUs and an
        optional configuration path string.

    Returns
    -------
    callable
        Callable that takes no parameters and returns an integer.
    """
    @click.command(func.__name__)
    @click.option(
        '-c',
        '--config',
        default=DEFAULT_USER_CONFIG,
        help=f'Configuration file. Defaults to {DEFAULT_USER_CONFIG}')
    @click.option('-j',
                  '--number-of-jobs',
                  type=int,
                  default=cpu_count() + 1,
                  help='Number of tasks to run simultaneously')
    @umask(new_umask=0o022)
    def ret(number_of_jobs: int = 0,
            config: str = DEFAULT_USER_CONFIG) -> None:
        try:
            return func(number_of_jobs, config)
        except KernelConfigError as e:
            logger.error(f'Kernel configuration error: {e}')
            raise click.Abort() from e

    return ret


# pylint: disable=invalid-name
#: Entry point for the ``upgrade-kernel`` command.
#:
#: See Also
#: --------
#: upgrade_kernel
upgrade_kernel_command = kernel_command(upgrade_kernel)
#: Entry point for the ``rebuild-kernel`` command.
#:
#: See Also
#: --------
#: rebuild_kernel
rebuild_kernel_command = kernel_command(rebuild_kernel)
# pylint: enable=invalid-name
