# SPDX-License-Identifier: MIT
from multiprocessing import cpu_count
from subprocess import CalledProcessError
from typing import Any, TypeVar
import subprocess as sp

from click.testing import CliRunner
from pytest_mock.plugin import MockerFixture as MockFixture
import click
import pytest

from upkeep.commands import emerges_command as emerges
from upkeep.constants import GRUB_CFG, OLD_KERNELS_DIR
from upkeep.utils.kernel import _esp_path, _has_grub, upgrade_kernel

from .utils import SubprocessMocker


def test_upgrade_kernel_no_eselect_output(sp_mocker: SubprocessMocker,
                                          mocker: MockFixture) -> None:
    sp_mocker.add_output(('eselect', '--colour=no', 'kernel', 'list'),
                         stdout_output='',
                         check=True,
                         stdout=sp.PIPE)
    sp_mocker.add_output(('emerge', '--keep-going', '--tree', '--update',
                          '--deep', '--newuse', '@world', '--quiet'),
                         check=True)
    sp_mocker.add_output(
        ['emerge', '--oneshot', '--update', 'portage', '--quiet'], check=True)
    sp_mocker.add_output(
        ['emerge', '--keep-going', '--quiet', '@live-rebuild'], check=True)
    sp_mocker.add_output(
        ['emerge', '--keep-going', '--quiet', '@preserved-rebuild'],
        check=True)
    sp_mocker.add_output(['which', 'systemctl'],
                         check=True,
                         stdout=sp.DEVNULL,
                         stderr=sp.DEVNULL)
    sp_mocker.add_output(['systemctl', 'daemon-reexec'],
                         check=True,
                         stdout=None,
                         stderr=None)
    mocker.patch('upkeep.utils.kernel.glob', return_value=['.'])
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(
        emerges,
        ('--no-live-rebuild', '--no-preserved-rebuild', '--no-daemon-reexec',
         '--fatal-upgrade-kernel')).exit_code != 0


def test_upgrade_kernel_eselect_too_many_kernels(sp_mocker: SubprocessMocker,
                                                 mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' *\n \n')
    sp_mocker.add_output(('emerge', '--keep-going', '--tree', '--update',
                          '--deep', '--newuse', '@world', '--quiet'),
                         check=True)
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' \n \n \n')
    sp_mocker.add_output(
        ['emerge', '--oneshot', '--update', 'portage', '--quiet'], check=True)
    mocker.patch('upkeep.utils.kernel.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(
        emerges,
        ('--no-live-rebuild', '--no-preserved-rebuild', '--no-daemon-reexec',
         '--fatal-upgrade-kernel')).exit_code != 0


