# SPDX-License-Identifier: MIT
from pytest_mock.plugin import MockerFixture as MockFixture
import pytest

from upkeep.constants import CONFIG_GZ
from upkeep.exceptions import KernelConfigError
from upkeep.utils.kernel import rebuild_kernel


def test_rebuild_kernel_no_config_yes_gz(mocker: MockFixture) -> None:
    def isfile(x: str) -> bool:
        if x == '.config':
            return False
        if x == CONFIG_GZ:
            return True
        raise Exception(x)  # pylint: disable=broad-exception-raised

    mocker.patch('upkeep.utils.kernel.isfile', new=isfile)
    mocker.patch('upkeep.utils.kernel.chdir')
    open_f = mocker.patch('upkeep.utils.kernel.open')
    gzip_open = mocker.patch('upkeep.utils.kernel.gzip.open')
    with pytest.raises(KernelConfigError):
        rebuild_kernel()
    assert gzip_open.call_count == 1
    assert open_f.call_count == 1
