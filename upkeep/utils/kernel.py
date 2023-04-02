# SPDX-License-Identifier: MIT
from contextlib import ExitStack
from functools import lru_cache
from glob import glob
from multiprocessing import cpu_count
from os import chdir, unlink
from os.path import isfile, join as path_join, realpath
from pathlib import Path
from shlex import quote
from typing import cast
import gzip
import re
import shutil
import subprocess as sp

from loguru import logger
import click

from ..constants import CONFIG_GZ, GRUB_CFG, KERNEL_SOURCE_DIR, OLD_KERNELS_DIR
from ..exceptions import KernelConfigError
from ..utils import get_config, get_temp_filename
from . import CommandRunner


def _update_grub() -> int:
    args = ['grub2-mkconfig', '-o', GRUB_CFG]
    runner = CommandRunner()
    try:
        return runner.suppress_output(args)
    except (sp.CalledProcessError, FileNotFoundError):
        args[0] = 'grub-mkconfig'
        return runner.run(args).returncode


def _bootctl_update_or_install() -> None:
    runner = CommandRunner()
    try:
        runner.run(('bootctl', 'update'), stderr=sp.PIPE)
    except sp.CalledProcessError as e:
        ok = True
        for line in cast(str, e.stderr).splitlines():
            if ('Failed to test system token validity' in line
                    or line.startswith('Skipping "')):
                continue
            ok = False
        if not ok:
            runner.suppress_output(('bootctl', 'install', '--graceful'))


def _maybe_sign_exes(esp_path: str, config_path: str | None) -> None:
    runner = CommandRunner()
    config = None
    if config_path:
        config = get_config(config_path)
    output_bootx64 = path_join(esp_path, 'EFI', 'BOOT', 'BOOTX64.EFI')
    output_systemd_bootx64 = path_join(esp_path, 'EFI', 'systemd',
                                       'systemd-bootx64.efi')
    db_key: str | None = None
    db_crt: str | None = None
    if config:
        db_key = config.get('systemd-boot', 'sign-key', fallback='')
        db_crt = config.get('systemd-boot', 'sign-cert', fallback='')
    if (not db_key or not db_crt and 'Secure Boot: enabled' in runner.run(
        ('bootctl', 'status'), stdout=sp.PIPE).stdout):
        logger.info(
            'You appear to have Secure Boot enabled. Make sure to sign '
            'the boot loader before rebooting. If you are using a unified'
            ' EFI kernel image, you must sign it as well.')
        return
    tmp_bootx64 = get_temp_filename()
    shutil.copy(output_bootx64, tmp_bootx64)
    files_to_sign = (
        (tmp_bootx64, output_bootx64),
        (tmp_bootx64, output_systemd_bootx64),
    )
    assert db_crt is not None, 'Expected db_crt to be a path to a certificate (value is None)'
    for input_file, output_path in files_to_sign:
        cmd = ('sbsign', '--key', db_key, '--cert', db_crt, input_file,
               '--output', output_path)
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        runner.suppress_output(cmd)
        assert db_crt is not None
        runner.suppress_output(('sbverify', '--cert', db_crt, output_path))
    for input_file, _ in files_to_sign:
        if isfile(input_file):
            unlink(input_file)


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


def _update_systemd_boot(config_path: str | None) -> None:
    if not _esp_path():
        raise KernelConfigError('`bootctl -p` returned empty string')
    _bootctl_update_or_install()
    kernel_version = _get_kernel_version()
    if not kernel_version:
        raise RuntimeError('Failed to detect Linux version')
    if not _uefi_unified():
        # Type #1 with kernel-install
        # Dracut is expected to be installed which will add initrd
        suffix = _get_kernel_version_suffix() or ''
        cmd = ('kernel-install', 'add', f'{kernel_version}{suffix}',
               f'/boot/vmlinuz-{kernel_version}{suffix}')
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        CommandRunner().run(cmd)
    _maybe_sign_exes(_esp_path(), config_path)
    # Clean up /boot
    for path in Path('/boot').glob(f'*{kernel_version}*'):
        path.unlink()


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
    - ``emerge --usepkg=n --quiet --keep-going --quiet-fail --verbose @module-rebuild @x11-module-rebuild``
    - Archives the old kernel and related files in ``/boot`` to the old kernels
      directory.
    - ``make install``
    - ``dracut --force`` (if GRUB is installed)
    - ``grub-mkconfig -o /boot/grub/grub.cfg`` (if GRUB is installed)

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
        ('emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
         '@module-rebuild', '@x11-module-rebuild'),
    )
    for cmd in commands:
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        runner.suppress_output(cmd)
    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    commands = (('find', '/boot', '-maxdepth', '1', '(', '-name',
                 'initramfs-*', '-o', '-name', 'vmlinuz-*', '-o', '-iname',
                 'System.map*', '-o', '-iname', 'config-*', ')', '-exec', 'mv',
                 '{}', OLD_KERNELS_DIR, ';'), (
                     'make',
                     'install',
                 ))
    for cmd in commands:
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        try:
            runner.suppress_output(cmd)
        except sp.CalledProcessError:
            runner.suppress_output(('eselect', 'kernel', 'set', '1'))
    if _has_grub() or _uefi_unified():
        kver_arg = '-'.join(realpath('.').split('-')[1:]) + suffix
        cmd = ('dracut', '--force', '--kver', kver_arg)
        logger.info(f'Running: {" ".join(quote(c) for c in cmd)}')
        runner.suppress_output(cmd)
    if _has_grub():
        _update_grub()
        return
    _update_systemd_boot(config_path)


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
