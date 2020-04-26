from unittest.mock import patch

from upkeep import ecleans

from .utils import SubprocessMocker


def test_ecleans_exception(sp_mocker: SubprocessMocker) -> None:
    sp_mocker.add_output4(('emerge', '--depclean', '--quiet'), raise_=True)
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert ecleans() == 255


def test_ecleans(sp_mocker: SubprocessMocker) -> None:
    with patch('upkeep.sp.check_call', side_effect=sp_mocker.get_output):
        assert ecleans() == 0
