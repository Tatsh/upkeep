# SPDX-License-Identifier: MIT
from unittest.mock import patch
import subprocess as sp
import sys

from upkeep import emerges

from .utils import SubprocessMocker


def test_emerges_keyboard_interrupt(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output4(
        ['emerge', '--oneshot', '--update', 'portage', '--quiet'],
        raise_=True,
        raise_cls=KeyboardInterrupt)
    sys.argv = ['emerges']
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert emerges() == 1


def test_emerges_live_rebuild(sp_mocker: SubprocessMocker) -> None:
    sys.argv = [
        'emerges', '--no-preserved-rebuild', '--no-daemon-reexec',
        '--no-upgrade-kernel'
    ]
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert emerges() == 0
        assert (
            'emerge --keep-going --quiet @live-rebuild') in sp_mocker.history


def test_emerges_preserved_rebuild(sp_mocker: SubprocessMocker) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-daemon-reexec',
        '--no-upgrade-kernel'
    ]
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert emerges() == 0
        assert ('emerge --keep-going --quiet @preserved-rebuild'
                ) in sp_mocker.history


def test_emerges_daemon_reexec(sp_mocker: SubprocessMocker) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-upgrade-kernel'
    ]
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert emerges() == 0
        assert 'systemctl daemon-reexec' in sp_mocker.history


def test_emerges_daemon_reexec_no_systemd(sp_mocker: SubprocessMocker) -> None:
    sys.argv = [
        'emerges', '--no-live-rebuild', '--no-preserved-rebuild',
        '--no-upgrade-kernel'
    ]
    sp_mocker.add_output4(('which', 'systemctl'),
                          raise_=True,
                          stdout=sp.DEVNULL,
                          stderr=sp.DEVNULL)
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert emerges() == 0
        assert 'systemctl daemon-reexec' not in sp_mocker.history
