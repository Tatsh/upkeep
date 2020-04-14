from unittest.mock import patch
import sys

from upkeep import emerges

from .utils import SubprocessMocker


def test_emerges_keyboard_interrupt(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output4(
        ('emerge', '--oneshot', '--quiet', '--update', 'portage'),
        raise_=True,
        raise_cls=KeyboardInterrupt)
    sys.argv = ['emerges']
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert emerges() == 1
