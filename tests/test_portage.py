from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import subprocess as sp

import pytest

from upkeep.utils import binary_package_directory, build_directory, portage_env
from upkeep.utils.portage import PORTAGE_ENV_FALLBACKS

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from .utils import SubprocessMocker


def test_portage_env(sp_mocker: SubprocessMocker, mocker: MockFixture) -> None:
    sp_mocker.add_output3(('portageq', 'envvar', 'PKGDIR'), stdout_output='/home/binpkgs\n')
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert portage_env('PKGDIR') == '/home/binpkgs'


def test_portage_env_empty_output_falls_back(sp_mocker: SubprocessMocker,
                                             mocker: MockFixture) -> None:
    sp_mocker.add_output3(('portageq', 'envvar', 'PKGDIR'), stdout_output='\n')
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert portage_env('PKGDIR') == PORTAGE_ENV_FALLBACKS['PKGDIR']


@pytest.mark.parametrize('error',
                         [FileNotFoundError('portageq'),
                          sp.CalledProcessError(1, 'portageq')])
def test_portage_env_error_falls_back(error: Exception, mocker: MockFixture) -> None:
    mocker.patch('upkeep.utils.portage.CommandRunner.run', side_effect=error)
    assert portage_env('PORTAGE_TMPDIR') == PORTAGE_ENV_FALLBACKS['PORTAGE_TMPDIR']


def test_portage_env_unknown_variable(mocker: MockFixture) -> None:
    mocker.patch('upkeep.utils.portage.CommandRunner.run', side_effect=FileNotFoundError)
    assert not portage_env('NOT_A_PORTAGE_VARIABLE')


def test_build_directory_follows_portage_tmpdir(mocker: MockFixture) -> None:
    mocker.patch('upkeep.utils.portage.portage_env', return_value='/home')
    assert build_directory() == Path('/home/portage')


def test_binary_package_directory(mocker: MockFixture) -> None:
    mocker.patch('upkeep.utils.portage.portage_env', return_value='/home/binpkgs')
    assert binary_package_directory() == Path('/home/binpkgs')
