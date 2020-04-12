from contextlib import ExitStack
from functools import lru_cache, wraps
from multiprocessing import cpu_count
from os import chdir, environ, umask as set_umask
from os.path import basename, isfile, realpath
from pathlib import Path
from shlex import quote
from typing import Any, Callable, Dict, Optional, Tuple, cast
import argparse
import gzip
import logging
import re
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
    'sys-devel/gcc',
    'sys-devel/clang',
    'www-client/chromium',
    'www-client/firefox',
    'sys-devel/llvm',
    'app-office/libreoffice',
    'dev-qt/qtwebengine',
    'net-libs/webkit-gtk',
    'kde-frameworks/kdewebkit',
    'dev-qt/qtwebkit',
    'mail-client/thunderbird',
    'dev-java/icedtea',
)


class KernelConfigError(Exception):
    pass


CONFIG_GZ = '/proc/config.gz'
GRUB_CFG = '/boot/grub/grub.cfg'
KERNEL_SRC_DIR = '/usr/src/linux'
OLD_KERNELS_DIR = '/var/lib/upkeep/old-kernels'
SPECIAL_ENV = ('USE', 'HOME', 'MAKEOPTS', 'CONFIG_PROTECT_MASK', 'LANG',
               'PATH', 'SHELL', 'CONFIG_PROTECT', 'TERM')
AnyCallable = Callable[..., Any]


def umask(_func: Optional[AnyCallable] = None, *,
          new_umask: int) -> AnyCallable:
    """Restores prior umask after calling the decorated function."""
    def decorator_umask(func: AnyCallable) -> AnyCallable:
        @wraps(func)
        def inner(*args: Any, **kwargs: Any) -> Any:
            old_umask = set_umask(new_umask)
            try:
                return func(*args, **kwargs)
            finally:
                set_umask(old_umask)

        return inner

    if not _func:
        return decorator_umask
    return decorator_umask(_func)


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
    env = _minenv()

    if args.run_layman:
        try:
            sp.run(('which', 'layman'), stdout=sp.PIPE, check=True, env=env)
            sp.run(('layman', '-S'), check=True, env=env)
        except sp.CalledProcessError:
            pass

    try:
        sp.run(('which', 'eix-sync'), stdout=sp.PIPE, check=True, env=env)
    except sp.CalledProcessError as e:
        if e.returncode != 2:
            log.error('You need to have eix-sync installed for this to work')
        return 1

    return sp.run(('eix-sync', '-qH'), env=env).returncode  # pylint: disable=subprocess-run-check


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
    env = _minenv()
    sp.run(('emerge', '--depclean', '--quiet'), check=True, env=env)
    sp.run(('emerge', '--quiet', '@preserved-rebuild'), check=True, env=env)
    sp.run(('revdep-rebuild', '--quiet'), check=True, env=env)
    sp.run(('eclean-dist', '--deep'), check=True, env=env)
    return sp.run(['rm', '-fR'] +  # pylint: disable=subprocess-run-check
                  list(map(str,
                           Path('/var/tmp/portage').glob('*')))).returncode


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
    - ``-H`` / ``--allow-heavy``: Allow heavy packages to be built with the
      rest of the upgrades.

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
                        '--allow-heavy',
                        action='store_true',
                        help='Allow heavy packages to be built with the rest')
    args = parser.parse_args()

    live_rebuild = not args.no_live_rebuild
    preserved_rebuild = not args.no_preserved_rebuild
    daemon_reexec = not args.no_daemon_reexec
    up_kernel = not args.no_upgrade_kernel
    ask_arg = ['--ask'] if args.ask else []
    env = _minenv()

    sp.run(('emerge', '--oneshot', '--quiet', '--update', 'portage'),
           check=True,
           env=env)
    if not args.allow_heavy:
        ask_arg += [f'--exclude={name}' for name in HEAVY_PACKAGES]
    sp.run([
        'emerge', '--keep-going', '--with-bdeps=y', '--tree', '--quiet',
        '--update', '--deep', '--newuse', '@world'
    ] + ask_arg,
           check=True,
           env=env)
    if not args.allow_heavy:
        for name in HEAVY_PACKAGES:
            try:
                sp.run(('eix', '-I', '-e', name), check=True, env=env)
            except sp.CalledProcessError:
                continue
            sp.run(('emerge', '--oneshot', '--keep-going', '--tree', '--quiet',
                    '--update', '--deep', '--newuse', name),
                   check=True,
                   env=env)

    if live_rebuild:
        sp.run(('emerge', '--keep-going', '--quiet', '@live-rebuild'),
               check=True,
               env=env)
    if preserved_rebuild:
        sp.run(('emerge', '--keep-going', '--quiet', '@preserved-rebuild'),
               check=True,
               env=env)

    if daemon_reexec:
        try:
            sp.run(('which', 'systemctl'), check=True, stdout=sp.PIPE, env=env)
            sp.run(('systemctl', 'daemon-reexec'), check=True, env=env)
        except sp.CalledProcessError:
            pass

    if up_kernel:
        return upgrade_kernel(None)

    return 0


