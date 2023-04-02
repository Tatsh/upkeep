# SPDX-License-Identifier: MIT
import subprocess as sp

from loguru import logger
import click

from ..utils import CommandRunner

__all__ = ('esync', )


@click.command()
@click.option('-d', '--debug', is_flag=True)
@click.option('-l', '--run-layman', is_flag=True)
def esync(debug: bool = False, run_layman: bool = False) -> None:
    """
    Syncs Portage sources. Requires ``app-portage/eix`` to be installed.

    This runs the following:

    - ``layman -S`` (if ``-l`` is passed in CLI arguments and if it is
      available)
    - ``eix-sync``
    """
    runner = CommandRunner()
    if run_layman:
        try:
            runner.run(('which', 'layman'))
        except sp.CalledProcessError as e:
            logger.error('You need to have app-portage/layman installed')
            raise click.Abort() from e
        try:
            runner.run(('layman', '-S'))
        except sp.CalledProcessError as e:
            raise click.Abort() from e
    try:
        runner.run(('which', 'eix-sync'))
    except sp.CalledProcessError as e:
        msg: str | None = None
        if e.returncode != 2:
            msg = 'You need to have app-portage/eix installed for this to work'
        raise click.Abort(msg) from e
    sync_args = ('-a', ) if debug else ('-a', '-q', '-H')
    try:
        runner.run(('eix-sync', ) + sync_args, check=True)
    except sp.CalledProcessError as e:
        raise click.Abort() from e
