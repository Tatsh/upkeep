"""Module providing the ``ecleans`` command to perform various system clean-up tasks."""
from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING
import logging
import subprocess as sp

import click

from upkeep.cli import start_logging
from upkeep.config import load_config
from upkeep.constants import DEFAULT_USER_CONFIG
from upkeep.decorators import umask
from upkeep.exceptions import ConfigError
from upkeep.utils import CommandRunner, binary_package_directory, build_directory

if TYPE_CHECKING:
    from collections.abc import Iterator

    from upkeep.typing import UpkeepConfig

__all__ = ('ECLEANS_COMMANDS', 'ecleans')

logger = logging.getLogger(__name__)

ECLEANS_COMMANDS = (('emerge', '--depclean', '--quiet'),
                    ('emerge', '--quiet', '@preserved-rebuild'), ('revdep-rebuild', '--quiet'),
                    ('eclean-dist', '--deep'), ('eclean-pkg', '--deep'), ('emaint', '--fix', 'all'))
"""
Commands run by :py:func:`ecleans`, in order.

:meta hide-value:
"""


def _purge_directories(config: UpkeepConfig) -> None:
    if not (targets := [str(p) for d in _purge_roots(config) for p in d.glob('*')]):
        logger.debug('Nothing to purge.')
        return
    logger.info('Purging %d entries.', len(targets))
    CommandRunner.check_call(('rm', '-fR', *targets))


def _purge_roots(config: UpkeepConfig) -> Iterator[Path]:
    for root in (build_directory(),
                 *(Path(d) for d in config.get('ecleans', {}).get('extra_purge_dirs', ()))):
        # A relative root would expand against the current directory and be handed to `rm -fR`.
        if not root.is_absolute():
            logger.warning('Refusing to purge relative path `%s`.', root)
            continue
        yield root


def _purge_empty_binary_packages() -> None:
    if not (pkgdir := binary_package_directory()).is_dir():
        logger.debug('`%s` is not a directory.', pkgdir)
        return
    for path in pkgdir.rglob('*'):
        with suppress(OSError):
            if path.is_file() and path.stat().st_size == 0:
                logger.info('Removing empty binary package `%s`.', path)
                path.unlink(missing_ok=True)


@click.command('ecleans', context_settings={'help_option_names': ('-h', '--help')})
@click.option('-c',
              '--config',
              default=DEFAULT_USER_CONFIG,
              help='Override configuration file path.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@click.pass_context
@umask(new_umask=0o022)
def ecleans(ctx: click.Context, config: str | None = None, *, debug: bool = False) -> None:
    """
    Remove build leftovers, unused packages, and stale distfiles.

    \b
    - Delete the contents of ``${PORTAGE_TMPDIR}/portage`` and any configured extra directories
    - ``emerge --depclean --quiet``
    - ``emerge --quiet @preserved-rebuild``
    - ``revdep-rebuild --quiet``
    - ``eclean-dist --deep``
    - ``eclean-pkg --deep``
    - ``emaint --fix all``
    - Delete zero-length files under ``PKGDIR``
    """  # ruff: ignore[docstring-missing-exception, escape-sequence-in-docstring]
    start_logging(ctx, debug=debug)
    try:
        _purge_directories(load_config(config))
        for command in ECLEANS_COMMANDS:
            CommandRunner.check_call(command)
    except (ConfigError, sp.CalledProcessError) as e:
        click.echo(str(e), err=True)
        raise click.Abort from e
    _purge_empty_binary_packages()