def rebuild_kernel(num_cpus: Optional[int] = None) -> int:
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

    env = _minenv()
    log.info('Running: make oldconfig')
    sp.run(('make', 'oldconfig'), check=True, env=env)
    commands: Tuple[Tuple[str, ...], ...] = (
        ('make', f'-j{num_cpus}'),
        ('make', 'modules_install'),
        ('emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
         '@module-rebuild', '@x11-module-rebuild'),
    )
    for cmd in commands:
        log.info('Running: %s', ' '.join(map(quote, cmd)))
        sp.run(cmd, check=True, env=env, stdout=sp.PIPE)

    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    sp.run(
        ('find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
         '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
         'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'),
        check=True,
        env=env)
    sp.run(('make', 'install'), check=True, env=env)
    kver_arg = '-'.join(realpath('.').split('-')[1:]) + suffix
    cmd = ('dracut', '--force', '--kver', kver_arg)
    log.info('Running: %s', ' '.join(map(quote, cmd)))
    try:
        sp.run(cmd,
               check=True,
               env=env,
               encoding='utf-8',
               stdout=sp.PIPE,
               stderr=sp.PIPE)
    except sp.CalledProcessError as e:
        log.error('Failed!')
        log.error('STDOUT: %s', e.stdout)
        log.error('STDERR: %s', e.stderr)
        return e.returncode

    args = ['grub2-mkconfig', '-o', GRUB_CFG]
    try:
        return sp.run(args,
                      check=True,
                      encoding='utf-8',
                      env=env,
                      stdout=sp.PIPE,
                      stderr=sp.PIPE).returncode
    except (sp.CalledProcessError, FileNotFoundError):
        args[0] = 'grub-mkconfig'
        try:
            return sp.run(args,
                          check=True,
                          env=env,
                          encoding='utf-8',
                          stdout=sp.PIPE,
                          stderr=sp.PIPE).returncode
        except sp.CalledProcessError as e:
            log.error('Failed!')
            log.error('STDOUT: %s', e.stdout)
            log.error('STDERR: %s', e.stderr)
            return e.returncode

    raise RuntimeError('Should not reach here (after attempting to run '
                       'grub2?-mkconfig)')


def upgrade_kernel(num_cpus: Optional[int] = None) -> int:
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
    env = _minenv()
    kernel_list = sp.run(('eselect', '--colour=no', 'kernel', 'list'),
                         check=True,
                         stdout=sp.PIPE,
                         encoding='utf-8',
                         env=env).stdout
    lines = filter(None, map(str.strip, kernel_list.split('\n')))

    if not any(re.search(r'\*$', line) for line in lines):
        log.info('Select a kernel to upgrade to (eselect kernel set ...).')
        return 1
    if len(
            list(
                filter(
                    None,
                    sp.run(('eselect', '--colour=no', '--brief', 'kernel',
                            'list'),
                           stdout=sp.PIPE,
                           check=True,
                           encoding='utf-8',
                           env=env).stdout.split('\n')))) > 2:
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
    sp.run(('eselect', 'kernel', 'set', str(unselected)), check=True, env=env)
    return rebuild_kernel(num_cpus)


def kernel_command(func: Callable[[Optional[int]], int]) -> Callable[[], int]:
    """
    CLI entry point for the ``upgrade-kernel`` and ``rebuild-kernel`` commands.

    Parameters
    ----------
    func : callable
        A callable that accepts an integer representing number of CPUs.

    Returns
    -------
    callable
        Callable that takes no parameters and returns an integer.
    """
    @umask(new_umask=0o022)
    def ret() -> int:
        parser = argparse.ArgumentParser(__name__)
        parser.add_argument('-j',
                            '--number-of-jobs',
                            default=cpu_count() + 1,
                            type=int)
        try:
            return func(parser.parse_args().number_of_jobs)
        except KernelConfigError:
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
