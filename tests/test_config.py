from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from upkeep.config import load_config
from upkeep.exceptions import ConfigError

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
