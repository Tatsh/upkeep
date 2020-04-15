import sys

from pytest_mock.plugin import MockFixture

from upkeep import emerges

from .utils import SubprocessMocker


def test_upgrade_kernel_no_eselect_output(sp_mocker: SubprocessMocker,
                                          mocker: MockFixture) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-daemon-reexec'
    ]
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output='')
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    mocker.patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output)
    assert emerges() == 1


def test_upgrade_kernel_eselect_too_many_kernels(sp_mocker: SubprocessMocker,
                                                 mocker: MockFixture) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-daemon-reexec'
    ]
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' *\n \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' \n \n \n')
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    mocker.patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output)
    assert emerges() == 1


def test_upgrade_kernel_eselect_kernel_set_invalid_output_from_eselect(
        sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-daemon-reexec'
    ]
    sp_mocker.add_output3(('eselect', '--colour=no', 'kernel', 'list'),
                          stdout_output=' [3] *\n [4] \n')
    sp_mocker.add_output3(
        ('eselect', '--colour=no', '--brief', 'kernel', 'list'),
        stdout_output=' *\n \n')
    mocker.patch('upkeep.sp.run', side_effect=sp_mocker.get_output)
    mocker.patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output)
    assert emerges() == 1
