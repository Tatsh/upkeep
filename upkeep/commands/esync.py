from __future__ import annotations

import logging
import subprocess as sp

import click

from upkeep.utils import CommandRunner

__all__ = ('esync',)

logger = logging.getLogger(__name__)


@click.command()
@click.option('-d', '--debug', is_flag=True)
@click.option('-l', '--run-layman', is_flag=True)
def esync(*, debug: bool = False, run_layman: bool = False) -> None:
    """
    Sync Portage sources. Requires ``app-portage/eix`` to be installed.

    This runs the following:

    - ``layman -S`` (if ``-l`` is passed in CLI arguments and if it is
      available)
    - ``eix-sync``
    """
    runner = CommandRunner()
    if run_layman:
        try:
            runner.run(('bash', '-c', 'command -v layman'), stdout=sp.PIPE)
        except sp.CalledProcessError as e:
            logger.exception('You need to have app-portage/layman installed')
            raise click.Abort from e
        try:
            runner.run(('layman', '-S'))
        except sp.CalledProcessError as e:
            raise click.Abort from e
    try:
        runner.run(('bash', '-c', 'command -v eix-sync'), stdout=sp.PIPE)
    except sp.CalledProcessError as e:
        click.echo('You need to have app-portage/eix installed for this to work', err=True)
        raise click.Abort from e
    sync_args = ('-a',) if debug else ('-a', '-q', '-H')
    try:
        runner.run(('eix-sync', *sync_args), check=True)
    except sp.CalledProcessError as e:
        raise click.Abort from e
