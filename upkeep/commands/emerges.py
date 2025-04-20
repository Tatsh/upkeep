from __future__ import annotations

import subprocess as sp

import click

from upkeep.constants import DEFAULT_USER_CONFIG
from upkeep.decorators import umask
from upkeep.utils import CommandRunner
from upkeep.utils.kernel import upgrade_kernel


@click.command('emerges')
@click.option('--fatal-upgrade-kernel',
              is_flag=True,
              help='Exit with status > 0 if kernel upgrade cannot be done')
@click.option('-D', '--no-daemon-reexec', is_flag=True, help='Do not run daemon-reexec (systemd)')
@click.option('-L', '--no-live-rebuild', is_flag=True, help='Skip the live-rebuild step')
@click.option('-P', '--no-preserved-rebuild', is_flag=True, help='Skip the preserved-rebuild step')
@click.option('-U', '--no-upgrade-kernel', is_flag=True, help='Skip upgrading the kernel')
@click.option('-a', '--ask', is_flag=True, help='Pass --ask to emerge')
@click.option('-c',
              '--config',
              default=DEFAULT_USER_CONFIG,
              help='Override configuration file path.')
@click.option('-e', '--exclude', metavar='ATOM')
@click.option('-v', '--verbose', is_flag=True, help='Pass --verbose to emerge and enable logging')
@umask(new_umask=0o022)
def emerges(config: str | None = None,
            exclude: str | None = None,
            *,
            ask: bool = False,
            no_live_rebuild: bool = False,
            no_preserved_rebuild: bool = False,
            no_daemon_reexec: bool = False,
            no_upgrade_kernel: bool = False,
            fatal_upgrade_kernel: bool = False,
            verbose: bool = False) -> None:
    """
    Run the following steps:

    - ``emerge --oneshot --quiet --update portage``
    - ``emerge --keep-going --tree --quiet --update --deep --newuse @world``
    - ``emerge --usepkg=n --keep-going --quiet @live-rebuild``
    - ``emerge --usepkg=n --keep-going --quiet @preserved-rebuild``
    - ``systemctl daemon-reexec`` if applicable
    - upgrade kernel

    This function understands the following CLI flags:

    - ``-a`` / ``--ask``: Pass ``--ask`` to the ``emerge @world`` command
    - ``-L`` / ``--no-live-rebuild``: Skip ``emerge @live-rebuild`` step
    - ``-P`` / ``--no-preserved-rebuild``: Skip ``emerge @preserved-rebuild``
      step
    - ``-D`` / ``--no-daemon-reexec``: Skip ``systemctl daemon-reexec`` step
    - ``-U`` / ``--no-upgrade-kernel``: Skip upgrading the kernel

    See Also
    --------
    upgrade_kernel
    """  # noqa: D400
    live_rebuild = not no_live_rebuild
    preserved_rebuild = not no_preserved_rebuild
    daemon_reexec = not no_daemon_reexec
    up_kernel = not no_upgrade_kernel
    ask_arg = ['--ask'] if ask else []
    verbose_arg = ['--verbose'] if verbose else ['--quiet']
    exclude_arg = [f'--exclude={x}' for x in exclude or []]
    runner = CommandRunner()
    try:
        runner.check_call(['emerge', '--oneshot', '--update', 'portage', *verbose_arg])
        runner.check_call([
            'emerge', '--keep-going', '--tree', '--update', '--deep', '--newuse', '@world',
            *ask_arg, *verbose_arg, *exclude_arg
        ])
        if live_rebuild:
            runner.check_call(('emerge', '--keep-going', '--quiet', '--usepkg=n', '@live-rebuild'))
        if preserved_rebuild:
            runner.check_call((
                'emerge',
                '--keep-going',
                '--quiet',
                '--usepkg=n',
                '@preserved-rebuild',
            ))
    except sp.CalledProcessError as e:
        click.echo(str(e), err=True)
        raise click.Abort from e
    if daemon_reexec:
        try:
            runner.suppress_output(('bash', '-c', 'command -v systemctl'))
            runner.check_call(('systemctl', 'daemon-reexec'))
        except sp.CalledProcessError:
            pass
    if up_kernel:
        upgrade_kernel(None, fatal=fatal_upgrade_kernel)
