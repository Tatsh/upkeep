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
    try:
        sp.check_call(['which', 'layman'], stdout=sp.PIPE)
        sp.check_call(['layman', '-S'])
    except sp.CalledProcessError:
        pass
    try:
        sp.check_call(['eix-sync', '-qH'])
    except sp.CalledProcessError:
        print('You need to have eix-sync installed for this to work',
              file=sys.stderr)
        return 1


def ecleans():
    sp.check_call(['emerge', '--depclean', '--quiet'])
    sp.check_call(['emerge', '--quiet', '@preserved-rebuild'])
    sp.check_call(['revdep-rebuild', '--quiet'])
    sp.check_call(['eclean-dist', '--deep'])
    dirs = list(Path('/var/tmp/portage').glob('*'))
    sp.check_call(['rm', '-fR'] + dirs)


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

    try:
        sp.check_call(['emerge', '--oneshot', '--quiet', '--update',
                       'portage'])
        sp.check_call(['emerge', '--keep-going', '--with-bdeps=y', '--tree',
                       '--quiet', '--update', '--deep', '--newuse',
                       '@world'] + ask_arg)

        if live_rebuild:
            sp.check_call(['emerge', '--keep-going', '--quiet',
                           '@live-rebuild'])
        if preserved_rebuild:
            sp.check_call(['emerge', '--keep-going', '--quiet',
                           '@preserved-rebuild'])

        if daemon_reexec:
            try:
                sp.check_call(['which', 'systemctl'])
                sp.check_call(['systemctl', 'daemon-reexec'])
            except sp.CalledProcessError:
                pass

        if up_kernel:
            upgrade_kernel()
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

    sp.check_call(['make', 'oldconfig'])
    sp.check_call(['make', '-j{}'.format(num_cpus)])
    sp.check_call(['make', 'modules_install'])
    sp.check_call(['emerge',
                   '--quiet',
                   '--keep-going',
                   '--quiet-fail',
                   '--verbose',
                   '@module-rebuild',
                   '@x11-module-rebuild'])

    Path(OLD_KERNELS_DIR).mkdir(parents=True, exist_ok=True)
    sp.check_call([
        'find', '/boot',
        '-maxdepth', '1',
        '(',
        '-name', 'initramfs-*',
        '-o', '-name', 'vmlinuz-*',
        '-o', '-iname', 'System.map*',
        '-o', '-iname', 'config-*',
        ')',
        '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'])
    sp.check_call(['make', 'install'])
    kver_arg = '-'.join(realpath('.').split('-')[1:]) + suffix
    sp.check_call(['dracut', '--force', '--kver', kver_arg])
    sp.check_call(['grub2-mkconfig', '-o', GRUB_CFG])


def upgrade_kernel(suffix=None, num_cpus=None):
    lines = filter(None, map(str.strip,
                             sp.check_output(['eselect',  'kernel',  'list'])
                               .decode('utf-8')
                               .split('\n')))
    found = False

    for line in lines:
        if re.search(r'\*$', line):
            found = True
            break
    if not found:
        return 1

    blines = sp.check_output(['eselect', '--brief', 'kernel', 'list'])
    blines = list(filter(None, blines.decode('utf-8').split('\n')))
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

    sp.check_call(['eselect', 'kernel', 'set', str(unselected)])

    rebuild_kernel(num_cpus=num_cpus)


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
