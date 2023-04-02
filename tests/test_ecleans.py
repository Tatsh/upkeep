# SPDX-License-Identifier: MIT
from click.testing import CliRunner
from pytest_mock import MockFixture

from upkeep.commands import ecleans_command as ecleans
from upkeep.commands.ecleans import ECLEANS_COMMANDS

from .utils import SubprocessMocker


def test_ecleans_exception(sp_mocker: SubprocessMocker,
                           mocker: MockFixture) -> None:
    sp_mocker.add_output4(('emerge', '--depclean', '--quiet'),
                          raise_=True,
                          check=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code != 0


def test_ecleans(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    for command in ECLEANS_COMMANDS:
        sp_mocker.add_output4(command, check=True)
    mocker.patch('upkeep.utils.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code == 0
