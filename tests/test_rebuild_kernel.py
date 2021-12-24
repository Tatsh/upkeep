# SPDX-License-Identifier: MIT
from pytest_mock.plugin import MockerFixture as MockFixture
from upkeep import CONFIG_GZ, KernelConfigError, rebuild_kernel

import pytest


def test_rebuild_kernel_no_config_yes_gz(mocker: MockFixture) -> None:
    def isfile(x: str) -> bool:
        if x == '.config':
            return False
        if x == CONFIG_GZ:
            return True
        raise Exception(x)

    mocker.patch('upkeep.isfile', new=isfile)
    open_f = mocker.patch('upkeep.open')
    gzip_open = mocker.patch('upkeep.gzip.open')
    with pytest.raises(KernelConfigError):
        rebuild_kernel()
    assert gzip_open.call_count == 1
    assert open_f.call_count == 1
