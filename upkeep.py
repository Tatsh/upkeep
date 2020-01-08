from multiprocessing import cpu_count
from os import chdir, environ, umask
from os.path import basename, isfile, realpath
from pathlib import Path
from shlex import quote
from typing import Callable, Dict, Optional, Tuple
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

CONFIG_GZ = '/proc/config.gz'
GRUB_CFG = '/boot/grub/grub.cfg'
KERNEL_SRC_DIR = '/usr/src/linux'
OLD_KERNELS_DIR = '/var/lib/upkeep/old-kernels'
SPECIAL_ENV = ('USE', 'HOME', 'MAKEOPTS', 'CONFIG_PROTECT_MASK', 'LANG',
               'PATH', 'SHELL', 'CONFIG_PROTECT')
log: Optional[logging.Logger] = None


def _setup_logging_stdout(name: Optional[str] = None,
                          verbose: bool = False) -> None:
    global log
    name = name if name else basename(sys.argv[0])
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    channel = logging.StreamHandler(sys.stdout)
    channel.setFormatter(logging.Formatter('%(message)s'))
    channel.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.addHandler(channel)


class KernelConfigError(Exception):
    pass


def _minenv() -> Dict[str, str]:
    env = dict()
    for key in SPECIAL_ENV:
        if environ.get(key):
            env[key] = environ[key]
    return env


def esync() -> int:
    _setup_logging_stdout()
    assert log is not None
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

    return sp.run(('eix-sync', '-qH'), env=env).returncode


def ecleans() -> int:
    env = _minenv()
    sp.run(('emerge', '--depclean', '--quiet'), check=True, env=env)
    sp.run(('emerge', '--quiet', '@preserved-rebuild'), check=True, env=env)
    sp.run(('revdep-rebuild', '--quiet'), check=True, env=env)
    sp.run(('eclean-dist', '--deep'), check=True, env=env)
    return sp.run(['rm', '-fR'] +
                  list(map(str,
                           Path('/var/tmp/portage').glob('*')))).returncode


def emerges() -> int:
    _setup_logging_stdout()
    assert log is not None
    old_umask = umask(0o022)
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-a', '--ask', action='store_true')
    parser.add_argument('-L', '--no-live-rebuild', action='store_true')
    parser.add_argument('-P', '--no-preserved-rebuild', action='store_true')
    parser.add_argument('-D', '--no-daemon-reexec', action='store_true')
    parser.add_argument('-U', '--no-upgrade-kernel', action='store_true')
    args = parser.parse_args()

    live_rebuild = not args.no_live_rebuild
    preserved_rebuild = not args.no_preserved_rebuild
    daemon_reexec = not args.no_daemon_reexec
    up_kernel = not args.no_upgrade_kernel
    ask_arg = ['--ask'] if args.ask else []
    env = _minenv()

    try:
        sp.run(('emerge', '--oneshot', '--quiet', '--update', 'portage'),
               check=True,
               env=env)
        sp.run([
            'emerge', '--keep-going', '--with-bdeps=y', '--tree', '--quiet',
            '--update', '--deep', '--newuse', '@world'
        ] + ask_arg,
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
                sp.run(('which', 'systemctl'),
                       check=True,
                       stdout=sp.PIPE,
                       env=env)
                sp.run(('systemctl', 'daemon-reexec'), check=True, env=env)
            except sp.CalledProcessError:
                pass

        if up_kernel:
            return upgrade_kernel(None)
    finally:
        umask(old_umask)

    return 0


def rebuild_kernel(num_cpus: Optional[int]) -> int:
    assert log is not None
    if not num_cpus:
        num_cpus = cpu_count() + 1
    chdir(KERNEL_SRC_DIR)

    if not isfile('.config') and isfile(CONFIG_GZ):
        with gzip.open(CONFIG_GZ) as z:
            with open('.config', 'wb+') as f:
                f.write(z.read())
    if not isfile('.config'):
        raise KernelConfigError(
            'Will not build without a .config file present')

    suffix = ''
    with open('.config', 'r') as f2:
        for line in f2.readlines():
            if line.startswith('CONFIG_LOCALVERSION='):
                s = line.split('=')[-1].strip()[1:-1]
                if s:
                    suffix = s
                break

    env = _minenv()
    commands: Tuple[Tuple[str, ...], ...] = (
        ('make', 'oldconfig'),
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


def upgrade_kernel(num_cpus: Optional[int]) -> int:
    assert log is not None
    env = _minenv()
    kernel_list = sp.run(('eselect', '--colour=no', 'kernel', 'list'),
                         check=True,
                         stdout=sp.PIPE,
                         encoding='utf-8',
                         env=env).stdout
    lines = filter(None, map(str.strip, kernel_list.split('\n')))
    found = False

    for line in lines:
        if re.search(r'\*$', line):
            found = True
            break
    if not found:
        return 1

    b_lines = sp.run(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                     stdout=sp.PIPE,
                     check=True,
                     encoding='utf-8',
                     env=env).stdout
    b_lines_list = list(filter(None, b_lines.split('\n')))
    if len(b_lines_list) > 2:
        log.info('Unexpected number of lines (eselect --brief). Not updating '
                 'kernel.')
        return 1

    unselected = None
    for line in lines:
        if not line.endswith('*'):
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
    def ret() -> int:
        old_umask = umask(0o022)
        parser = argparse.ArgumentParser(__name__)
        parser.add_argument('-j',
                            '--number-of-jobs',
                            default=cpu_count() + 1,
                            type=int)
        _setup_logging_stdout()
        try:
            return func(parser.parse_args().number_of_jobs)
        finally:
            umask(old_umask)
        return 1

    return ret


upgrade_kernel_command = kernel_command(upgrade_kernel)
rebuild_kernel_command = kernel_command(rebuild_kernel)
