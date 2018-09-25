from multiprocessing import cpu_count
from pathlib import Path
from os import chdir, umask
from os.path import isfile, realpath
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
    'upgrade_kernel',
    'rebuild_kernel_command',
    'upgrade_kernel_command',
]


CONFIG_GZ = '/proc/config.gz'
OLD_KERNELS_DIR = '/root/.upkeep/old-kernels'
GRUB_CFG = '/boot/grub/grub.cfg'
KERNEL_SRC_DIR = '/usr/src/linux'


class KernelConfigError(Exception):
    pass


def esync():
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-l', '--run-layman',
                        action='store_true',
                        help='Run "layman -S" if installed')
    args = parser.parse_args()

    if args.run_layman:
        try:
            sp.run(['which', 'layman'], stdout=sp.PIPE, check=True)
            sp.run(['layman', '-S'], check=True)
        except sp.CalledProcessError:
            pass
    try:
        sp.run(['which', 'eix-sync'], stdout=sp.PIPE, check=True)
    except sp.CalledProcessError as e:
        if e.returncode != 2:
            print('You need to have eix-sync installed for this to work',
                  file=sys.stderr)
        return 1
    return sp.run(['eix-sync', '-qH']).returncode


def ecleans():
    sp.run(['emerge', '--depclean', '--quiet'], check=True)
    sp.run(['emerge', '--quiet', '@preserved-rebuild'], check=True)
    sp.run(['revdep-rebuild', '--quiet'], check=True)
    sp.run(['eclean-dist', '--deep'], check=True)
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
    # Building bc will fail if BC_ENV_ARGS uses a file that Portage cannot read
    env = dict(BC_ENV_ARGS='')

    try:
        sp.run(['emerge', '--oneshot', '--quiet', '--update', 'portage'],
               check=True)
        sp.run(['emerge', '--keep-going', '--with-bdeps=y', '--tree',
                '--quiet', '--update', '--deep', '--newuse',
                '@world'] + ask_arg, check=True, env=env)

        if live_rebuild:
            sp.run(['emerge', '--keep-going', '--quiet', '@live-rebuild'],
                   check=True, env=env)
        if preserved_rebuild:
            sp.run(['emerge', '--keep-going', '--quiet', '@preserved-rebuild'],
                   check=True, env=env)

        if daemon_reexec:
            try:
                sp.run(['which', 'systemctl'], check=True, stdout=sp.PIPE)
                sp.run(['systemctl', 'daemon-reexec'], check=True)
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

    sp.run(['make', 'oldconfig'], check=True)
    sp.run(['make', '-j{}'.format(num_cpus)], check=True)
    sp.run(['make', 'modules_install'], check=True)
    sp.run(['emerge',
            '--quiet',
            '--keep-going',
            '--quiet-fail',
            '--verbose',
            '@module-rebuild',
            '@x11-module-rebuild'], check=True)

    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    sp.run(['find', '/boot',
            '-maxdepth', '1',
            '(',
            '-name', 'initramfs-*',
            '-o', '-name', 'vmlinuz-*',
            '-o', '-iname', 'System.map*',
            '-o', '-iname', 'config-*',
            ')',
            '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'], check=True)
    sp.run(['make', 'install'], check=True)
    kver_arg = '-'.join(realpath('.').split('-')[1:]) + suffix
    sp.run(['dracut', '--force', '--kver', kver_arg], check=True)
    return sp.run(['grub2-mkconfig', '-o', GRUB_CFG]).returncode


def upgrade_kernel(suffix=None, num_cpus=None):
    kernel_list = sp.run(['eselect', '--colour=no', 'kernel', 'list'],
                         check=True, stdout=sp.PIPE).stdout.decode('utf-8')
    lines = filter(None, map(str.strip, kernel_list.split('\n')))
    found = False

    for line in lines:
        if re.search(r'\*$', line):
            found = True
            break
    if not found:
        return 1

    blines = sp.run(['eselect', '--colour=no', '--brief', 'kernel', 'list'],
                    stdout=sp.PIPE,
                    check=True).stdout.decode('utf-8')
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

    if unselected not in (1, 2,):
        print('Unexpected number of lines. Not updating kernel.',
              file=sys.stderr)
        return 1

    sp.run(['eselect', 'kernel', 'set', str(unselected)], check=True)

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
