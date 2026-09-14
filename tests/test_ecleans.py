from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from upkeep.commands import ecleans_command as ecleans
from upkeep.commands.ecleans import ECLEANS_COMMANDS

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockFixture

    from .utils import SubprocessMocker


def _setup_dirs(mocker: MockFixture, tmp_path: Path) -> tuple[Path, Path]:
    build_dir = tmp_path / 'portage'
    build_dir.mkdir()
    pkgdir = tmp_path / 'binpkgs'
    pkgdir.mkdir()
    mocker.patch('upkeep.commands.ecleans.build_directory', return_value=build_dir)
    mocker.patch('upkeep.commands.ecleans.binary_package_directory', return_value=pkgdir)
    return build_dir, pkgdir


def test_ecleans_exception(sp_mocker: SubprocessMocker, mocker: MockFixture,
                           tmp_path: Path) -> None:
    _setup_dirs(mocker, tmp_path)
    sp_mocker.add_output4(('emerge', '--depclean', '--quiet'), raise_=True, check=True)
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code != 0


def test_ecleans(sp_mocker: SubprocessMocker, mocker: MockFixture, tmp_path: Path) -> None:
    _setup_dirs(mocker, tmp_path)
    for command in ECLEANS_COMMANDS:
        sp_mocker.add_output4(command, check=True)
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code == 0
    assert 'emaint --fix all' in sp_mocker.history


def test_ecleans_purges_build_directory(sp_mocker: SubprocessMocker, mocker: MockFixture,
                                        tmp_path: Path) -> None:
    build_dir, _ = _setup_dirs(mocker, tmp_path)
    leftover = build_dir / 'cat-pkg-1.0'
    leftover.mkdir()
    for command in ECLEANS_COMMANDS:
        sp_mocker.add_output4(command, check=True)
    sp_mocker.add_output4(('rm', '-fR', str(leftover)), check=True)
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code == 0
    assert f'rm -fR {leftover}' in sp_mocker.history


def test_ecleans_purges_extra_dirs(sp_mocker: SubprocessMocker, mocker: MockFixture,
                                   tmp_path: Path) -> None:
    _setup_dirs(mocker, tmp_path)
    extra = tmp_path / 'extra'
    extra.mkdir()
    leftover = extra / 'stale'
    leftover.mkdir()
    mocker.patch('upkeep.commands.ecleans.load_config',
                 return_value={'ecleans': {
                     'extra_purge_dirs': [str(extra)]
                 }})
    for command in ECLEANS_COMMANDS:
        sp_mocker.add_output4(command, check=True)
    sp_mocker.add_output4(('rm', '-fR', str(leftover)), check=True)
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code == 0
    assert f'rm -fR {leftover}' in sp_mocker.history


def test_ecleans_purges_empty_binary_packages(sp_mocker: SubprocessMocker, mocker: MockFixture,
                                              tmp_path: Path) -> None:
    _, pkgdir = _setup_dirs(mocker, tmp_path)
    empty = pkgdir / 'cat' / 'pkg-1.0.gpkg.tar'
    empty.parent.mkdir()
    empty.touch()
    kept = pkgdir / 'cat' / 'pkg-2.0.gpkg.tar'
    kept.write_bytes(b'data')
    for command in ECLEANS_COMMANDS:
        sp_mocker.add_output4(command, check=True)
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code == 0
    assert not empty.exists()
    assert kept.exists()


def test_ecleans_no_binary_package_directory(sp_mocker: SubprocessMocker, mocker: MockFixture,
                                             tmp_path: Path) -> None:
    _setup_dirs(mocker, tmp_path)
    mocker.patch('upkeep.commands.ecleans.binary_package_directory',
                 return_value=tmp_path / 'missing')
    for command in ECLEANS_COMMANDS:
        sp_mocker.add_output4(command, check=True)
    mocker.patch('upkeep.utils.misc.sp.run', new=sp_mocker.get_output)
    assert CliRunner().invoke(ecleans).exit_code == 0
