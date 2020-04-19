from configparser import ConfigParser
from contextlib import ExitStack
from functools import lru_cache, wraps
from multiprocessing import cpu_count
from os import chdir, close, environ, makedirs, umask as set_umask, unlink
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

HEAVY_PACKAGES = (
    'app-office/libreoffice',
    'dev-java/icedtea',
    'dev-qt/qtwebengine',
    'dev-qt/qtwebkit',
    'kde-frameworks/kdewebkit',
    'mail-client/thunderbird',
    'net-libs/webkit-gtk',
    'sys-devel/clang',
    'sys-devel/gcc',
    'sys-devel/llvm',
    'www-client/chromium',
    'www-client/firefox',
)


class KernelConfigError(Exception):
    pass


CONFIG_GZ = '/proc/config.gz'
DEFAULT_USER_CONFIG = '/etc/upkeeprc'
GRUB_CFG = '/boot/grub/grub.cfg'
INTEL_UC = '/boot/intel-uc.img'
KERNEL_SRC_DIR = '/usr/src/linux'
OLD_KERNELS_DIR = '/var/lib/upkeep/old-kernels'
SPECIAL_ENV = ('USE', 'HOME', 'MAKEOPTS', 'CONFIG_PROTECT_MASK', 'LANG',
               'PATH', 'SHELL', 'CONFIG_PROTECT', 'TERM')
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
          new_umask: int) -> AnyCallable:
    """Restores prior umask after calling the decorated function."""
    def decorator_umask(func: AnyCallable) -> AnyCallable:
        @wraps(func)
        def inner(*args: Any, **kwargs: Any) -> Any:
            set_umask(new_umask)
            return func(*args, **kwargs)

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
    parser.add_argument('-l',
                        '--run-layman',
                        action='store_true',
                        help='Run "layman -S" if installed')
    args = parser.parse_args()
    if args.run_layman:
        try:
            _run_output(('which', 'layman'))
        except sp.CalledProcessError:
            log.error('You need to have app-portage/layman installed')
            return 1
        _run_output(('layman', '-S'))
    try:
        _run_output(('which', 'eix-sync'))
    except sp.CalledProcessError as e:
        if e.returncode != 2:
            log.error(
                'You need to have app-portage/eix installed for this to work')
        return 1
    try:
        _run_output(('eix-sync', '-qH'))
    except sp.CalledProcessError as e:
        return e.returncode
    return 0


@graceful_interrupt
@umask(new_umask=0o022)
def ecleans() -> int:
    """
    Runs the following clean up commands:

    - ``emerge --depclean --quiet``
    - ``emerge --quiet @preserved-rebuild``
    - ``revdep-rebuild --quiet``
    - ``eclean-dist --deep``
    - ``rm -fR /var/tmp/portage/*``

    Returns
    -------
    int
        Exit code of the last command.
    """
    try:
        _check_call(('emerge', '--depclean', '--quiet'))
        _check_call(('emerge', '--quiet', '@preserved-rebuild'))
        _check_call(('revdep-rebuild', '--quiet'))
        _check_call(('eclean-dist', '--deep'))
        _check_call(['rm', '-fR'] +
                    list(map(str,
                             Path('/var/tmp/portage').glob('*'))))
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
    - ``emerge --keep-going --with-bdeps=y --tree --quiet --update --deep --newuse @world``
    - ``emerge --keep-going --quiet @live-rebuild``
    - ``emerge --keep-going --quiet @preserved-rebuild``
    - ``systemctl daemon-reexec`` if applicable
    - upgrade kernel

    In the second step, if ``-H`` is not passed, heavier packages like Clang
    and Chromium are built separately, to hopefully allow a machine to remain
    responsive while building packages.

    This function understands the following CLI flags:

    - ``-a`` / ``--ask``: Pass ``--ask`` to the ``emerge @world`` command
    - ``-L`` / ``--no-live-rebuild``: Skip ``emerge @live-rebuild`` step
    - ``-P`` / ``--no-preserved-rebuild``: Skip ``emerge @preserved-rebuild``
      step
    - ``-D`` / ``--no-daemon-reexec``: Skip ``systemctl daemon-reexec`` step
    - ``-U`` / ``--no-upgrade-kernel``: Skip upgrading the kernel
    - ``-H`` / ``--split-heavy``: Split heavy packages to be built separately.

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
    parser.add_argument('-H',
                        '--split-heavy',
                        action='store_true',
                        help='Split heavy packages to be built separately')
    parser.add_argument(
        '-c',
        '--config',
        default=DEFAULT_USER_CONFIG,
        help=f'Configuration file. Defaults to {DEFAULT_USER_CONFIG}')
    args = parser.parse_args()

    live_rebuild = not args.no_live_rebuild
    preserved_rebuild = not args.no_preserved_rebuild
    daemon_reexec = not args.no_daemon_reexec
    up_kernel = not args.no_upgrade_kernel
    ask_arg = ['--ask'] if args.ask else []

    _check_call(('emerge', '--oneshot', '--quiet', '--update', 'portage'))
    if args.split_heavy:
        ask_arg += [f'--exclude={name}' for name in HEAVY_PACKAGES]
    _check_call([
        'emerge', '--keep-going', '--with-bdeps=y', '--tree', '--quiet',
        '--update', '--deep', '--newuse', '@world'
    ] + ask_arg)
    if args.split_heavy:
        for name in HEAVY_PACKAGES:
            try:
                _check_call(('eix', '-I', '-e', name))
            except sp.CalledProcessError:
                continue
            _check_call(('emerge', '--oneshot', '--keep-going', '--tree',
                         '--quiet', '--update', '--deep', '--newuse', name))

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
        return upgrade_kernel(None, args.config)

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
            log.error('Failed!')
            log.error('STDOUT: %s', e.stdout)
            log.error('STDERR: %s', e.stderr)
            return e.returncode


