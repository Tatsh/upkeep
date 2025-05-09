from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner
from upkeep.commands import esync_command as esync

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from .utils import SubprocessMocker


def test_esync_no_eix(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output3(('bash', '-c', 'command -v eix-sync'), raise_=True, stdout=-1)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync).exit_code != 0


def test_esync_no_layman(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output3(('bash', '-c', 'command -v eix-sync'), stdout=-1)
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'), stdout=None, raise_=True)
    sp_mocker.add_output3(('bash', '-c', 'command -v layman'), raise_=True, stdout=-1)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync, ['-l']).exit_code != 0


def test_esync_layman(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'), stdout=None)
    sp_mocker.add_output3(('bash', '-c', 'command -v eix-sync'), stdout=-1)
    sp_mocker.add_output3(('bash', '-c', 'command -v layman'), stdout=-1)
    sp_mocker.add_output3(('layman', '-S'), stdout=None)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync, ['-l']).exit_code == 0


def test_esync_layman_fail(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'), stdout=None)
    sp_mocker.add_output3(('bash', '-c', 'command -v eix-sync'), stdout=-1)
    sp_mocker.add_output3(('bash', '-c', 'command -v layman'), stdout=-1)
    sp_mocker.add_output3(('layman', '-S'), stdout=None, raise_=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync, ['-l']).exit_code != 0


def test_esync_eix_sync_failure(sp_mocker: SubprocessMocker, mocker: MockFixture,
                                runner: CliRunner) -> None:
    sp_mocker.add_output3(('bash', '-c', 'command -v eix-sync'), stdout=-1)
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'), stdout=None, raise_=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert runner.invoke(esync).exit_code != 0
