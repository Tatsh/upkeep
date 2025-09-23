"""Module providing the ``ecleans`` command to perform various system clean-up tasks."""
from __future__ import annotations

from pathlib import Path
import subprocess as sp

from bascom import setup_logging
from upkeep.decorators import umask
from upkeep.utils import CommandRunner
import click

__all__ = ('ecleans',)
ECLEANS_COMMANDS = (
    ('emerge', '--depclean', '--quiet'), ('emerge', '--quiet', '@preserved-rebuild'),
    ('revdep-rebuild', '--quiet'), ('eclean-dist', '--deep'), ('eclean-pkg', '--deep'),
    ['rm', '-fR'] + [str(s) for s in Path('/var/tmp/portage').glob('*')])  # noqa: S108


@click.command('ecleans')
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@umask(new_umask=0o022)
def ecleans(*, debug: bool = False) -> None:
    """
    Run the following clean up commands:

    - ``emerge --depclean --quiet``
    - ``emerge --usepkg=n --quiet @preserved-rebuild``
    - ``revdep-rebuild --quiet` -- --usepkg=n``
    - ``eclean-dist --deep``
    - ``rm -fR /var/tmp/portage/*``
    """  # noqa: D400, DOC501
    setup_logging(debug=debug, loggers={'upkeep': {'handlers': ('console',), 'propagate': False}})
    try:
        for command in ECLEANS_COMMANDS:
            CommandRunner.check_call(command)
    except sp.CalledProcessError as e:
        raise click.Abort from e
