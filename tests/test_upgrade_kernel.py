# SPDX-License-Identifier: MIT
from subprocess import CalledProcessError
from typing import Any, Optional, TypeVar
import sys

from pytest_mock.plugin import MockerFixture as MockFixture
import click
import pytest

from upkeep.commands import emerges
from upkeep.constants import GRUB_CFG
from upkeep.utils.kernel import _esp_path, _has_grub, upgrade_kernel

from .utils import SubprocessMocker


def test_upgrade_kernel_no_eselect_output(sp_mocker: SubprocessMocker,
                                          mocker: MockFixture) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-daemon-reexec', '--fatal-upgrade-kernel'
    ]
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output='')
    mocker.patch('upkeep.glob', return_value=['.'])
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    with pytest.raises(click.Abort):
        emerges()


def test_upgrade_kernel_eselect_too_many_kernels(sp_mocker: SubprocessMocker,
                                                 mocker: MockFixture) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-daemon-reexec', '--fatal-upgrade-kernel'
    ]
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' *\n \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' \n \n \n')
    mocker.patch('upkeep.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    with pytest.raises(click.Abort):
        emerges()


def test_upgrade_kernel_eselect_kernel_set_invalid_output_from_eselect(
        sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-daemon-reexec', '--fatal-upgrade-kernel'
    ]
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [3] *\n [4] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    mocker.patch('upkeep.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    with pytest.raises(click.Abort):
        emerges()


def test_upgrade_kernel_rebuild_no_config(mocker: MockFixture,
                                          sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.chdir')
    mocker.patch('upkeep.isfile', return_value=False)
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    with pytest.raises(click.Abort):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_error_during_build(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.Path')
    mocker.patch('upkeep.chdir')
    mocker.patch('upkeep.open')
    mocker.patch('upkeep.realpath',
                 return_value='/usr/src/linux-5.6.14-gentoo')
    mocker.patch('upkeep.isfile', return_value=True)
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.14-gentoo\n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' [1] linux-5.6.14-gentoo *\n \n')
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/efi')
    sp_mocker.add_output3(('dracut', '--force', '--kver', '5.6.14-gentoo'),
                          raise_=True)
    with pytest.raises(CalledProcessError):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_error_during_grub(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.Path')
    mocker.patch('upkeep.chdir')
    mocker.patch('upkeep.open')
    mocker.patch('upkeep.isfile', return_value=True)
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(['grub2-mkconfig', '-o', GRUB_CFG], raise_=True)
    sp_mocker.add_output3(['grub-mkconfig', '-o', GRUB_CFG], raise_=True)
    with pytest.raises(CalledProcessError):
        upgrade_kernel()


T = TypeVar('T')


def test_upgrade_kernel_rebuild_systemd_boot_no_esp_path(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:

    def identity(x: T) -> T:
        return x

    _has_grub.cache_clear()
    mocker.patch('upkeep.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.Path')
    mocker.patch('upkeep.chdir')
    mocker.patch('upkeep.open')
    mocker.patch('upkeep.isfile', return_value=True)
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    mocker.patch('upkeep.lru_cache', side_effect=identity)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          raise_=True)
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='')
    with pytest.raises(click.Abort):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_systemd_boot_no_kernel_version(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:
    _esp_path.cache_clear()
    mocker.patch('upkeep.glob', return_value=['/etc/profile'])
    mocker.patch('upkeep.Path')
    mocker.patch('shutil.rmtree')
    mocker.patch('upkeep.chdir')
    mocker.patch('upkeep.open')
    mocker.patch('upkeep.isfile', return_value=True)
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          raise_=True)
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/efi')
    with pytest.raises(RuntimeError, match='Failed to detect Linux version'):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_systemd_boot_normal(
        mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:

    class FakeFile:

        def __init__(self, content: bytes = b''):
            self.content = content

        def read(self, _count: Optional[int] = None) -> bytes:
            return self.content

        def write(self, _value: Any):
            pass

        def readlines(self) -> list[Any]:
            return []

        def __enter__(self):
            return self

        def __exit__(self, _a: Any, _b: Any, _c: Any):
            pass

    class PathMock:

        def __init__(self, name: str):
            self.name = name

        def glob(self, _glob_str: str):
            if self.name == '/boot':
                return [PathMock('mz-file'), PathMock('not-mz-file')]
            return []

        def open(self, _mode: str):
            if self.name == 'mz-file':
                return FakeFile(b'MZ')
            return FakeFile()

        def mkdir(self, *args: Any, **kwargs: Any):
            pass

        def exists(self):
            return False

        def unlink(self):
            pass

        def joinpath(self, *args: Any):  # pylint: disable=unused-argument
            return self

    mocker.patch('upkeep.glob', return_value=[])
    mocker.patch('upkeep.Path', side_effect=PathMock)
    mocker.patch('upkeep.shutil.rmtree')
    mocker.patch('upkeep.shutil.copy')
    mocker.patch('upkeep.chdir')
    mocker.patch('upkeep.shutil.copyfile')
    mocker.patch('upkeep.open')
    mocker.patch('upkeep.isfile', return_value=True)
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.6-gentoo\n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'),
                          raise_=True)
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/boot/efi')
    sp_mocker.add_output3(('bootctl', 'status'), stdout_output='')
    mocker.patch('upkeep.utils.kernel._get_kernel_version',
                 return_value='5.6.6-gentoo')
    assert upgrade_kernel() is None
