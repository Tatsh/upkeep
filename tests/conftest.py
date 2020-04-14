from typing import Iterator

import pytest

from .utils import SubprocessMocker


@pytest.fixture
def sp_mocker() -> Iterator[SubprocessMocker]:
    m = SubprocessMocker()
    yield m
    m.reset_output()
