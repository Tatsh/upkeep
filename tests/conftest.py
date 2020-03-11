from typing import Callable, Iterator

import pytest

from .utils import add_output as add_output_func, reset_output

AddOutput = Callable[..., None]


@pytest.fixture
def add_output() -> Iterator[AddOutput]:
    yield add_output_func
    reset_output()
