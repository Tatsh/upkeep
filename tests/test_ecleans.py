# SPDX-License-Identifier: MIT
from unittest.mock import patch

from upkeep.commands import ecleans

from .utils import SubprocessMocker


def test_ecleans_exception(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output4(('emerge', '--depclean', '--quiet'),
                          raise_=True,
                          check=True,
                          stdout=-1,
                          stderr=-1)
    with patch('upkeep.sp.run', side_effect=sp_mocker.get_output):
        assert ecleans() == 255


def test_ecleans(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output4(('emerge', '--depclean', '--quiet'),
                          check=True,
                          stdout=-1,
                          stderr=-1)
    sp_mocker.add_output4(('emerge', '--quiet', '@preserved-rebuild'),
                          check=True,
                          stdout=-1,
                          stderr=-1)
    with patch('upkeep.sp.run', side_effect=sp_mocker.get_output):
        assert ecleans() == 0
