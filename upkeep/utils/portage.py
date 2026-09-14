"""Queries against Portage's own configuration."""
from __future__ import annotations

from pathlib import Path
import logging
import subprocess as sp

from .misc import CommandRunner

__all__ = ('PORTAGE_ENV_FALLBACKS', 'binary_package_directory', 'build_directory', 'portage_env')

logger = logging.getLogger(__name__)

PORTAGE_ENV_FALLBACKS = {
    'PKGDIR': '/var/cache/binpkgs',
    'PORTAGE_TMPDIR': '/var/tmp'  # ruff: ignore[hardcoded-temp-file]
}
"""
Portage's own defaults, used when ``portageq`` cannot be run or returns nothing.

:meta hide-value:
"""


def portage_env(name: str) -> str:
    """
    Read a Portage configuration variable with ``portageq envvar``.

    Parameters
    ----------
    name : str
        Name of the variable, such as ``PKGDIR``.

    Returns
    -------
    str
        The value reported by Portage, or the matching entry in
        :py:data:`PORTAGE_ENV_FALLBACKS` if ``portageq`` is unavailable or reports nothing.
    """
    try:
        value = CommandRunner.run(('portageq', 'envvar', name), stdout=sp.PIPE).stdout.strip()
    except (OSError, sp.CalledProcessError):
        logger.warning('Could not read `%s` from portageq. Assuming the default.', name)
        value = ''
    return value or PORTAGE_ENV_FALLBACKS.get(name, '')


def build_directory() -> Path:
    """
    Locate the directory Portage builds packages in.

    Returns
    -------
    pathlib.Path
        ``${PORTAGE_TMPDIR}/portage``, which is ``/var/tmp/portage`` only when ``PORTAGE_TMPDIR``
        is left at its default.
    """
    return Path(portage_env('PORTAGE_TMPDIR')) / 'portage'


def binary_package_directory() -> Path:
    """
    Locate the directory Portage stores binary packages in.

    Returns
    -------
    pathlib.Path
        The value of ``PKGDIR``.
    """
    return Path(portage_env('PKGDIR'))
