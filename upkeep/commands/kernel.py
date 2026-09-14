"""Module providing the ``upgrade-kernel`` and ``rebuild-kernel`` commands."""
from __future__ import annotations

from multiprocessing import cpu_count
from typing import TYPE_CHECKING

import click

from upkeep.cli import start_logging
from upkeep.decorators import umask
from upkeep.exceptions import KernelError
from upkeep.utils.kernel import rebuild_kernel, upgrade_kernel

if TYPE_CHECKING:
    from collections.abc import Callable


def kernel_command(name: str,
                   func: Callable[[int | None], object],
                   description: str = '') -> click.Command:
    """
    CLI entry point for the ``upgrade-kernel`` and ``rebuild-kernel`` commands.

    Parameters
    ----------
    name : str
        Name the command is registered under.
    func : Callable[[int | None], object]
        A callable that accepts an optional integer representing number of CPUs.
    description : str
        Help text shown by ``--help``.

    Returns
    -------
    click.Command
        Callable that takes no parameters and returns ``None``.
    """
    @click.command(name, context_settings={'help_option_names': ('-h', '--help')}, help=description)
    @click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
    @click.option('-j',
                  '--number-of-jobs',
                  type=int,
                  default=cpu_count() + 1,
                  help='Number of tasks to run simultaneously.')
    @click.pass_context
    @umask(new_umask=0o022)
    def ret(ctx: click.Context, number_of_jobs: int = 0, *, debug: bool = False) -> None:
        start_logging(ctx, debug=debug)
        try:
            func(number_of_jobs)
        except KernelError as e:
            click.echo(f'Kernel configuration error: {str(e) or "unknown"}', err=True)
            raise click.Abort from e

    return ret


_UPGRADE_KERNEL_HELP = """Select the newest kernel and build it.

``eselect kernel list`` sorts its entries by version, so the highest-numbered entry is the newest
kernel available. If it is already selected there is nothing to do. Otherwise:

\b
- ``eselect kernel set`` the newest entry
- ``make oldconfig``, seeding ``.config`` from ``/proc/config.gz`` if needed
- ``make``
- ``make modules_install``
- ``emerge --keep-going @module-rebuild @x11-module-rebuild``
- ``make install``
"""
_REBUILD_KERNEL_HELP = """Rebuild the kernel currently selected in ``/usr/src/linux``.

Runs the build steps without touching the ``eselect kernel`` selection:

\b
- ``make oldconfig``, seeding ``.config`` from ``/proc/config.gz`` if needed
- ``make``
- ``make modules_install``
- ``emerge --keep-going @module-rebuild @x11-module-rebuild``
- ``make install``
"""
upgrade_kernel_command = kernel_command('upgrade-kernel', upgrade_kernel, _UPGRADE_KERNEL_HELP)
"""
Entry point for the ``upgrade-kernel`` command.

See Also
--------
:py:func:`~upkeep.utils.kernel.upgrade_kernel`

:meta hide-value:
"""
rebuild_kernel_command = kernel_command('rebuild-kernel', rebuild_kernel, _REBUILD_KERNEL_HELP)
"""
Entry point for the ``rebuild-kernel`` command.

See Also
--------
:py:func:`~upkeep.utils.kernel.rebuild_kernel`

:meta hide-value:
"""
