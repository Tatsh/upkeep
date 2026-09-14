"""Kernel-related utilities."""
from __future__ import annotations

from multiprocessing import cpu_count
from os import chdir
from pathlib import Path
from shlex import quote
import gzip
import logging
import re
import subprocess as sp

from upkeep.constants import CONFIG_GZ, KERNEL_SOURCE_DIR
from upkeep.exceptions import KernelConfigMissing, NoKernelToUpgradeTo, NoValueIsUnselected

from . import CommandRunner

__all__ = ('rebuild_kernel', 'upgrade_kernel')

logger = logging.getLogger(__name__)

KERNEL_ENTRY_RE = re.compile(r'^\[(\d+)\]')
"""Matches the index of an entry in ``eselect kernel list`` output.

:meta hide-value:
"""


def _kernel_entries(output: str) -> tuple[tuple[int, bool], ...]:
    return tuple((int(m.group(1)), line.endswith('*'))
                 for line in (s.strip() for s in output.splitlines())
                 if (m := KERNEL_ENTRY_RE.match(line)))


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

    See Also
    --------
    upgrade_kernel
    """
    if not num_cpus:
        num_cpus = cpu_count() + 1
    chdir(KERNEL_SOURCE_DIR)
    dot_config_exists = Path('.config').is_file()
    if not dot_config_exists and Path(CONFIG_GZ).is_file():
        with gzip.open(CONFIG_GZ) as gz:
            Path('.config').write_bytes(gz.read())
    if not dot_config_exists:
        raise KernelConfigMissing
    logger.info('Running: make oldconfig')
    CommandRunner.check_call(('make', 'oldconfig'))
    commands: tuple[tuple[str, ...], ...] = (('make', f'-j{num_cpus}'), ('make', 'modules_install'),
                                             ('emerge', '--keep-going', '@module-rebuild',
                                              '@x11-module-rebuild'), ('make', 'install'))
    for cmd in commands:
        logger.info('Running: %s', ' '.join(quote(c) for c in cmd))
        CommandRunner.suppress_output(cmd)


def upgrade_kernel(num_cpus: int | None = None, *, fatal: bool | None = True) -> None:
    """
    Upgrades the kernel.

    ``eselect kernel list`` sorts its entries by version, so the highest-numbered entry is the
    newest kernel available. If that entry is not already selected it is selected and
    :py:func:`rebuild_kernel` takes care of the rest.

    Parameters
    ----------
    num_cpus : int
        Number of CPUs (or threads) to pass to ``make -j...``. If not passed,
        defaults to getting the value from ``multiprocessing.cpu_count()``.
    fatal : bool | None
        If ``True``, raises certain exceptions or returns 1. If ``False``,
        always returns 0.

    Raises
    ------
    NoKernelToUpgradeTo
        If the newest kernel is already selected.
    NoValueIsUnselected
        If ``eselect kernel list`` lists no usable entries.
    KernelConfigMissing
        If a kernel configuration cannot be found.

    See Also
    --------
    rebuild_kernel
    """
    entries = _kernel_entries(
        CommandRunner.run(('eselect', '--colour=no', 'kernel', 'list'), stdout=sp.PIPE).stdout)
    if not entries:
        logger.debug('`eselect kernel list` listed no kernels.')
        if fatal:
            raise NoValueIsUnselected
        return
    newest = max(index for index, _ in entries)
    if newest in {index for index, is_selected in entries if is_selected}:
        logger.info('The newest kernel is already selected.')
        if fatal:
            raise NoKernelToUpgradeTo
        return
    cmd: tuple[str, ...] = ('eselect', 'kernel', 'set', str(newest))
    logger.debug('Running: %s', ' '.join(quote(c) for c in cmd))
    CommandRunner.suppress_output(cmd)
    try:
        rebuild_kernel(num_cpus)
    except KernelConfigMissing:
        if not fatal:
            return
        raise