def _bootctl_update_or_install() -> None:
    try:
        _run_output(('bootctl', 'update'))
    except sp.CalledProcessError:
        try:
            _run_output(('bootctl', 'install'))
        except sp.CalledProcessError as e:
            if 'Failed to test system token validity' not in e.stderr:
                raise e


def _get_temp_filename(*args: Any, **kwargs: Any):
    fd, tmp_name = mkstemp(*args, **kwargs)
    close(fd)
    return tmp_name


def _maybe_sign_exes(esp_path: str,
                     kernel_filename: str,
                     kernel_path: Path,
                     config_path: Optional[str] = None) -> None:
    log = _setup_logging_stdout()
    config = None
    if config_path:
        config = _config(config_path)
    output_bootx64 = path_join(esp_path, 'EFI', 'BOOT', 'BOOTX64.EFI')
    output_systemd_bootx64 = path_join(esp_path, 'EFI', 'systemd',
                                       'systemd-bootx64.efi')
    tmp_kernel = _get_temp_filename()
    tmp_bootx64 = _get_temp_filename()
    shutil.copy(output_bootx64, tmp_bootx64)
    shutil.copy(str(kernel_path), tmp_kernel)
    files_to_sign = (
        (tmp_bootx64, output_bootx64),
        (tmp_bootx64, output_systemd_bootx64),
        (tmp_kernel, path_join(esp_path, 'gentoo', kernel_filename)),
    )
    for line in _run_output(('bootctl', 'status')).stdout.split('\n'):
        if 'Secure Boot: enabled' in line:
            db_key = db_crt = None
            if config:
                db_key = config.get('systemd-boot', 'sign-key', fallback='')
                db_crt = config.get('systemd-boot', 'sign-cert', fallback='')
            if not db_key or not db_crt:
                shutil.copy(tmp_kernel,
                            path_join(esp_path, 'gentoo', kernel_filename))
                log.info('You appear to have Secure Boot enabled. Make sure '
                         'you sign your boot loader and your kernel (which '
                         'also must have EFI stub and its command line '
                         'built-in) before rebooting.')
                break
            for input_file, output_path in files_to_sign:
                _run_output(('sbsign', '--key', db_key, '--cert', db_crt,
                             input_file, '--output', output_path))
                _run_output(('sbverify', '--cert', db_crt, output_path))
            for input_file, _ in files_to_sign:
                if isfile(input_file):
                    unlink(input_file)


def _manage_loader_conf(loader_conf: Path,
                        config_path: Optional[str] = None) -> None:
    has_gentoo_default = False
    lines = []
    config = None
    timeout = None
    if config_path:
        config = _config(config_path)
        timeout = config.get('systemd-boot', 'timeout', fallback='3')
    with loader_conf.open('r') as f:
        for line in f.readlines():
            if 'default gentoo*' in line:
                has_gentoo_default = True
            if line.startswith('default ') or (line.startswith('timeout ')
                                               and config and timeout):
                continue
            lines.append(line)
    if not has_gentoo_default:
        with loader_conf.open('w+') as f:
            for line in lines:
                f.write(line)
            f.write('default gentoo*\n')
            if timeout:
                f.write(f'timeout {timeout}\n')


def _get_kernel_version_suffix() -> Optional[str]:
    with open('.config', 'r') as f:
        for line in f.readlines():
            if line.startswith('CONFIG_LOCALVERSION='):
                tmp_suffix = line.strip().split('=')[1][1:-1].strip()
                if tmp_suffix:
                    return tmp_suffix
                break
    return None


