# SPDX-License-Identifier: MIT
from configparser import ConfigParser
from contextlib import ExitStack
from functools import lru_cache, wraps
from glob import glob
from multiprocessing import cpu_count
from os import chdir, close, environ, umask as set_umask, unlink
from os.path import basename, isfile, join as path_join, realpath
from pathlib import Path
from shlex import quote
from subprocess import CompletedProcess
from tempfile import mkstemp
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, cast
import argparse
import gzip
import logging
import re
import shutil
import subprocess as sp
import sys

__all__ = (
    'ecleans',
    'emerges',
    'esync',
    'rebuild_kernel',
    'rebuild_kernel_command',
    'upgrade_kernel',
    'upgrade_kernel_command',
)


class KernelConfigError(Exception):
    pass


CONFIG_GZ = '/proc/config.gz'
DEFAULT_USER_CONFIG = '/etc/upkeeprc'
GRUB_CFG = '/boot/grub/grub.cfg'
INTEL_UC = '/boot/intel-uc.img'
KERNEL_SRC_DIR = '/usr/src/linux'
OLD_KERNELS_DIR = '/var/lib/upkeep/old-kernels'
SPECIAL_ENV = ('CONFIG_PROTECT', 'CONFIG_PROTECT_MASK', 'HOME', 'LANG',
               'MAKEOPTS', 'PATH', 'SHELL', 'SSH_AGENT_PID', 'SSH_AUTH_SOCK',
               'TERM', 'USE')
# --getbinpkg=n is broken when FEATURES=getbinpkg
# https://bugs.gentoo.org/759067
DISABLE_GETBINPKG_ENV_DICT = dict(FEATURES='-getbinpkg')
AnyCallable = Callable[..., Any]


@lru_cache()
def _config(path: str = DEFAULT_USER_CONFIG) -> ConfigParser:
    config = ConfigParser()
    config.read(path)
    return config


def graceful_interrupt(_func: Optional[AnyCallable] = None) -> AnyCallable:
    """
    Handles KeyboardInterrupt gracefully since stack trace is usually not
    needed for this event.
    """

    def decorator_graceful(func: AnyCallable) -> AnyCallable:

        @wraps(func)
        def inner(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                log = _setup_logging_stdout()
                log.info('Interrupted by user')
                return 1

        return inner

    if not _func:
        return decorator_graceful
    return decorator_graceful(_func)


def umask(_func: Optional[AnyCallable] = None,
          *,
          new_umask: int,
          restore: bool = False) -> AnyCallable:
    """Sets the umask before calling the decorated function."""

    def decorator_umask(func: AnyCallable) -> AnyCallable:

        @wraps(func)
        def inner(*args: Any, **kwargs: Any) -> Any:
            old_umask = set_umask(new_umask)
            ret = func(*args, **kwargs)
            if restore:
                set_umask(old_umask)
            return ret

        return inner

    if not _func:
        return decorator_umask
    return decorator_umask(_func)


def _run_output(args: Any,
                check: bool = True,
                text: bool = True,
                env: Optional[Mapping[str, str]] = None,
                **kwargs: Any) -> CompletedProcess:
    return sp.run(args,
                  check=check,
                  stdout=sp.PIPE,
                  stderr=sp.PIPE,
                  universal_newlines=text,
                  env=env or _minenv(),
                  **kwargs)


def _check_call(args: Any,
                text: bool = True,
                env: Optional[Mapping[str, str]] = None,
                **kwargs: Any) -> int:
    return sp.check_call(args,
                         universal_newlines=text,
                         env=env or _minenv(),
                         **kwargs)


def _suppress_output(args: Any,
                     text: bool = True,
                     env: Optional[Mapping[str, str]] = None,
                     **kwargs: Any) -> int:
    return sp.check_call(args,
                         stdout=sp.DEVNULL,
                         stderr=sp.DEVNULL,
                         universal_newlines=text,
                         env=env or _minenv(),
                         **kwargs)


@lru_cache()
def _setup_logging_stdout(name: Optional[str] = None,
                          verbose: bool = False) -> logging.Logger:
    name = name if name else basename(sys.argv[0])
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    channel = logging.StreamHandler(sys.stdout)
    channel.setFormatter(logging.Formatter('%(message)s'))
    channel.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.addHandler(channel)
    return log


@lru_cache()
def _minenv() -> Dict[str, str]:
    env = dict()
    for key in SPECIAL_ENV:
        if environ.get(key):
            env[key] = environ[key]
    return env


@graceful_interrupt
def esync() -> int:
    """
    Syncs Portage sources. Requires ``app-portage/eix`` to be installed.

    This runs the following:

    - ``layman -S`` (if ``-l`` is passed in CLI arguments and if it is
      available)
    - ``eix-sync``

    Returns
    -------
    int
        Exit code of ``eix-sync``.
    """
    log = _setup_logging_stdout()
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-l',
                        '--run-layman',
                        action='store_true',
                        help='Run "layman -S" if installed')
    args = parser.parse_args()
    runner = cast(Callable[..., Any],
                  _run_output if not args.debug else sp.run)
    if args.run_layman:
        try:
            _run_output(('which', 'layman'))
        except sp.CalledProcessError:
            log.error('You need to have app-portage/layman installed')
            return 1
        try:
            runner(('layman', '-S'), check=True)
        except sp.CalledProcessError as e:
            return e.returncode
    try:
        _run_output(('which', 'eix-sync'))
    except sp.CalledProcessError as e:
        if e.returncode != 2:
            log.error(
                'You need to have app-portage/eix installed for this to work')
        return 1
    sync_args = ('-a', ) if args.debug else ('-a', '-q', '-H')
    try:
        runner(('eix-sync', ) + sync_args, check=True)
    except sp.CalledProcessError as e:
        return e.returncode
    return 0


