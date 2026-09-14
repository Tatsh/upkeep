"""Configuration file handling."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
import logging

from tomlkit.exceptions import ParseError
import tomlkit

from upkeep.constants import DEFAULT_USER_CONFIG
from upkeep.exceptions import ConfigError

if TYPE_CHECKING:
    from upkeep.typing import UpkeepConfig

__all__ = ('load_config',)

logger = logging.getLogger(__name__)


def load_config(path: str | Path | None = None) -> UpkeepConfig:
    """
    Read the TOML configuration file.

    Parameters
    ----------
    path : str | pathlib.Path | None
        Path to the configuration file. Defaults to
        :py:data:`~upkeep.constants.DEFAULT_USER_CONFIG`.

    Returns
    -------
    UpkeepConfig
        The parsed configuration, or an empty mapping if the file does not exist.

    Raises
    ------
    upkeep.exceptions.ConfigError
        If the file exists but does not contain valid TOML.
    """
    file = Path(path or DEFAULT_USER_CONFIG)
    if not file.is_file():
        logger.debug('No configuration file at `%s`.', file)
        return {}
    logger.debug('Reading configuration from `%s`.', file)
    try:
        with file.open('rb') as f:
            return cast('UpkeepConfig', tomlkit.load(f))
    except ParseError as e:
        raise ConfigError(str(file)) from e
