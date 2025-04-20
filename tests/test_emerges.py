from __future__ import annotations

from typing import TYPE_CHECKING
import subprocess as sp
import sys

from click.testing import CliRunner
from upkeep.commands import emerges_command as emerges

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from .utils import SubprocessMocker


def test_emerges_keyboard_interrupt(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output4(['emerge', '--oneshot', '--update', 'portage', '--quiet'],
                          raise_=True,
                          check=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(emerges).exit_code != 0


def test_emerges_live_rebuild(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output4(['emerge', '--oneshot', '--update', 'portage', '--quiet'], check=True)
    sp_mocker.add_output4(
        ['emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '@world', '--quiet'],
        check=True)
    sp_mocker.add_output4(['emerge', '--keep-going', '--quiet', '--usepkg=n', '@live-rebuild'],
                          check=True)
    sp_mocker.add_output4(['emerge', '--keep-going', '--quiet', '--usepkg=n', '@preserved-rebuild'],
                          check=True)
    sp_mocker.add_output4(['bash', '-c', 'command -v systemctl'],
                          check=True,
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output4(['systemctl', 'daemon-reexec'], check=True)
    sp_mocker.add_output3(['eselect', '--colour=no', 'kernel', 'list'], stdout_output='')
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(emerges).exit_code == 0
    assert ('emerge --keep-going --quiet --usepkg=n @live-rebuild') in sp_mocker.history


def test_emerges_preserved_rebuild(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sys.argv = ['emerges', '--no-live-rebuild', '--no-daemon-reexec', '--no-upgrade-kernel']
    sp_mocker.add_output4(('emerge', '--oneshot', '--update', 'portage', '--quiet'), check=True)
    sp_mocker.add_output4(
        ('emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '@world', '--quiet'),
        check=True)
    sp_mocker.add_output4(('emerge', '--keep-going', '--quiet', '--usepkg=n', '@preserved-rebuild'),
                          check=True)
    sp_mocker.add_output4(('emerge', '--keep-going', '--quiet', '--usepkg=n', '@live-rebuild'),
                          check=True)
    sp_mocker.add_output4(('bash', '-c', 'command -v systemctl'),
                          check=True,
                          stderr=sp.DEVNULL,
                          stdout=sp.DEVNULL)
    sp_mocker.add_output4(('systemctl', 'daemon-reexec'), check=True)
    sp_mocker.add_output3(['eselect', '--colour=no', 'kernel', 'list'], stdout_output='')
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(emerges).exit_code == 0
    assert ('emerge --keep-going --quiet --usepkg=n @preserved-rebuild') in sp_mocker.history


def test_emerges_daemon_reexec(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sys.argv = ['emerges', '--no-live-rebuild', '--no-preserved-rebuild', '--no-upgrade-kernel']
    sp_mocker.add_output4(('emerge', '--oneshot', '--update', 'portage', '--quiet'), check=True)
    sp_mocker.add_output4(
        ('emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '@world', '--quiet'),
        check=True)
    sp_mocker.add_output4(('emerge', '--keep-going', '--quiet', '--usepkg=n', '@live-rebuild'),
                          check=True)
    sp_mocker.add_output4(('emerge', '--keep-going', '--quiet', '--usepkg=n', '@preserved-rebuild'),
                          check=True)
    sp_mocker.add_output4(('bash', '-c', 'command -v systemctl'),
                          check=True,
                          stderr=sp.DEVNULL,
                          stdout=sp.DEVNULL)
    sp_mocker.add_output4(('systemctl', 'daemon-reexec'), check=True)
    sp_mocker.add_output3(['eselect', '--colour=no', 'kernel', 'list'], stdout_output='')
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(emerges).exit_code == 0
    assert 'systemctl daemon-reexec' in sp_mocker.history


def test_emerges_daemon_reexec_no_systemd(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sys.argv = ['emerges', '--no-live-rebuild', '--no-preserved-rebuild', '--no-upgrade-kernel']
    sp_mocker.add_output4(('emerge', '--oneshot', '--update', 'portage', '--quiet'), check=True)
    sp_mocker.add_output4(
        ('emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '@world', '--quiet'),
        check=True)
    sp_mocker.add_output4(('emerge', '--keep-going', '--quiet', '--usepkg=n', '@live-rebuild'),
                          check=True)
    sp_mocker.add_output4(('emerge', '--keep-going', '--quiet', '--usepkg=n', '@preserved-rebuild'),
                          check=True)
    sp_mocker.add_output4(('bash', '-c', 'command -v systemctl'),
                          raise_=True,
                          check=True,
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    sp_mocker.add_output3(['eselect', '--colour=no', 'kernel', 'list'], stdout_output='')
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    result = CliRunner().invoke(emerges)
    assert result.exit_code == 0
    assert 'systemctl daemon-reexec' not in sp_mocker.history


def test_emerges(mocker: MockFixture, runner: CliRunner) -> None:
    mocker.patch('upkeep.commands.emerges.CommandRunner')
    upgrade_kernel = mocker.patch('upkeep.commands.emerges.upgrade_kernel')
    result = runner.invoke(emerges, ('--no-upgrade-kernel'))
    assert result.exit_code == 0
    assert upgrade_kernel.call_count == 0
