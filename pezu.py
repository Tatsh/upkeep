from multiprocessing import cpu_count
from pathlib import Path
from os import chdir, read, setsid, umask, write
from os.path import isfile, realpath
from select import select
from termios import tcgetattr, tcsetattr, TCSADRAIN
import argparse
import gzip
import pty
import re
import tty
import subprocess as sp
import sys


OLD_KERNELS_DIR = '/root/.pezu/old-kernels'
CONFIG_GZ = '/proc/config.gz'
GRUB_CFG = '/boot/grub/grub.cfg'
KERNEL_SRC_DIR = '/usr/src/linux'

DISPATCH_CONF_BUFFER_SIZE = 10240


def interactive_proc(command, timeout=2):
    """Based on this answer: https://stackoverflow.com/a/43012138/374110"""
    old_tty = tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())
    master_fd, slave_fd = pty.openpty()

    p = sp.Popen(command)
    try:
        p.wait(timeout=timeout)
    except sp.TimeoutExpired:
        p.kill()
        p = sp.Popen(command,
                     preexec_fn=setsid,
                     stdin=slave_fd,
                     stdout=slave_fd,
                     stderr=slave_fd,
                     universal_newlines=True)
        while p.poll() is None:
            r, w, e = select([sys.stdin, master_fd], [], [])
            if sys.stdin in r:
                d = read(sys.stdin.fileno(), DISPATCH_CONF_BUFFER_SIZE)
                write(master_fd, d)
            elif master_fd in r:
                o = read(master_fd, DISPATCH_CONF_BUFFER_SIZE)
                if o:
                    write(sys.stdout.fileno(), o)
    tcsetattr(sys.stdin, TCSADRAIN, old_tty)


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
    interactive_proc(['dispatch-conf'])


def emerges():
    old_umask = umask(0o022)
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-a', '--ask', action='store_true')
    parser.add_argument('-L', '--no-live-rebuild', action='store_true')
    parser.add_argument('-P', '--no-preserved-rebuild', action='store_true')
    parser.add_argument('-D', '--no-daemon-reexec', action='store_true')
    parser.add_argument('-U', '--no-upgrade-kernel', action='store_true')
    parser.add_argument('--kernel-suffix')
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
            upgrade_kernel(suffix=args.kernel_suffix)
    finally:
        umask(old_umask)


def rebuild_kernel(num_cpus=None, suffix=None):
    if not num_cpus:
        num_cpus = cpu_count() + 1
    chdir(KERNEL_SRC_DIR)

    if not isfile('.config') and isfile(CONFIG_GZ):
        with gzip.open(CONFIG_GZ) as z:
            with open('.config', 'wb+') as f:
                f.write(z.read())

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
    kver_suffix = suffix if suffix else ''
    kver_arg = '-'.join(realpath('.').split('-')[1:] + [kver_suffix])
    sp.check_call(['dracut', '--force', '--kver', kver_arg])
    sp.check_call(['grub2-mkconfig', '-o', GRUB_CFG])


def upgrade_kernel(suffix=None, num_cpus=None):
    p = sp.Popen(['eselect',  'kernel',  'list'], stdout=sp.PIPE)
    p.wait()
    lines = [x.decode('utf-8') for x in p.stdout.readlines()]

    found = False
    for line in lines:
        if re.search(r'\*$', line):
            found = True
            break

    if not found:
        return 1

    line_count = len(
        sp.check_output(['eselect', '--brief', 'kernel', 'list'])
          .decode('utf-8').split('\n'))
    if line_count > 2:
        print('Unexpected number of lines. Not updating kernel.',
              file=sys.stderr)
        return

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^\[[0-9]+\].*', line):
            unselected = int(re.search(r'^\[([0-9]+)\]', line).groups()[0])
            break

    if unselected not in (1, 2,):
        print('Unexpected number of lines. Not updating kernel.',
              file=sys.stderr)
        return

    sp.check_call(['eselect', 'kernel', 'set', str(unselected)])

    rebuild_kernel(num_cpus=num_cpus,
                   suffix=suffix)
