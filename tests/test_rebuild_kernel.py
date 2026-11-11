from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from upkeep.commands.kernel import kernel_command
from upkeep.constants import CONFIG_GZ
from upkeep.exceptions import KernelError
from upkeep.utils.kernel import rebuild_kernel

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def test_rebuild_kernel_no_config_yes_gz(mocker: MockerFixture) -> None:
    class FakePath:
        def __init__(self, s: str) -> None:
            self.s = s

        def write_bytes(self, _content: str, /) -> int:  # ruff:ignore[no-self-use]
            return 0

        def is_file(self) -> bool:
            if self.s == '.config':
                return False
            if self.s == CONFIG_GZ:
                return True
            raise Exception(self.s)  # ruff:ignore[raise-vanilla-class]

    mocker.patch('upkeep.utils.kernel.Path', new=FakePath)
    mocker.patch('upkeep.utils.kernel.chdir')
    mocker.patch('upkeep.utils.kernel.open')
    gzip_open = mocker.patch('upkeep.utils.kernel.gzip.open')
    with pytest.raises(KernelError):
        rebuild_kernel(1)
    assert gzip_open.call_count == 1


def test_kernel_command_raises_abort(mocker: MockerFixture, runner: CliRunner) -> None:
    def raise_(x: int | None) -> None:
        raise KernelError

    res = runner.invoke(kernel_command('test-kernel', raise_))
    assert res.return_value != 0


def test_rebuild_kernel_seeds_config_from_gz(mocker: MockerFixture, tmp_path) -> None:
    import gzip
    import os as _os

    config_gz = tmp_path / 'config.gz'
    with gzip.open(config_gz, 'wb') as gz:
        gz.write(b'CONFIG_SEEDED=y\n')
    build_dir = tmp_path / 'linux'
    build_dir.mkdir()
    mocker.patch('upkeep.utils.kernel.CONFIG_GZ', str(config_gz))
    mocker.patch('upkeep.utils.kernel.chdir', lambda _d: _os.chdir(str(build_dir)))
    mocker.patch('upkeep.utils.kernel.CommandRunner.check_call')
    mocker.patch('upkeep.utils.kernel.CommandRunner.suppress_output')
    rebuild_kernel(1)
    assert (build_dir / '.config').read_bytes() == b'CONFIG_SEEDED=y\n'