def test_upgrade_kernel_eselect_kernel_set_invalid_output_from_eselect(
        sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [3] *\n [4] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    mocker.patch('upkeep.utils.kernel.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(
        emerges,
        ('emerges', '--no-live-rebuild', '--no-preserved-rebuild',
         '--no-daemon-reexec', '--fatal-upgrade-kernel')).exit_code != 0


def test_upgrade_kernel_rebuild_no_config(mocker: MockFixture,
                                          sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.kernel.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.isfile', return_value=False)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n',
                          stderr=None,
                          stdout=sp.PIPE)
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    with pytest.raises(click.Abort):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_error_during_build(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.kernel.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.utils.kernel.Path')
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    mocker.patch('upkeep.utils.kernel.realpath',
                 return_value='/usr/src/linux-5.6.14-gentoo')
    mocker.patch('upkeep.utils.kernel.isfile', return_value=True)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.14-gentoo\n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' [1] linux-5.6.14-gentoo *\n \n')
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/efi')
    sp_mocker.add_output3(('dracut', '--force', '--kver', '5.6.14-gentoo'),
                          raise_=True)
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'oldconfig'), stdout=None)
    sp_mocker.add_output3(('make', f'-j{cpu_count() + 1}'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL,
                          raise_=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    with pytest.raises(CalledProcessError):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_error_during_grub(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.kernel.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.utils.kernel.Path')
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    mocker.patch('upkeep.utils.kernel.isfile', return_value=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(['grub2-mkconfig', '-o', GRUB_CFG],
                          raise_=True,
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(['grub-mkconfig', '-o', GRUB_CFG],
                          raise_=True,
                          stdout=None)
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'oldconfig'), stdout=None)
    sp_mocker.add_output3(('make', f'-j{cpu_count() + 1}'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'modules_install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
         '@module-rebuild', '@x11-module-rebuild'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
         '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
         'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          stdout=None)
    sp_mocker.add_output3(('dracut', '--force', '--kver', ''),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    with pytest.raises(CalledProcessError):
        upgrade_kernel()


T = TypeVar('T')


def test_upgrade_kernel_rebuild_systemd_boot_no_esp_path(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:

    def identity(x: T) -> T:
        return x

    _has_grub.cache_clear()
    etc_profile = '/etc/profile'
    mocker.patch('upkeep.utils.kernel.glob', return_value=[etc_profile])
    mocker.patch('upkeep.utils.kernel.Path')
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    mocker.patch('upkeep.utils.kernel.isfile', return_value=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    mocker.patch('upkeep.utils.kernel.lru_cache', new=identity)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.14-gentoo\n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' [1] *\n [2] linux-5.6.14-gentoo\n')
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          raise_=True)
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='')
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'oldconfig'), stdout=None)
    sp_mocker.add_output3(('make', f'-j{cpu_count() + 1}'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'modules_install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
         '@module-rebuild', '@x11-module-rebuild'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
         '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
         'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          stdout=None,
                          raise_=True)
    sp_mocker.add_output3(('dracut', '--force', '--kver', ''),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(['grub2-mkconfig', '-o', GRUB_CFG],
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(['grub-mkconfig', '-o', GRUB_CFG], stdout=None)
    sp_mocker.add_output(('grep', '-E', '^uefi="(yes|true)"', etc_profile),
                         check=True,
                         stdout=sp.DEVNULL,
                         stderr=sp.DEVNULL)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    with pytest.raises(click.Abort):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_systemd_boot_no_kernel_version(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:
    _esp_path.cache_clear()
    mocker.patch('upkeep.utils.kernel.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.utils.kernel.Path')
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    mocker.patch('upkeep.utils.kernel.isfile', return_value=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.14-gentoo\n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          raise_=True,
                          stdout=None)
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'oldconfig'), stdout=None)
    sp_mocker.add_output3(('make', f'-j{cpu_count() + 1}'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/efi')
    sp_mocker.add_output3(('bootctl', 'update'), stdout=None, stderr=sp.PIPE)
    sp_mocker.add_output3(('make', 'modules_install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
         '@module-rebuild', '@x11-module-rebuild'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
         '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
         'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('dracut', '--force', '--kver', ''),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(['grub2-mkconfig', '-o', GRUB_CFG],
                          raise_=True,
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    with pytest.raises(RuntimeError, match='Failed to detect Linux version'):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_systemd_boot_normal(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:

    class FakeFile:

        def __init__(self, content: bytes = b''):
            self.content = content

        def read(self, _count: int | None = None) -> bytes:
            return self.content

        def write(self, _value: Any) -> None:
            pass

        def readlines(self) -> list[Any]:
            return []

        def __enter__(self) -> 'FakeFile':
            return self

        def __exit__(self, _a: Any, _b: Any, _c: Any) -> None:
            pass

    class PathMock:

        def __init__(self, name: str):
            self.name = name

        def glob(self, _glob_str: str) -> list['PathMock']:
            if self.name == '/boot':
                return [PathMock('mz-file'), PathMock('not-mz-file')]
            return []

        def open(self, _mode: str) -> FakeFile:
            if self.name == 'mz-file':
                return FakeFile(b'MZ')
            return FakeFile()

        def mkdir(self, *args: Any, **kwargs: Any) -> None:
            pass

        def exists(self) -> bool:
            return False

        def unlink(self) -> None:
            pass

        def joinpath(self, *args: Any) -> 'PathMock':  # pylint: disable=unused-argument
            return self

    mocker.patch('upkeep.utils.kernel.glob', return_value=[])
    mocker.patch('upkeep.utils.kernel.Path', side_effect=PathMock)
    mocker.patch('upkeep.utils.kernel.shutil.copy')
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    mocker.patch('upkeep.utils.kernel.isfile', return_value=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.6-gentoo\n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          raise_=True)
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/boot/efi')
    sp_mocker.add_output3(('bootctl', 'status'), stdout_output='')
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'oldconfig'), stdout=None)
    sp_mocker.add_output3(('make', f'-j{cpu_count() + 1}'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'modules_install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('emerge', '--quiet', '--keep-going', '--quiet-fail', '--verbose',
         '@module-rebuild', '@x11-module-rebuild'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(
        ('find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
         '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
         'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'),
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'install'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          stdout=None)
    sp_mocker.add_output3(('dracut', '--force', '--kver', ''),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(['grub2-mkconfig', '-o', GRUB_CFG],
                          raise_=True,
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(['grub-mkconfig', '-o', GRUB_CFG], stdout=None)
    sp_mocker.add_output3(('bootctl', 'update'), stdout=None, stderr=sp.PIPE)
    mocker.patch('upkeep.utils.kernel._get_kernel_version',
                 return_value='5.6.6-gentoo')
    try:
        upgrade_kernel()
    except RuntimeError as e:
        pytest.fail(f'Unexpected RuntimeError: {e.args}')
