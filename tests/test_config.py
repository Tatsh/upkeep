from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from upkeep.config import load_config
from upkeep.exceptions import ConfigError
from upkeep.typing import UpkeepConfig

if TYPE_CHECKING:
    from pathlib import Path


def test_load_config_missing(tmp_path: Path) -> None:
    assert load_config(tmp_path / 'nope.toml') == {}


def test_load_config(tmp_path: Path) -> None:
    file = tmp_path / 'upkeeprc'
    file.write_text("[emerge]\nextra_args = ['--backtrack=1000']\n")
    assert load_config(file) == {'emerge': {'extra_args': ['--backtrack=1000']}}


def test_load_config_invalid(tmp_path: Path) -> None:
    file = tmp_path / 'upkeeprc'
    file.write_text('not toml at all = = =\n')
    with pytest.raises(ConfigError):
        load_config(file)


def test_load_config_documented_shape(tmp_path: Path) -> None:
    file = tmp_path / 'upkeeprc'
    file.write_text("[emerge]\n"
                    "extra_args = ['--backtrack=1000']\n"
                    '\n'
                    '[ecleans]\n'
                    "extra_purge_dirs = ['/home/portage']\n"
                    '\n'
                    '[sync]\n'
                    "post = ['true after']\n"
                    "pre = ['true before']\n")
    config = load_config(file)
    assert set(config) == set(UpkeepConfig.__annotations__)
    assert config['emerge']['extra_args'] == ['--backtrack=1000']
    assert config['ecleans']['extra_purge_dirs'] == ['/home/portage']
    assert config['sync']['post'] == ['true after']
    assert config['sync']['pre'] == ['true before']
