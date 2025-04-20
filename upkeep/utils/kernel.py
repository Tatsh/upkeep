from __future__ import annotations

from contextlib import ExitStack
from multiprocessing import cpu_count
from os import chdir
from pathlib import Path
from shlex import quote
import gzip
import logging
import re
import subprocess as sp

from upkeep.constants import CONFIG_GZ, KERNEL_SOURCE_DIR, MINIMUM_ESELECT_LINES
from upkeep.exceptions import KernelConfigMissing

from . import CommandRunner

__all__ = ('rebuild_kernel', 'upgrade_kernel')

logger = logging.getLogger(__name__)


def rebuild_kernel(num_cpus: int | None = None) -> None:
    """
    Rebuilds the kernel.

    Runs the following steps:

    - Checks for a kernel configuration in ``/usr/src/linux/.config`` or
      ``/proc/config.gz``
    - ``make oldconfig``
    - ``make``
    - ``make modules_install``
    - ``make install``
    - ``emerge --usepkg=n @module-rebuild @x11-module-rebuild``

    The expectation is that your configuration for installkernel will set up booting from the new
    kernel (updating systemd-boot, etc).

    Parameters
    ----------
    num_cpus : int
        Number of CPUs (or threads) to pass to ``make -j...``. If not passed,
        defaults to getting the value from ``multiprocessing.cpu_count()``.

    Raises
    ------
    KernelConfigMissing
        If a kernel configuration cannot be found.
    RuntimeError
        If grub-mkconfig fails

    See Also
    --------
    upgrade_kernel
    """
    if not num_cpus:
        num_cpus = cpu_count() + 1
    chdir(KERNEL_SOURCE_DIR)
    dot_config_exists = Path('.config').is_file()
    if not dot_config_exists and Path(CONFIG_GZ).is_file():
        with ExitStack() as stack:
            stack.enter_context(Path('.config').open('wb+')).write(
                stack.enter_context(gzip.open(CONFIG_GZ)).read())
    if not dot_config_exists:
        raise KernelConfigMissing
    runner = CommandRunner()
    logger.info('Running: make oldconfig')
    runner.check_call(('make', 'oldconfig'))
    commands: tuple[tuple[str, ...], ...] = (('make', f'-j{num_cpus}'), ('make', 'modules_install'),
                                             ('emerge', '--keep-going', '@module-rebuild',
                                              '@x11-module-rebuild'), ('make', 'install'))
    for cmd in commands:
        logger.info('Running: %s', ' '.join(quote(c) for c in cmd))
        runner.suppress_output(cmd)


def upgrade_kernel(num_cpus: int | None = None, *, fatal: bool | None = True) -> None:
    """
    Upgrades the kernel.

    The logic used here is to check the `eselect kernel` output for two kernel
    lines, where one is selected and the newest kernel is not. The newest
    kernel then gets picked and ``upgrade_kernel()`` takes care of the rest.

    Parameters
    ----------
    num_cpus : int
        Number of CPUs (or threads) to pass to ``make -j...``. If not passed,
        defaults to getting the value from ``multiprocessing.cpu_count()``.
    fatal : Optional[bool]
        If ``True``, raises certain exceptions or returns 1. If ``False``,
        always returns 0.

    See Also
    --------
    rebuild_kernel
    """
    runner = CommandRunner()
    kernel_list = runner.run(('eselect', '--colour=no', 'kernel', 'list'), stdout=sp.PIPE)
    lines = (s.strip() for s in kernel_list.stdout.splitlines() if s)
    if not any(re.search(r'\*$', line) for line in lines):
        logger.info('Select a kernel to upgrade to (eselect kernel set ...).')
        if fatal:
            msg = 'No kernel to upgrade to.'
            raise ValueError(msg)
        return
    if (len([
            s for s in runner.run(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                                  stdout=sp.PIPE).stdout.splitlines() if s
    ]) > MINIMUM_ESELECT_LINES):
        logger.info('Unexpected number of lines (eselect --brief). Not updating kernel.')
        if fatal:
            msg = 'Too many lines from eselect.'
            raise ValueError(msg)
        return
    unselected = None
    for line in (x for x in lines if not x.endswith('*')):
        if m := re.search(r'^\[([0-9]+)\]', line):
            unselected = int(m.group(1))
            break
    if not unselected:
        if fatal:
            msg = 'No value is unselected.'
            raise ValueError(msg)
        return
    cmd: tuple[str, ...] = ('eselect', 'kernel', 'set', str(unselected))
    logger.info('Running: %s', ' '.join(quote(c) for c in cmd))
    runner.suppress_output(cmd)
    rebuild_kernel(num_cpus)
