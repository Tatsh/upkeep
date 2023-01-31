# SPDX-License-Identifier: MIT
from unittest.mock import patch

from click.testing import CliRunner

from upkeep.commands.ecleans import ECLEANS_COMMANDS, ecleans

from .utils import SubprocessMocker


def test_ecleans_exception(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output4(('emerge', '--depclean', '--quiet'),
                          raise_=True,
                          check=True)
    with patch('upkeep.utils.sp.run', side_effect=sp_mocker.get_output):
        assert CliRunner().invoke(ecleans).exit_code != 0


def test_ecleans(sp_mocker: SubprocessMocker) -> None:
    for command in ECLEANS_COMMANDS:
        sp_mocker.add_output4(command, check=True)
    with patch('upkeep.utils.sp.run', side_effect=sp_mocker.get_output):
        assert CliRunner().invoke(ecleans).exit_code == 0
