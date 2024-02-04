"""Configuration for Pytest."""  # noqa: INP001
from collections.abc import Iterator
from typing import NoReturn
import os

from click.testing import CliRunner
import pytest

from .utils import SubprocessMocker

if os.getenv('_PYTEST_RAISE', '0') != '0':  # pragma no cover

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[None]) -> NoReturn:
        assert call.excinfo is not None
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[BaseException]) -> NoReturn:
        raise excinfo.value


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def sp_mocker() -> Iterator[SubprocessMocker]:
    m = SubprocessMocker()
    yield m
    m.reset_output()
