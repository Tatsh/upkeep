# SPDX-License-Identifier: MIT
import gzip
import re
import shutil
import subprocess as sp
from contextlib import ExitStack
from functools import lru_cache
from glob import glob
from multiprocessing import cpu_count
from os import chdir, unlink
from os.path import isfile, realpath
from os.path import join as path_join
from pathlib import Path
from shlex import quote
from typing import cast

import click
from loguru import logger

from ..constants import CONFIG_GZ, GRUB_CFG, KERNEL_SOURCE_DIR, OLD_KERNELS_DIR
from ..exceptions import KernelConfigError
from ..utils import get_config, get_temp_filename
from . import CommandRunner


@lru_cache()
def _get_kernel_version_suffix() -> str | None:
    with open('.config', 'r') as f:
        for line in f.readlines():
            if line.startswith('CONFIG_LOCALVERSION='):
                tmp_suffix = line.strip().split('=')[1][1:-1].strip()
                if tmp_suffix:
                    return tmp_suffix
                break
    return None


@lru_cache()
def _get_kernel_version() -> str | None:
    with open('include/generated/autoconf.h', 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith('* Linux/') and line.endswith(
                    ' Kernel Configuration'):
                return line.split(' ')[2]
    return None


@lru_cache()
def _uefi_unified() -> bool:
    try:
        CommandRunner().suppress_output(['grep', '-E', '^uefi="(yes|true)"'] +
                                        glob('/etc/dracut.conf.d/*.conf'))
        return True
    except sp.CalledProcessError:
        return False


@lru_cache()
def _has_grub() -> bool:
    try:
        CommandRunner().run(('eix', '--installed', '--exact', 'grub'))
        return True
    except sp.CalledProcessError:
        return False


@lru_cache()
def _esp_path() -> str:
    return CommandRunner().run(('bootctl', '-p'),
                               stdout=sp.PIPE).stdout.split('\n')[0].strip()


def rebuild_kernel(num_cpus: int | None = None,
                   config_path: str | None = None) -> None:
    # pylint: disable=line-too-long
    """
    Rebuilds the kernel.

    Runs the following steps:

    - Checks for a kernel configuration in ``/usr/src/linux/.config`` or
      ``/proc/config.gz``
    - ``make oldconfig``
    - ``make``
    - ``make modules_install``
    - ``emerge --usepkg=n @module-rebuild @x11-module-rebuild``
    - Archives the old kernel and related files in ``/boot`` to the old kernels
      directory.
    - ``make install``

    The expectation is that your configuration for kernelinstall will have the correct behaviour
    such as running Dracut and building an initrd or unified image for UEFI booting. A matching
    ``vmlinuz-*`` file is expected to appear in ``/boot``.

    Parameters
    ----------
    num_cpus : int
        Number of CPUs (or threads) to pass to ``make -j...``. If not passed,
        defaults to getting the value from ``multiprocessing.cpu_count()``.

    config_path : Optional[str]
        Configuration file path.

    Raises
    ------
    KernelConfigError
        If a kernel configuration cannot be found.
    RuntimeError
        If grub-mkconfig fails

    See Also
    --------
    upgrade_kernel
    """
    # pylint: enable=line-too-long
    if not num_cpus:
        num_cpus = cpu_count() + 1
    chdir(KERNEL_SOURCE_DIR)
    if not isfile('.config') and isfile(CONFIG_GZ):
        with ExitStack() as stack:
            stack.enter_context(open('.config', 'wb+')).write(
                stack.enter_context(gzip.open(CONFIG_GZ)).read())
    if not isfile('.config'):
        raise KernelConfigError(
            'Will not build without a .config file present')
    runner = CommandRunner()
    suffix = _get_kernel_version_suffix() or ''
    logger.info('Running: make oldconfig')
    runner.check_call(('make', 'oldconfig'))
    commands: tuple[tuple[str, ...], ...] = (
        ('make', f'-j{num_cpus}'),
        ('make', 'modules_install'),
        ('emerge', '--keep-going', '@module-rebuild', '@x11-module-rebuild'),
    )
    for cmd in commands:
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        runner.suppress_output(cmd)
    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    commands = (('find', '/boot', '-maxdepth', '1', '(', '-name',
                 'initramfs-*', '-o', '-name', 'vmlinuz-*', '-o', '-iname',
                 'System.map*', '-o', '-iname', 'config-*', ')', '-exec', 'mv',
                 '{}', OLD_KERNELS_DIR, ';'), ('make', 'install'))
    for cmd in commands:
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        try:
            runner.suppress_output(cmd)
        except sp.CalledProcessError:
            runner.suppress_output(('eselect', 'kernel', 'set', '1'))


def upgrade_kernel(  # pylint: disable=too-many-branches
        num_cpus: int | None = None,
        config_path: str | None = None,
        fatal: bool | None = True) -> None:
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

    config_path : Optional[str]
        Configuration file path.

    fatal : Optional[bool]
        If ``True``, raises certain exceptions or returns 1. If ``False``,
        always returns 0.

    See Also
    --------
    rebuild_kernel
    """
    runner = CommandRunner()
    kernel_list = runner.run(('eselect', '--colour=no', 'kernel', 'list'),
                             stdout=sp.PIPE)
    lines = (s.strip() for s in kernel_list.stdout.splitlines() if s)
    if not any(re.search(r'\*$', line) for line in lines):
        logger.info('Select a kernel to upgrade to (eselect kernel set ...).')
        if fatal:
            raise click.Abort()
        return None
    if (len([
            s for s in runner.run(('eselect', '--colour=no', '--brief',
                                   'kernel', 'list'),
                                  stdout=sp.PIPE).stdout.splitlines() if s
    ]) > 2):
        logger.info(
            'Unexpected number of lines (eselect --brief). Not updating '
            'kernel.')
        if fatal:
            raise click.Abort()
        return None
    unselected = None
    for line in (x for x in lines if not x.endswith('*')):
        m = re.search(r'^\[([0-9]+)\]', line)
        if m:
            unselected = int(m.group(1))
            break
    if unselected not in (1, 2):
        logger.info('Unexpected number of lines. Not updating kernel.')
        if fatal:
            raise click.Abort()
        return None
    cmd: tuple[str, ...] = ('eselect', 'kernel', 'set', str(unselected))
    logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
    runner.suppress_output(cmd)
    try:
        rebuild_kernel(num_cpus, config_path)
    except KernelConfigError as e:
        logger.exception(e)
        if fatal:
            raise click.Abort()
        return None
    kernel_list = runner.run(('eselect', '--colour=no', 'kernel', 'list'),
                             stdout=sp.PIPE)
    lines = (s.strip() for s in kernel_list.stdout.splitlines() if s)
    old_kernel = None
    for line in (x for x in lines if not x.endswith('*')):
        m = re.search(r'^\[[0-9]+\]', line)
        if m:
            old_kernel = re.split(r'^\[[0-9]+\]\s+', line)[1][6:]
            break
    if not old_kernel:
        if not fatal:
            return None
        raise KernelConfigError('Failed to determine old kernel version')
    suffix = _get_kernel_version_suffix() or ''
    if _uefi_unified():
        for path in Path(_esp_path()).joinpath(
                'EFI', 'Linux').glob(f'linux-{old_kernel}{suffix}*.efi'):
            path.unlink()
    else:
        cmd = ('kernel-install', 'remove', f'{old_kernel}{suffix}')
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        runner.suppress_output(cmd)
    return None
