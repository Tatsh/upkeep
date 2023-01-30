# SPDX-License-Identifier: MIT
from unittest.mock import patch
import sys

from upkeep.commands import esync

from .utils import SubprocessMocker


def test_esync_no_eix(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output3(('which', 'eix-sync'), raise_=True)
    sys.argv = ['esync']
    with patch('upkeep.sp.run', side_effect=sp_mocker.get_output):
        assert esync() == 1


def test_esync_no_layman(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output3(('eix-sync', '-qH'), returncode=0)
    sp_mocker.add_output3(('which', 'layman'), raise_=True)
    sys.argv = ['esync', '-l']
    with patch('upkeep.sp.run', side_effect=sp_mocker.get_output):
        assert esync() == 1


def test_esync_layman(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output3(('eix-sync', '-qH'), returncode=0)
    sp_mocker.add_output3(('which', 'layman'), returncode=0)
    sys.argv = ['esync', '-l']
    with patch('upkeep.sp.run', side_effect=sp_mocker.get_output):
        assert esync() == 0


def test_esync_eix_sync_failure(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output3(('eix-sync', '-a', '-q', '-H'), raise_=True)
    sys.argv = ['esync']
    with patch('upkeep.sp.run', side_effect=sp_mocker.get_output):
        assert esync() == 255
