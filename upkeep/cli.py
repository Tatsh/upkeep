"""Helpers shared by every subcommand."""
from __future__ import annotations

from typing import TYPE_CHECKING

from bascom import setup_logging

if TYPE_CHECKING:
    import click

__all__ = ('start_logging',)


def start_logging(ctx: click.Context, *, debug: bool = False) -> None:
    """
    Configure logging for a subcommand.

    ``--debug`` is accepted by the ``upkeep`` group and by every subcommand, so the value given
    before the subcommand name is merged with the one given after it.

    Parameters
    ----------
    ctx : click.Context
        Context of the running command. The group stores its own ``--debug`` value in
        :py:attr:`click.Context.obj`, which subcommands inherit.
    debug : bool
        Value of the subcommand's own ``--debug`` flag.
    """
    setup_logging(debug=debug or bool((ctx.obj or {}).get('debug')),
                  loggers={'upkeep': {
                      'handlers': ('console',),
                      'propagate': False
                  }})
