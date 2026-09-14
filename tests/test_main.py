from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from upkeep.main import main

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockerFixture

SUBCOMMANDS = ('all', 'ecleans', 'emerges', 'rebuild-kernel', 'upgrade-kernel')


@pytest.mark.parametrize('name', SUBCOMMANDS)
def test_main_lists_subcommand(name: str, runner: CliRunner) -> None:
    result = runner.invoke(main, ('--help',))
    assert result.exit_code == 0
    assert name in result.output


@pytest.mark.parametrize('name', SUBCOMMANDS)
def test_main_subcommand_accepts_debug(name: str, runner: CliRunner) -> None:
    result = runner.invoke(main, (name, '--help'))
    assert result.exit_code == 0
    assert '-d, --debug' in result.output


@pytest.mark.parametrize('args', [('-d', 'all'), ('all', '-d'), ('-d', 'all', '-d')])
def test_main_debug_either_side_of_subcommand(args: tuple[str, ...], mocker: MockerFixture,
                                              runner: CliRunner) -> None:
    setup_logging = mocker.patch('upkeep.cli.setup_logging')
    mocker.patch('upkeep.commands.everything.CommandRunner')
    mocker.patch('upkeep.commands.everything.emerges')
    mocker.patch('upkeep.commands.everything.ecleans')
    assert runner.invoke(main, args).exit_code == 0
    assert setup_logging.call_args.kwargs['debug'] is True


def test_main_without_debug(mocker: MockerFixture, runner: CliRunner) -> None:
    setup_logging = mocker.patch('upkeep.cli.setup_logging')
    mocker.patch('upkeep.commands.everything.CommandRunner')
    mocker.patch('upkeep.commands.everything.emerges')
    mocker.patch('upkeep.commands.everything.ecleans')
    assert runner.invoke(main, ('all',)).exit_code == 0
    assert setup_logging.call_args.kwargs['debug'] is False


def test_main_version(runner: CliRunner) -> None:
    result = runner.invoke(main, ('--version',))
    assert result.exit_code == 0
    assert '1.7.1' in result.output
