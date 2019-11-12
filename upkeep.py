from multiprocessing import cpu_count
from os import chdir, environ, umask
from os.path import isfile, realpath
from pathlib import Path
import argparse
import gzip
import re
import subprocess as sp
import sys

__all__ = [
    'ecleans',
    'emerges',
    'esync',
    'rebuild_kernel',
    'rebuild_kernel_command',
    'upgrade_kernel',
    'upgrade_kernel_command',
]

CONFIG_GZ = '/proc/config.gz'
GRUB_CFG = '/boot/grub/grub.cfg'
KERNEL_SRC_DIR = '/usr/src/linux'
OLD_KERNELS_DIR = '/root/.upkeep/old-kernels'
SPECIAL_ENV = ('USE', 'MAKEOPTS', 'CONFIG_PROTECT_MASK', 'LANG', 'PATH',
               'SHELL', 'CONFIG_PROTECT')


class KernelConfigError(Exception):
    pass


def _minenv():
    env = dict()
    for key in SPECIAL_ENV:
        if environ.get(key):
            env[key] = environ[key]


def esync():
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-l',
                        '--run-layman',
                        action='store_true',
                        help='Run "layman -S" if installed')
    args = parser.parse_args()
    env = _minenv()

    if args.run_layman:
        try:
            sp.run(['which', 'layman'], stdout=sp.PIPE, check=True, env=env)
            sp.run(['layman', '-S'], check=True, env=env)
        except sp.CalledProcessError:
            pass
    try:
        sp.run(['which', 'eix-sync'], stdout=sp.PIPE, check=True, env=env)
    except sp.CalledProcessError as e:
        if e.returncode != 2:
            print('You need to have eix-sync installed for this to work',
                  file=sys.stderr)
        return 1
    return sp.run(['eix-sync', '-qH'], env=env).returncode


def ecleans():
    env = _minenv()
    sp.run(['emerge', '--depclean', '--quiet'], check=True, env=env)
    sp.run(['emerge', '--quiet', '@preserved-rebuild'], check=True, env=env)
    sp.run(['revdep-rebuild', '--quiet'], check=True, env=env)
    sp.run(['eclean-dist', '--deep'], check=True, env=env)
    dirs = list(Path('/var/tmp/portage').glob('*'))
    return sp.run(['rm', '-fR'] + dirs).returncode


def emerges():
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
        sp.run(['emerge', '--oneshot', '--quiet', '--update', 'portage'],
               check=True)
        sp.run([
            'emerge', '--keep-going', '--with-bdeps=y', '--tree', '--quiet',
            '--update', '--deep', '--newuse', '@world'
        ] + ask_arg,
               check=True,
               env=env)

        if live_rebuild:
            sp.run(['emerge', '--keep-going', '--quiet', '@live-rebuild'],
                   check=True,
                   env=env)
        if preserved_rebuild:
            sp.run(['emerge', '--keep-going', '--quiet', '@preserved-rebuild'],
                   check=True,
                   env=env)

        if daemon_reexec:
            try:
                sp.run(['which', 'systemctl'],
                       check=True,
                       stdout=sp.PIPE,
                       env=env)
                sp.run(['systemctl', 'daemon-reexec'], check=True, env=env)
            except sp.CalledProcessError:
                pass

        if up_kernel:
            return upgrade_kernel()
    finally:
        umask(old_umask)


def rebuild_kernel(num_cpus=None):
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
    with open('.config', 'r') as f:
        for line in f.readlines():
            if line.startswith('CONFIG_LOCALVERSION='):
                s = line.split('=')[-1].strip()[1:-1]
                if s:
                    suffix = s
                break

    env = _minenv()
    sp.run(['make', 'oldconfig'], check=True, env=env)
    sp.run(['make', '-j{}'.format(num_cpus)], check=True, env=env)
    sp.run(['make', 'modules_install'], check=True, env=env)
    sp.run([
        'emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
        '@module-rebuild', '@x11-module-rebuild'
    ],
           check=True,
           env=env)

    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    sp.run([
        'find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
        '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
        'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'
    ],
           check=True,
           env=env)
    sp.run(['make', 'install'], check=True, env=env)
    kver_arg = '-'.join(realpath('.').split('-')[1:]) + suffix
    sp.run(['dracut', '--force', '--kver', kver_arg], check=True, env=env)

    args = ['grub2-mkconfig', '-o', GRUB_CFG]
    try:
        return sp.run(args, check=True, env=env).returncode
    except (sp.CalledProcessError, FileNotFoundError):
        args[0] = 'grub-mkconfig'
        return sp.run(args, check=True, env=env).returncode

    raise RuntimeError('Should not reach here (after attempting to run '
                       'grub2?-mkconfig)')


def upgrade_kernel(suffix=None, num_cpus=None):
    env = _minenv()
    kernel_list = sp.run(['eselect', '--colour=no', 'kernel', 'list'],
                         check=True,
                         stdout=sp.PIPE,
                         env=env).stdout.decode('utf-8')
    lines = filter(None, map(str.strip, kernel_list.split('\n')))
    found = False

    for line in lines:
        if re.search(r'\*$', line):
            found = True
            break
    if not found:
        return 1

    env = _minenv()
    blines = sp.run(['eselect', '--colour=no', '--brief', 'kernel', 'list'],
                    stdout=sp.PIPE,
                    check=True,
                    env=env).stdout.decode('utf-8')
    blines = list(filter(None, blines.split('\n')))
    if len(blines) > 2:
        print(('Unexpected number of lines (eselect --brief). '
               'Not updating kernel.'),
              file=sys.stderr)
        return 1

    unselected = None
    for line in lines:
        if not line.endswith('*'):
            unselected = int(re.search(r'^\[([0-9]+)\]', line).group(1))
            break

    if unselected not in (1, 2):
        print('Unexpected number of lines. Not updating kernel.',
              file=sys.stderr)
        return 1

    sp.run(['eselect', 'kernel', 'set', str(unselected)], check=True, env=env)

    return rebuild_kernel(num_cpus=num_cpus)


def kernel_command(func):
    def ret():
        old_umask = umask(0o022)
        parser = argparse.ArgumentParser(__name__)
        parser.add_argument('-j',
                            '--number-of-jobs',
                            default=cpu_count() + 1,
                            type=int)
        args = parser.parse_args()

        try:
            return func(num_cpus=args.number_of_jobs)
        except KeyboardInterrupt:
            pass
        finally:
            umask(old_umask)

    return ret


upgrade_kernel_command = kernel_command(upgrade_kernel)
rebuild_kernel_command = kernel_command(rebuild_kernel)