@graceful_interrupt
@umask(new_umask=0o022)
def ecleans() -> int:
    """
    Runs the following clean up commands:

    - ``emerge --depclean --quiet``
    - ``emerge --usepkg=n --quiet @preserved-rebuild``
    - ``revdep-rebuild --quiet` -- --usepkg=n`
    - ``eclean-dist --deep``
    - ``rm -fR /var/tmp/portage/*``

    Returns
    -------
    int
        Exit code of the last command.
    """
    try:
        _check_call(('emerge', '--depclean', '--quiet'))
        _check_call(('emerge', '--usepkg=n', '--quiet', '@preserved-rebuild'),
                    env=DISABLE_GETBINPKG_ENV_DICT)
        _check_call(('revdep-rebuild', '--quiet', '--', '--usepkg=n'),
                    env=DISABLE_GETBINPKG_ENV_DICT)
        _check_call(('eclean-dist', '--deep'))
        _check_call(['rm', '-fR'] +
                    [str(s) for s in Path('/var/tmp/portage').glob('*')])
    except sp.CalledProcessError as e:
        log = _setup_logging_stdout()
        log.error('%s failed', e.cmd)
        log.error('STDOUT: %s', e.stdout)
        log.error('STDOUT: %s', e.stderr)
        return e.returncode
    return 0


