import sys
from pathlib import Path

# The fakes module sits beside the tests.
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from pytest_socket import disable_socket


@pytest.fixture(autouse=True)
def _no_network() -> None:
    disable_socket()
