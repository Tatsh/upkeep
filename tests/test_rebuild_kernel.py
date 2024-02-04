# SPDX-License-Identifier: MIT
from click.testing import CliRunner
from pytest_mock.plugin import MockerFixture as MockFixture
import pytest

from upkeep.commands.kernel import kernel_command
from upkeep.constants import CONFIG_GZ
from upkeep.exceptions import KernelError
from upkeep.utils.kernel import rebuild_kernel


def test_rebuild_kernel_no_config_yes_gz(mocker: MockFixture) -> None:
    class FakePath:
        def __init__(self, s: str):
            self.s = s

        def is_file(self) -> bool:
            if self.s == '.config':
                return False
            if self.s == CONFIG_GZ:
                return True
            raise Exception(self.s)  # noqa: TRY002

    mocker.patch('upkeep.utils.kernel.Path', new=FakePath)
    mocker.patch('upkeep.utils.kernel.chdir')
    open_f = mocker.patch('upkeep.utils.kernel.open')
    gzip_open = mocker.patch('upkeep.utils.kernel.gzip.open')
    with pytest.raises(KernelError):
        rebuild_kernel(1)
    assert gzip_open.call_count == 1
    assert open_f.call_count == 1


def test_kernel_command_raises_abort(mocker: MockFixture, runner: CliRunner) -> None:
    def raise_(x: int | None) -> None:
        raise KernelError

    res = runner.invoke(kernel_command(raise_))
    assert res.return_value != 0