@graceful_interrupt
@umask(new_umask=0o022)
def emerges() -> int:
    # pylint: disable=line-too-long
    """
    Runs the following steps:

    - ``emerge --oneshot --quiet --update portage``
    - ``emerge --keep-going --tree --quiet --update --deep --newuse @world``
    - ``emerge --keep-going --quiet @live-rebuild``
    - ``emerge --keep-going --quiet @preserved-rebuild``
    - ``systemctl daemon-reexec`` if applicable
    - upgrade kernel

    This function understands the following CLI flags:

    - ``-a`` / ``--ask``: Pass ``--ask`` to the ``emerge @world`` command
    - ``-L`` / ``--no-live-rebuild``: Skip ``emerge @live-rebuild`` step
    - ``-P`` / ``--no-preserved-rebuild``: Skip ``emerge @preserved-rebuild``
      step
    - ``-D`` / ``--no-daemon-reexec``: Skip ``systemctl daemon-reexec`` step
    - ``-U`` / ``--no-upgrade-kernel``: Skip upgrading the kernel

    Returns
    -------
    int
        The exit code of the last command from ``upgrade_kernel`` or ``0``.

    See Also
    --------
    upgrade_kernel
    """
    # pylint: enable=line-too-long
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-a',
                        '--ask',
                        action='store_true',
                        help='Pass --ask to emerge command')
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Pass --verbose to emerge and enable verbose messages')
    parser.add_argument('-L',
                        '--no-live-rebuild',
                        action='store_true',
                        help='Skip emerge @live-rebuild step')
    parser.add_argument('-P',
                        '--no-preserved-rebuild',
                        action='store_true',
                        help='Skip @preserved-ebuild step')
    parser.add_argument(
        '-D',
        '--no-daemon-reexec',
        action='store_true',
        help='Do not run systemctl daemon-reexec (on systemd systems)')
    parser.add_argument('-U',
                        '--no-upgrade-kernel',
                        action='store_true',
                        help='Do not attempt to upgrade kernel')
    parser.add_argument(
        '-c',
        '--config',
        default=DEFAULT_USER_CONFIG,
        help=f'Configuration file. Defaults to {DEFAULT_USER_CONFIG}')
    parser.add_argument(
        '--fatal-upgrade-kernel',
        action='store_true',
        help='Exit with status > 0 if kernel upgrade cannot be done')
    parser.add_argument('-e', '--exclude', nargs='*', metavar='ATOM')
    args = parser.parse_args()

    live_rebuild = not args.no_live_rebuild
    preserved_rebuild = not args.no_preserved_rebuild
    daemon_reexec = not args.no_daemon_reexec
    up_kernel = not args.no_upgrade_kernel
    ask_arg = ['--ask'] if args.ask else []
    verbose_arg = ['--verbose'] if args.verbose else ['--quiet']
    exclude_arg = [f'--exclude={x}' for x in args.exclude or []]

    _check_call(['emerge', '--oneshot', '--update', 'portage'] + verbose_arg)
    _check_call([
        'emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse',
        '@world'
    ] + ask_arg + verbose_arg + exclude_arg)

    if live_rebuild:
        _check_call(('emerge', '--keep-going', '--quiet', '@live-rebuild'))
    if preserved_rebuild:
        _check_call((
            'emerge',
            '--keep-going',
            '--quiet',
            '@preserved-rebuild',
        ))

    if daemon_reexec:
        try:
            _suppress_output(('which', 'systemctl'))
            _check_call(('systemctl', 'daemon-reexec'))
        except sp.CalledProcessError:
            pass

    if up_kernel:
        return upgrade_kernel(None,
                              args.config,
                              fatal=args.fatal_upgrade_kernel)

    return 0


def _update_grub() -> int:
    log = _setup_logging_stdout()
    args = ['grub2-mkconfig', '-o', GRUB_CFG]
    try:
        return _run_output(args).returncode
    except (sp.CalledProcessError, FileNotFoundError):
        args[0] = 'grub-mkconfig'
        try:
            return _run_output(args).returncode
        except sp.CalledProcessError as e:
            log.error('STDOUT: %s', e.stdout)
            log.error('STDERR: %s', e.stderr)
            raise e


def _bootctl_update_or_install() -> None:
    try:
        _run_output(('bootctl', 'update'))
    except sp.CalledProcessError as e:
        ok = True
        for line in e.stderr.splitlines():
            if ('Failed to test system token validity' in line
                    or line.startswith('Skipping "')):
                continue
            ok = False
        if not ok:
            _run_output(('bootctl', 'install', '--graceful'))


def _get_temp_filename(*args: Any, **kwargs: Any) -> str:
    fd, tmp_name = mkstemp(*args, **kwargs)
    close(fd)
    return tmp_name


def _maybe_sign_exes(esp_path: str, config_path: Optional[str] = None) -> None:
    log = _setup_logging_stdout()
    config = None
    if config_path:
        config = _config(config_path)

    output_bootx64 = path_join(esp_path, 'EFI', 'BOOT', 'BOOTX64.EFI')
    output_systemd_bootx64 = path_join(esp_path, 'EFI', 'systemd',
                                       'systemd-bootx64.efi')
    db_key: Optional[str] = None
    db_crt: Optional[str] = None
    if config:
        db_key = config.get('systemd-boot', 'sign-key', fallback='')
        db_crt = config.get('systemd-boot', 'sign-cert', fallback='')
    if (not db_key or not db_crt and 'Secure Boot: enabled' in _run_output(
        ('bootctl', 'status')).stdout):
        log.info('You appear to have Secure Boot enabled. Make sure to sign '
                 'the boot loader before rebooting. If you are using a unified'
                 ' EFI kernel image, you must sign it as well.')
        return

    tmp_bootx64 = _get_temp_filename()
    shutil.copy(output_bootx64, tmp_bootx64)
    files_to_sign = (
        (tmp_bootx64, output_bootx64),
        (tmp_bootx64, output_systemd_bootx64),
    )
    for input_file, output_path in files_to_sign:
        cmd = ('sbsign', '--key', db_key, '--cert', cast(str, db_crt),
               input_file, '--output', output_path)
        log.info('Running: %s', ' '.join(quote(c) for c in cmd))
        _run_output(cmd)
        _run_output(('sbverify', '--cert', db_crt, output_path))
    for input_file, _ in files_to_sign:
        if isfile(input_file):
            unlink(input_file)


