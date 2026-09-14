"""Module providing the ``emerges`` command to update the system."""
from __future__ import annotations

import subprocess as sp

import click

from upkeep.cli import start_logging
from upkeep.config import load_config
from upkeep.constants import DEFAULT_USER_CONFIG
from upkeep.decorators import umask
from upkeep.exceptions import ConfigError
from upkeep.utils import CommandRunner
from upkeep.utils.kernel import upgrade_kernel

__all__ = ('emerges',)


@click.command('emerges', context_settings={'help_option_names': ('-h', '--help')})
@click.option('--fatal-upgrade-kernel',
              is_flag=True,
              help='Exit with status > 0 if kernel upgrade cannot be done.')
@click.option('-D', '--no-daemon-reexec', is_flag=True, help='Do not run daemon-reexec (systemd).')
@click.option('-L', '--no-live-rebuild', is_flag=True, help='Skip the live-rebuild step.')
@click.option('-P', '--no-preserved-rebuild', is_flag=True, help='Skip the preserved-rebuild step.')
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
def emerges(ctx: click.Context,
            config: str | None = None,
            exclude: str | None = None,
            *,
            ask: bool = False,
            debug: bool = False,
            no_live_rebuild: bool = False,
            no_preserved_rebuild: bool = False,
            no_daemon_reexec: bool = False,
            no_upgrade_kernel: bool = False,
            fatal_upgrade_kernel: bool = False,
            verbose: bool = False) -> None:
    """
    Update Portage, ``@world``, and the kernel.

    \b
    - ``emerge --oneshot --quiet --update portage``
    - ``emerge --keep-going --tree --quiet --update --deep --newuse --with-bdeps=y @world``
    - ``emerge --usepkg=n --keep-going --quiet @live-rebuild``
    - ``emerge --usepkg=n --keep-going --quiet @preserved-rebuild``
    - ``systemctl daemon-reexec`` if applicable
    - upgrade kernel

    Anything listed under ``extra_args`` in the ``[emerge]`` table of the configuration file is
    appended to the ``@world`` update.
    """  # ruff: ignore[docstring-missing-exception, escape-sequence-in-docstring]
    start_logging(ctx, debug=debug)
    live_rebuild = not no_live_rebuild
    preserved_rebuild = not no_preserved_rebuild
    daemon_reexec = not no_daemon_reexec
    up_kernel = not no_upgrade_kernel
    ask_arg = ['--ask'] if ask else []
    verbose_arg = ['--verbose'] if verbose else ['--quiet']
    exclude_arg = [f'--exclude={exclude}'] if exclude else []
    try:
        extra_args = list(load_config(config).get('emerge', {}).get('extra_args', ()))
    except ConfigError as e:
        click.echo(str(e), err=True)
        raise click.Abort from e
    commands = [
        ['emerge', '--oneshot', '--update', 'portage', *verbose_arg],
        [
            'emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '--with-bdeps=y',
            '@world', *ask_arg, *verbose_arg, *exclude_arg, *extra_args
        ],
    ]
    if live_rebuild:
        commands.append(['emerge', '--keep-going', '--quiet', '--usepkg=n', '@live-rebuild'])
    if preserved_rebuild:
        commands.append(['emerge', '--keep-going', '--quiet', '--usepkg=n', '@preserved-rebuild'])
    try:
        for command in commands:
            CommandRunner.check_call(command)
    except sp.CalledProcessError as e:
        click.echo(str(e), err=True)
        raise click.Abort from e
    if daemon_reexec:
        try:
            CommandRunner.suppress_output(('bash', '-c', 'command -v systemctl'))
            CommandRunner.check_call(('systemctl', 'daemon-reexec'))
        except sp.CalledProcessError:
            pass
    if up_kernel:
        upgrade_kernel(None, fatal=fatal_upgrade_kernel)
