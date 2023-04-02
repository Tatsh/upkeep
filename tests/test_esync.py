# SPDX-License-Identifier: MIT
from click.testing import CliRunner
from pytest_mock import MockFixture

from upkeep.commands import esync_command as esync

from .utils import SubprocessMocker


def test_esync_no_eix(sp_mocker: SubprocessMocker,
                      mocker: MockFixture) -> None:
    sp_mocker.add_output3(('which', 'eix-sync'), raise_=True, stdout=None)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync).exit_code != 0


def test_esync_no_layman(sp_mocker: SubprocessMocker,
                         mocker: MockFixture) -> None:
    sp_mocker.add_output3(('which', 'eix-sync'), stdout=None)
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'),
                          stdout=None,
                          raise_=True)
    sp_mocker.add_output3(('which', 'layman'), raise_=True, stdout=None)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync, ['-l']).exit_code != 0


def test_esync_layman(sp_mocker: SubprocessMocker,
                      mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'), stdout=None)
    sp_mocker.add_output3(('which', 'eix-sync'), stdout=None)
    sp_mocker.add_output3(('which', 'layman'), stdout=None)
    sp_mocker.add_output3(('layman', '-S'), stdout=None)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync, ['-l']).exit_code == 0


def test_esync_eix_sync_failure(sp_mocker: SubprocessMocker,
                                mocker: MockFixture) -> None:
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'), raise_=True)
    sp_mocker.add_output3(('which', 'layman'), raise_=True)
    sp_mocker.add_output3(('which', 'eix-sync'), stdout=None, raise_=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(esync).exit_code != 0