@lru_cache()
def _get_kernel_version_suffix() -> Optional[str]:
    with open('.config', 'r') as f:
        for line in f.readlines():
            if line.startswith('CONFIG_LOCALVERSION='):
                tmp_suffix = line.strip().split('=')[1][1:-1].strip()
                if tmp_suffix:
                    return tmp_suffix
                break
    return None


@lru_cache()
def _get_kernel_version() -> Optional[str]:
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
        _run_output(['grep', '-E', '^uefi="(yes|true)"'] +
                    glob('/etc/dracut.conf.d/*.conf'))
        return True
    except sp.CalledProcessError:
        return False


@lru_cache()
def _has_grub():
    try:
        _run_output(('eix', '--installed', '--exact', 'grub'))
        return True
    except sp.CalledProcessError:
        return False


@lru_cache()
def _esp_path() -> str:
    return _run_output(('bootctl', '-p')).stdout.split('\n')[0].strip()


def _update_systemd_boot(config_path: Optional[str] = None) -> int:
    log = _setup_logging_stdout()
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
        log.info('Running: %s', ' '.join(quote(c) for c in cmd))
        _run_output(cmd)
    _maybe_sign_exes(_esp_path(), config_path)
    # Clean up /boot
    for path in Path('/boot').glob(f'*{kernel_version}*'):
        path.unlink()

    return 0


