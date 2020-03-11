from typing import Callable
from unittest.mock import patch
import subprocess as sp
import sys

from upkeep import _minenv, esync

from .utils import get_output

AddOutput = Callable[..., None]


def test_esync_no_eix(add_output: AddOutput) -> None:
    add_output(('which', 'eix-sync'),
               raise_=True,
               stdout=sp.PIPE,
               check=True,
               env=_minenv())
    sys.argv = ['esync']
    with patch('upkeep.sp.run', side_effect=get_output):
        assert esync() == 1


def test_esync(add_output: AddOutput) -> None:
    env = _minenv()
    add_output(('eix-sync', '-qH'), env=env, returncode=0)
    add_output(('which', 'layman'),
               stdout=sp.PIPE,
               check=True,
               env=env,
               returncode=0)
    add_output(('layman', '-S'), check=True, env=env, raise_=True)
    sys.argv = ['esync', '-l']
    with patch('upkeep.sp.run', side_effect=get_output):
        assert esync() == 0
