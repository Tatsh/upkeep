from __future__ import annotations

from multiprocessing import cpu_count
from subprocess import CalledProcessError
from typing import TYPE_CHECKING, Any, TypeVar
import subprocess as sp

from click.testing import CliRunner
from typing_extensions import Self, override
from upkeep.commands import emerges_command as emerges
from upkeep.constants import OLD_KERNELS_DIR
from upkeep.exceptions import KernelConfigMissing, NoValueIsUnselected
from upkeep.utils.kernel import upgrade_kernel
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from pytest_mock.plugin import MockerFixture as MockFixture

    from .utils import SubprocessMocker

T = TypeVar('T')


def method_return(return_value: T) -> Callable[[], T]:
    def cb() -> T:
        return return_value

    return cb


def method_return1(return_value: T) -> Callable[[Any, Any], T]:
    def cb(self: Any, x: Any) -> T:
        return return_value

    return cb


def test_upgrade_kernel_no_eselect_output(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output(('eselect', '--colour=no', 'kernel', 'list'),
                         stdout_output='',
                         check=True,
                         stdout=sp.PIPE)
    sp_mocker.add_output(
        ('emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '@world', '--quiet'),
        check=True)
    sp_mocker.add_output(['emerge', '--oneshot', '--update', 'portage', '--quiet'], check=True)
    sp_mocker.add_output(['emerge', '--keep-going', '--quiet', '@live-rebuild'], check=True)
    sp_mocker.add_output(['emerge', '--keep-going', '--quiet', '@preserved-rebuild'], check=True)
    sp_mocker.add_output(['bash', '-c', 'command -v systemctl'],
                         check=True,
                         stdout=sp.DEVNULL,
                         stderr=sp.DEVNULL)
    sp_mocker.add_output(['systemctl', 'daemon-reexec'], check=True, stdout=None, stderr=None)
    mocker.patch('upkeep.utils.kernel.Path').return_value.glob = method_return1(['.'])
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(emerges,
                              ('--no-live-rebuild', '--no-preserved-rebuild', '--no-daemon-reexec',
                               '--fatal-upgrade-kernel')).exit_code != 0


def test_upgrade_kernel_eselect_too_many_kernels(sp_mocker: SubprocessMocker,
                                                 mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'), stdout_output=' *\n \n')
    sp_mocker.add_output(
        ('emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '@world', '--quiet'),
        check=True)
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output=' \n \n \n')
    sp_mocker.add_output(['emerge', '--oneshot', '--update', 'portage', '--quiet'], check=True)
    mocker.patch('upkeep.utils.kernel.Path').return_value.glob = method_return1(['/etc/profile'])
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(emerges,
                              ('--no-live-rebuild', '--no-preserved-rebuild', '--no-daemon-reexec',
                               '--fatal-upgrade-kernel')).exit_code != 0


def test_upgrade_kernel_eselect_kernel_set_invalid_output_from_eselect(
        sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [3] *\n [4] \n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output=' *\n \n')
    mocker.patch('upkeep.utils.kernel.Path').return_value.glob = method_return1(['/etc/profile'])
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(emerges,
                              ('emerges', '--no-live-rebuild', '--no-preserved-rebuild',
                               '--no-daemon-reexec', '--fatal-upgrade-kernel')).exit_code != 0


def test_upgrade_kernel_rebuild_no_config(mocker: MockFixture, sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.kernel.Path').return_value.glob = method_return1(['/etc/profile'])
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.Path').return_value.is_file = method_return(
        return_value=False)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n',
                          stderr=None,
                          stdout=sp.PIPE)
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output=' *\n \n')
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    with pytest.raises(KernelConfigMissing):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_error_during_build(mocker: MockFixture,
                                                   sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.kernel.Path').return_value.glob = method_return1(['/etc/profile'])
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    mocker.patch('upkeep.utils.kernel.Path').return_value.is_file = method_return(return_value=True)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.14-gentoo\n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output=' [1] linux-5.6.14-gentoo *\n \n')
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/efi')
    sp_mocker.add_output3(('dracut', '--force', '--kver', '5.6.14-gentoo'), raise_=True)
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'oldconfig'), stdout=None)
    sp_mocker.add_output3(('make', f'-j{cpu_count() + 1}'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL,
                          raise_=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    with pytest.raises(CalledProcessError):
        upgrade_kernel()


def test_upgrade_kernel_rebuild_systemd_boot_normal(mocker: MockFixture,
                                                    sp_mocker: SubprocessMocker) -> None:
    class FakeFile:
        def __init__(self, content: bytes = b'') -> None:
            self.content = content

        def read(self, _count: int | None = None) -> bytes:
            return self.content

        def write(self, _value: Any) -> None:
            pass

        def readlines(self) -> list[Any]:
            return []

        def __enter__(self) -> Self:
            return self

        def __exit__(self, _a: type[BaseException] | None, _b: BaseException | None,
                     _c: TracebackType | None) -> None:
            pass

    class PathMock:
        def __init__(self, name: str) -> None:
            self.name = name

        def glob(self, _glob_str: str) -> list[PathMock]:
            if self.name == '/boot':
                return [PathMock('mz-file'), PathMock('not-mz-file')]
            if self.name == '/etc/dracut.conf.d':
                return [PathMock('/etc/dracut.conf.d/main.conf')]
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

        def joinpath(self, *args: Any) -> PathMock:
            return self

        def is_file(self) -> bool:
            return True

        @override
        def __str__(self) -> str:
            return self.name

    mocker.patch('upkeep.utils.kernel.Path', new=PathMock)
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.6-gentoo\n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output=' *\n \n')
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'), raise_=True)
    sp_mocker.add_output3(('bootctl', '-p'), stdout_output='/boot/efi')
    sp_mocker.add_output3(('bootctl', 'status'), stdout_output='')
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'oldconfig'), stdout=None)
    sp_mocker.add_output3(('make', f'-j{cpu_count() + 1}'), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'modules_install'), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp_mocker.add_output3(('emerge', '--keep-going', '@module-rebuild', '@x11-module-rebuild'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('find', '/boot', '-maxdepth', '1', '(', '-name', 'initramfs-*', '-o',
                           '-name', 'vmlinuz-*', '-o', '-iname', 'System.map*', '-o', '-iname',
                           'config-*', ')', '-exec', 'mv', '{}', OLD_KERNELS_DIR, ';'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(('make', 'install'), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp_mocker.add_output3(('eix', '--installed', '--exact', 'grub'), stdout=None)
    sp_mocker.add_output3(('bootctl', 'update'), stdout=None, stderr=sp.PIPE)
    sp_mocker.add_output3(('grep', '-E', '^uefi="(yes|true)"', '/etc/dracut.conf.d/main.conf'),
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    try:
        upgrade_kernel()
    except RuntimeError as e:
        pytest.fail(f'Unexpected RuntimeError: {e.args}')


def test_upgrade_kernel_eselect_kernel_non_fatal(mocker: MockFixture,
                                                 sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] linux-5.6.6-gentoo\n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output=' *\n \n \n')
    abort = mocker.patch('upkeep.utils.kernel.KernelConfigMissing')
    upgrade_kernel(fatal=False)
    assert abort.call_count == 0


def test_upgrade_kernel_no_config_non_fatal(mocker: MockFixture,
                                            sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [1] *\n [2] \n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output=' *\n \n')
    sp_mocker.add_output3(('eselect', 'kernel', 'set', '2'), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    mocker.patch('upkeep.utils.kernel.rebuild_kernel', side_effect=KernelConfigMissing)
    try:
        upgrade_kernel(fatal=False)
    except KernelConfigMissing:
        pytest.fail('KernelConfigMissing was raised')


def test_upgrade_kernel_eselect_no_selection(mocker: MockFixture,
                                             sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'), stdout_output='*\n\n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output='*\n\n')
    with pytest.raises(NoValueIsUnselected):
        upgrade_kernel()


def test_upgrade_kernel_eselect_no_selection2(mocker: MockFixture,
                                              sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output='[abc] *\n [abc]\n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output='*\n\n')
    with pytest.raises(NoValueIsUnselected):
        upgrade_kernel()


def test_upgrade_kernel_eselect_no_selection_non_fatal(mocker: MockFixture,
                                                       sp_mocker: SubprocessMocker) -> None:
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output='[abc] *\n [abc]\n')
    sp_mocker.add_output3(('eselect', '--colour=no', '--brief', 'kernel', 'list'),
                          stdout_output='*\n\n')
    try:
        upgrade_kernel(fatal=False)
    except NoValueIsUnselected:
        pytest.fail('NoValueIsUnselected was raised')
