"""CLI 參數守門：旗標（含 --help）不得被忽略後直接執行有副作用之子命令。"""

import sys

import pytest

from tped import cli
from tped.acquire import oracle, run
from tped.build import review


@pytest.fixture
def no_side_effects(monkeypatch):
    def boom(argv):
        raise AssertionError(f"不應執行子命令：{argv}")
    for mod in (run, oracle, review):
        monkeypatch.setattr(mod, "main", boom)


def _exit(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["tped", *argv])
    with pytest.raises(SystemExit) as ei:
        cli.main()
    return ei.value.code


@pytest.mark.parametrize("argv,code", [
    (["--help"], 0),
    (["-h"], 0),
    (["acquire", "--help"], 0),
    (["acquire", "-h"], 0),
    (["oracle-check", "--help"], 0),
    (["review-init", "--help"], 0),
    (["acquire", "--dry-run"], 2),
    (["acquire", "extra"], 2),
    (["oracle-check", "x"], 2),
    (["review-init", "--force", "115090"], 2),
    ([], 2),
    (["nope"], 2),
])
def test_flags_never_run_subcommand(monkeypatch, no_side_effects, capsys, argv, code):
    assert _exit(monkeypatch, *argv) == code
    out = capsys.readouterr()
    assert "usage: tped" in (out.out if code == 0 else out.err)


def test_plain_acquire_still_runs(monkeypatch):
    called = []
    monkeypatch.setattr(run, "main", lambda argv: called.append(argv) or 0)
    assert _exit(monkeypatch, "acquire") == 0
    assert called == [[]]
