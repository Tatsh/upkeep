"""Main script."""
from __future__ import annotations

import click

from upkeep import __version__
from upkeep.commands import (
    all_command,
    ecleans_command,
    emerges_command,
    rebuild_kernel_command,
    upgrade_kernel_command,
)

__all__ = ('main',)


@click.group(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@click.version_option(__version__)
@click.pass_context
def main(ctx: click.Context, *, debug: bool = False) -> None:
    """
    Maintain a Gentoo system.

    ``--debug`` is also accepted by every subcommand, so it may be given on either side of the
    subcommand name.
    """
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug


main.add_command(all_command)
main.add_command(ecleans_command)
main.add_command(emerges_command)
main.add_command(rebuild_kernel_command)
main.add_command(upgrade_kernel_command)
