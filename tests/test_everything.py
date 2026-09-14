from __future__ import annotations

from typing import TYPE_CHECKING
import subprocess as sp

from upkeep.commands import all_command as do_everything
from upkeep.exceptions import ConfigError

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockFixture


def test_do_everything(mocker: MockFixture, runner: CliRunner) -> None:
    command_runner = mocker.patch('upkeep.commands.everything.CommandRunner')
    emerges = mocker.patch('upkeep.commands.everything.emerges')
    ecleans = mocker.patch('upkeep.commands.everything.ecleans')
    assert runner.invoke(do_everything).exit_code == 0
    command_runner.check_call.assert_called_once_with(('emerge', '--sync'))
    assert emerges.call_count == 1
    assert ecleans.call_count == 1


def test_do_everything_no_sync(mocker: MockFixture, runner: CliRunner) -> None:
    command_runner = mocker.patch('upkeep.commands.everything.CommandRunner')
    emerges = mocker.patch('upkeep.commands.everything.emerges')
    mocker.patch('upkeep.commands.everything.ecleans')
    assert runner.invoke(do_everything, ('--no-sync',)).exit_code == 0
    assert command_runner.check_call.call_count == 0
    assert emerges.call_count == 1


def test_do_everything_no_clean(mocker: MockFixture, runner: CliRunner) -> None:
    mocker.patch('upkeep.commands.everything.CommandRunner')
    emerges = mocker.patch('upkeep.commands.everything.emerges')
    ecleans = mocker.patch('upkeep.commands.everything.ecleans')
    assert runner.invoke(do_everything, ('--no-clean',)).exit_code == 0
    assert emerges.call_count == 1
    assert ecleans.call_count == 0


def test_do_everything_sync_hooks(mocker: MockFixture, runner: CliRunner) -> None:
    command_runner = mocker.patch('upkeep.commands.everything.CommandRunner')
    mocker.patch('upkeep.commands.everything.emerges')
    mocker.patch('upkeep.commands.everything.ecleans')
    mocker.patch('upkeep.commands.everything.load_config',
                 return_value={'sync': {
                     'post': ['true after'],
                     'pre': ['true before', '']
                 }})
    assert runner.invoke(do_everything).exit_code == 0
    assert [call.args[0]
            for call in command_runner.check_call.call_args_list] == [['true', 'before'],
                                                                      ('emerge', '--sync'),
                                                                      ['true', 'after']]


def test_do_everything_sync_failure(mocker: MockFixture, runner: CliRunner) -> None:
    command_runner = mocker.patch('upkeep.commands.everything.CommandRunner')
    command_runner.check_call.side_effect = sp.CalledProcessError(1, ('emerge', '--sync'))
    emerges = mocker.patch('upkeep.commands.everything.emerges')
    assert runner.invoke(do_everything).exit_code != 0
    assert emerges.call_count == 0


def test_do_everything_bad_config(mocker: MockFixture, runner: CliRunner) -> None:
    mocker.patch('upkeep.commands.everything.CommandRunner')
    mocker.patch('upkeep.commands.everything.load_config', side_effect=ConfigError('/etc/upkeeprc'))
    emerges = mocker.patch('upkeep.commands.everything.emerges')
    assert runner.invoke(do_everything).exit_code != 0
    assert emerges.call_count == 0