def rebuild_kernel(num_cpus: Optional[int] = None,
                   config_path: Optional[str] = None) -> int:
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

    Returns
    -------
    int
        Returns the exit code of the last run command.

    See Also
    --------
    upgrade_kernel
    """
    # pylint: enable=line-too-long
    log = _setup_logging_stdout()
    if not num_cpus:
        num_cpus = cpu_count() + 1
    chdir(KERNEL_SRC_DIR)

    if not isfile('.config') and isfile(CONFIG_GZ):
        with ExitStack() as stack:
            stack.enter_context(open('.config', 'wb+')).write(
                stack.enter_context(gzip.open(CONFIG_GZ)).read())
    if not isfile('.config'):
        raise KernelConfigError(
            'Will not build without a .config file present')

    suffix = _get_kernel_version_suffix() or ''
    log.info('Running: make oldconfig')
    _check_call(('make', 'oldconfig'))
    commands1: Tuple[Tuple[Tuple[str, ...], Dict[str, str]], ...] = (
        (('make', f'-j{num_cpus}'), {}),
        (('make', 'modules_install'), {}),
        (('emerge', '--usepkg=n', '--quiet', '--keep-going', '--quiet-fail',
          '--verbose', '@module-rebuild', '@x11-module-rebuild'),
         DISABLE_GETBINPKG_ENV_DICT),
    )
    for cmd, env in commands1:
        log.info('Running: env %s %s',
                 ' '.join(quote(f'{k}={v}') for k, v in env.items()),
                 ' '.join(quote(c) for c in cmd))
        _run_output(cmd, env=env)

    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    commands = (('find', '/boot', '-maxdepth', '1', '(', '-name',
                 'initramfs-*', '-o', '-name', 'vmlinuz-*', '-o', '-iname',
                 'System.map*', '-o', '-iname', 'config-*', ')', '-exec', 'mv',
                 '{}', OLD_KERNELS_DIR, ';'), (
                     'make',
                     'install',
                 ))
    for cmd in commands:
        log.info('Running: %s', ' '.join(quote(c) for c in cmd))
        try:
            _run_output(cmd)
        except sp.CalledProcessError as e:
            try:
                _run_output(('eselect', 'kernel', 'set', '1'))
            except sp.CalledProcessError:
                pass
            raise e

    if _has_grub() or _uefi_unified():
        kver_arg = '-'.join(realpath('.').split('-')[1:]) + suffix
        cmd = ('dracut', '--force', '--kver', kver_arg)
        log.info('Running: %s', ' '.join(quote(c) for c in cmd))
        try:
            _run_output(cmd)
        except sp.CalledProcessError as e:
            log.error('STDOUT: %s', e.stdout)
            log.error('STDERR: %s', e.stderr)
            raise e

    if _has_grub():
        return _update_grub()

    return _update_systemd_boot(config_path)


def upgrade_kernel(num_cpus: Optional[int] = None,
                   config_path: Optional[str] = None,
                   fatal: Optional[bool] = True) -> int:
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

    Returns
    -------
    int
        Returns ``1`` if the ``eselect`` output is not usable. Otherwise,
        returns the result from ``upgrade_kernel()``.

    See Also
    --------
    rebuild_kernel
    """
    log = _setup_logging_stdout()
    kernel_list = _run_output(('eselect', '--colour=no', 'kernel', 'list'))
    lines = (s.strip() for s in kernel_list.stdout.splitlines() if s)

    if not any(re.search(r'\*$', line) for line in lines):
        log.info('Select a kernel to upgrade to (eselect kernel set ...).')
        return 1 if fatal else 0

    if len([
            s for s in _run_output(('eselect', '--colour=no', '--brief',
                                    'kernel', 'list')).stdout.splitlines() if s
    ]) > 2:
        log.info('Unexpected number of lines (eselect --brief). Not updating '
                 'kernel.')
        return 1 if fatal else 0

    unselected = None
    for line in (x for x in lines if not x.endswith('*')):
        m = re.search(r'^\[([0-9]+)\]', line)
        if m:
            unselected = int(m.group(1))
            break
    if unselected not in (1, 2):
        log.info('Unexpected number of lines. Not updating kernel.')
        return 1 if fatal else 0
    cmd: Tuple[str, ...] = ('eselect', 'kernel', 'set', str(unselected))
    log.info('Running: %s', ' '.join(quote(c) for c in cmd))
    _run_output(cmd)
    try:
        rebuild_kernel(num_cpus, config_path)
    except KernelConfigError as e:
        log.error('%s', e)
        return 1 if fatal else 0

    kernel_list = _run_output(('eselect', '--colour=no', 'kernel', 'list'))
    lines = (s.strip() for s in kernel_list.stdout.splitlines() if s)
    old_kernel = None
    for line in (x for x in lines if not x.endswith('*')):
        m = re.search(r'^\[[0-9]+\]', line)
        if m:
            old_kernel = re.split(r'^\[[0-9]+\]\s+', line)[1][6:]
            break
    if not old_kernel:
        if not fatal:
            return 0
        raise KernelConfigError('Failed to determine old kernel version')
    suffix = _get_kernel_version_suffix() or ''
    if _uefi_unified():
        for path in Path(_esp_path()).joinpath(
                'EFI', 'Linux').glob(f'linux-{old_kernel}{suffix}*.efi'):
            path.unlink()
    else:
        cmd = ('kernel-install', 'remove', f'{old_kernel}{suffix}')
        log.info('Running: %s', ' '.join(quote(c) for c in cmd))
        _run_output(cmd)

    return 0


def kernel_command(
        func: Callable[[Optional[int], Optional[str]],
                       int]) -> Callable[[], int]:
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

    @graceful_interrupt
    @umask(new_umask=0o022)
    def ret() -> int:
        parser = argparse.ArgumentParser(__name__)
        parser.add_argument('-j',
                            '--number-of-jobs',
                            default=cpu_count() + 1,
                            help='Number of tasks to run simultaneously',
                            type=int)
        parser.add_argument(
            '-c',
            '--config',
            default=DEFAULT_USER_CONFIG,
            help=f'Configuration file. Defaults to {DEFAULT_USER_CONFIG}')
        args = parser.parse_args()
        try:
            return func(args.number_of_jobs, args.config)
        except KernelConfigError as e:
            log = _setup_logging_stdout()
            log.error('Kernel configuration error: %s', e)
            return 1

    return cast(Callable[[], int], ret)


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
