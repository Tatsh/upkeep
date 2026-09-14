"""Module providing the ``all`` command."""
from __future__ import annotations

from shlex import split
from typing import TYPE_CHECKING
import logging
import subprocess as sp

import click

from upkeep.cli import start_logging
from upkeep.config import load_config
from upkeep.constants import DEFAULT_USER_CONFIG
from upkeep.decorators import umask
from upkeep.exceptions import ConfigError
from upkeep.utils import CommandRunner

from .ecleans import ecleans
from .emerges import emerges

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ('SYNC_COMMAND', 'do_everything')

logger = logging.getLogger(__name__)

SYNC_COMMAND = ('emerge', '--sync')
"""Command used to synchronise the repositories.

:meta hide-value:
"""


def _run_hooks(entries: Iterable[str], when: str) -> None:
    for entry in entries:
        if not (argv := split(entry)):
            continue
        logger.info('Running %s-sync hook: %s', when, entry)
        CommandRunner.check_call(argv)


@click.command('all', context_settings={'help_option_names': ('-h', '--help')})
@click.option('--fatal-upgrade-kernel',
              is_flag=True,
              help='Exit with status > 0 if kernel upgrade cannot be done.')
@click.option('-C', '--no-clean', is_flag=True, help='Skip the clean-up stage.')
@click.option('-S', '--no-sync', is_flag=True, help='Skip synchronising the repositories.')
@click.option('-U', '--no-upgrade-kernel', is_flag=True, help='Skip upgrading the kernel.')
@click.option('-a', '--ask', is_flag=True, help='Pass --ask to emerge.')
@click.option('-c',
              '--config',
              default=DEFAULT_USER_CONFIG,
              help='Override configuration file path.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@click.option('-e', '--exclude', metavar='ATOM', help='Atom to exclude from the @world update.')
@click.option('-v', '--verbose', is_flag=True, help='Pass --verbose to emerge.')
@click.pass_context
@umask(new_umask=0o022)
def do_everything(ctx: click.Context,
                  config: str | None = None,
                  exclude: str | None = None,
                  *,
                  ask: bool = False,
                  debug: bool = False,
                  fatal_upgrade_kernel: bool = False,
                  no_clean: bool = False,
                  no_sync: bool = False,
                  no_upgrade_kernel: bool = False,
                  verbose: bool = False) -> None:
    """
    Sync, update, and clean in one pass.

    \b
    - ``emerge --sync``, wrapped by any configured ``[sync]`` hooks (skip with ``--no-sync``)
    - everything ``emerges`` does, including the kernel upgrade
    - everything ``ecleans`` does (skip with ``--no-clean``)
    """  # ruff: ignore[docstring-missing-exception, escape-sequence-in-docstring]
    start_logging(ctx, debug=debug)
    try:
        sync_config = load_config(config).get('sync', {})
    except ConfigError as e:
        click.echo(str(e), err=True)
        raise click.Abort from e
    if not no_sync:
        try:
            _run_hooks(sync_config.get('pre', ()), 'pre')
            CommandRunner.check_call(SYNC_COMMAND)
            _run_hooks(sync_config.get('post', ()), 'post')
        except sp.CalledProcessError as e:
            click.echo(str(e), err=True)
            raise click.Abort from e
    ctx.invoke(emerges,
               ask=ask,
               config=config,
               debug=debug,
               exclude=exclude,
               fatal_upgrade_kernel=fatal_upgrade_kernel,
               no_upgrade_kernel=no_upgrade_kernel,
               verbose=verbose)
    if not no_clean:
        ctx.invoke(ecleans, config=config, debug=debug)