def _get_kernel_version() -> Optional[str]:
    with open('include/generated/autoconf.h', 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith('* Linux/') and line.endswith(
                    ' Kernel Configuration'):
                return line.split(' ')[2]
    return None


def _update_systemd_boot(config_path: Optional[str] = None) -> int:
    log = _setup_logging_stdout()
    esp_path = _run_output(('bootctl', '-p')).stdout.split('\n')[0].strip()
    if not esp_path:
        log.warning(
            '`bootctl -p` returned empty string. Not installing new kernel')
        return 1
    _bootctl_update_or_install()
    kernel_location = path_join(esp_path, 'gentoo')
    if Path(kernel_location).exists():
        shutil.rmtree(kernel_location)
    entries_path = path_join(esp_path, 'loader', 'entries')
    makedirs(kernel_location, 0o755, exist_ok=True)
    makedirs(entries_path, 0o755, exist_ok=True)
    gentoo_conf = Path(path_join(entries_path, 'gentoo.conf'))
    loader_conf = Path(path_join(esp_path, 'loader', 'loader.conf'))
    kernel_version = _get_kernel_version()
    if not kernel_version:
        raise RuntimeError('Failed to detect Linux version')
    suffix = _get_kernel_version_suffix() or ''
    rd_filename = f'initramfs-{kernel_version}{suffix}.img'
    rd_path = path_join('/boot', rd_filename)
    has_rd = isfile(rd_path)
    kernel_filename = kernel_path = None
    for path in Path('/boot').glob(f'*{kernel_version}*'):
        with path.open('rb') as fb:
            if fb.read(2) == b'MZ' and not kernel_filename:
                kernel_filename = basename(path.name)
                kernel_path = path
            else:
                shutil.copy(str(path), path_join(kernel_location, path.name))
    if not kernel_filename or not kernel_path:
        raise RuntimeError('Failed to find Linux image')
    with gentoo_conf.open('w+') as f:
        f.write('title Gentoo\n')
        f.write(f'linux /gentoo/{kernel_filename}\n')
        if isfile(INTEL_UC):
            shutil.copyfile(INTEL_UC,
                            path_join(kernel_location, basename(INTEL_UC)))
            f.write('initrd /gentoo/intel-uc.img\n')
        if has_rd:
            f.write(f'initrd /gentoo/{rd_filename}\n')
    _manage_loader_conf(loader_conf, config_path)
    _maybe_sign_exes(esp_path, kernel_filename, kernel_path, config_path)
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
    - ``emerge --quiet --keep-going --quiet-fail --verbose @module-rebuild @x11-module-rebuild``
    - Archives the old kernel and related files in ``/boot`` to the old kernels
      directory.
    - ``make install``
    - ``dracut --force``
    - ``grub-mkconfig -o /boot/grub/grub.cfg``

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

    suffix = ''
    with open('.config', 'r') as file2:
        for line in file2.readlines():
            if line.startswith('CONFIG_LOCALVERSION='):
                s = line.split('=')[-1].strip()[1:-1]
                if s:
                    suffix = s
                break

    log.info('Running: make oldconfig')
    sp.run(('make', 'oldconfig'), check=True)
    commands: Tuple[Tuple[str, ...], ...] = (
        ('make', f'-j{num_cpus}'),
        ('make', 'modules_install'),
        ('emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
         '@module-rebuild', '@x11-module-rebuild'),
    )
    for cmd in commands:
        log.info('Running: %s', ' '.join(map(quote, cmd)))
        _run_output(cmd)

    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    _run_output(
        ('find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
         '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
         'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'))
    _run_output(('make', 'install'))
    kver_arg = '-'.join(realpath('.').split('-')[1:]) + suffix
    cmd = ('dracut', '--force', '--kver', kver_arg)
    log.info('Running: %s', ' '.join(map(quote, cmd)))
    try:
        _run_output(cmd)
    except sp.CalledProcessError as e:
        log.error('Failed!')
        log.error('STDOUT: %s', e.stdout)
        log.error('STDERR: %s', e.stderr)
        return e.returncode

    try:
        _run_output(('eix', '-I', '-e', 'grub'))
        has_grub = True
    except sp.CalledProcessError:
        has_grub = False

    if has_grub:
        return _update_grub()
    return _update_systemd_boot(config_path)


def upgrade_kernel(num_cpus: Optional[int] = None,
                   config_path: Optional[str] = None) -> int:
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
    lines = filter(None, map(str.strip, kernel_list.stdout.split('\n')))

    if not any(re.search(r'\*$', line) for line in lines):
        log.info('Select a kernel to upgrade to (eselect kernel set ...).')
        return 1
    if len(
            list(
                filter(
                    None,
                    _run_output(('eselect', '--colour=no', '--brief', 'kernel',
                                 'list')).stdout.split('\n')))) > 2:
        log.info('Unexpected number of lines (eselect --brief). Not updating '
                 'kernel.')
        return 1

    unselected = None
    for line in (x for x in lines if not x.endswith('*')):
        m = re.search(r'^\[([0-9]+)\]', line)
        if m:
            unselected = int(m.group(1))
            break
    if unselected not in (1, 2):
        log.info('Unexpected number of lines. Not updating kernel.')
        return 1
    _run_output(('eselect', 'kernel', 'set', str(unselected)))
    return rebuild_kernel(num_cpus, config_path)


def kernel_command(
    func: Callable[[Optional[int], Optional[str]], int]
) -> Callable[[], int]:
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
