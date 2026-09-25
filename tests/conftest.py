import copy
import logging
from datetime import date

import pytest

from tped import manifest
from tped.build import run

logging.getLogger("pdfminer").setLevel(logging.ERROR)

RELEASE_DATE = date(2026, 9, 25)


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 完整 compile 兩次（AC-5）")


@pytest.fixture(scope="session")
def m():
    return manifest.load()


@pytest.fixture
def m_copy(m):
    return copy.deepcopy(m)


@pytest.fixture(scope="session")
def compiled(tmp_path_factory):
    out = tmp_path_factory.mktemp("compile")
    r = run.compile_all(RELEASE_DATE, out=out, render=False)
    r["out"] = out
    return r


@pytest.fixture(scope="session")
def records(compiled):
    return compiled["questions"]


@pytest.fixture(scope="session")
def by_id(records):
    return {r["id"]: r for r in records}
