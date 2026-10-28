"""`tped review-backfill-digest`（spec §6.2）：既有審查檔一次性回填 l2_digest。

只寫 l2_digest；前置檢查（revs、樣本、日期來源、全部 pass）不符、部分已有 digest、參數不合法 → 拒絕且檔案不變。
"""

import copy
import json

import pytest

from tped import jsonio
from tped.build import review_backfill, run

REVS = {"P1": {"Q": "sha256:q1", "ANS": "sha256:a1", "MOD": None, "mod_page": "sha256:p1"}}
SAMPLE = ["114-1-PHARM-P1-001", "114-1-PHARM-P1-002"]
DIGESTS = {SAMPLE[0]: "sha256:" + "a" * 64, SAMPLE[1]: "sha256:" + "b" * 64}
EXAM = {"exam_code": "114020", "exam_date": "2025-01-19", "exam_date_source_url": "https://example/114020",
        "exam_date_source_quote": "考試日期： 114/1/17~1/19"}


def _legacy_review(code="114020"):
    return {"exam_code": code, "revs": copy.deepcopy(REVS), "exam_date": EXAM["exam_date"], "exam_date_source_url": EXAM["exam_date_source_url"],
            "exam_date_source_quote": EXAM["exam_date_source_quote"], "not_applicable": [],
            "items": [{"id": i, "labels": ["edge"], "result": "pass", "reviewer": "LG", "note": ""} for i in SAMPLE]}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(review_backfill, "ROOT", tmp_path)
    monkeypatch.setattr(review_backfill, "INPUTS_EXAMS_PATH", tmp_path / "inputs" / "exams.json")
    jsonio.dump([EXAM, {**EXAM, "exam_code": "114090"}], tmp_path / "inputs" / "exams.json")
    for code in ("114020", "114090"):
        jsonio.dump({"exam_code": code, "seed": "s", "revs": copy.deepcopy(REVS), "sample": SAMPLE, "labels": {i: ["edge"] for i in SAMPLE},
                     "l2_digest": DIGESTS, "not_applicable": []}, tmp_path / "intermediate" / "mg1" / f"{code}.json")
    jsonio.dump(_legacy_review(), tmp_path / "review" / "114020.json")
    return tmp_path


def _bytes(root):
    return {p.name: p.read_bytes() for p in sorted((root / "review").iterdir())}


# ---------- 成功 ----------

def test_backfill_writes_only_l2_digest(root):
    before = jsonio.load(root / "review" / "114020.json")
    assert review_backfill.main(["114020"]) == 0
    after = jsonio.load(root / "review" / "114020.json")
    assert [list(it) for it in after["items"]] == [["id", "labels", "l2_digest", "result", "reviewer", "note"]] * 2
    assert {it["id"]: it["l2_digest"] for it in after["items"]} == DIGESTS
    stripped = copy.deepcopy(after)
    for it in stripped["items"]:
        del it["l2_digest"]
    assert stripped == before, "l2_digest 以外欄位不得改動"
    assert run._review_verdict(after, SAMPLE, digests=DIGESTS, exam=EXAM)["result"] == "pass"
    assert not list((root / "review").glob("*.tmp"))


def test_backfill_reports_count(root, capsys):
    assert review_backfill.main(["114020"]) == 0
    assert "114020：回填 2 題" in capsys.readouterr().out


def test_backfill_all(root, capsys):
    jsonio.dump(_legacy_review("114090"), root / "review" / "114090.json")
    assert review_backfill.main(["--all"]) == 0
    out = capsys.readouterr().out
    assert "114020：回填 2 題" in out and "114090：回填 2 題" in out
    assert all("l2_digest" in it for f in ("114020", "114090") for it in jsonio.load(root / "review" / f"{f}.json")["items"])


def test_backfill_already_complete_is_noop(root, capsys):
    assert review_backfill.main(["114020"]) == 0
    before = _bytes(root)
    assert review_backfill.main(["114020"]) == 0
    assert _bytes(root) == before
    assert "已有 l2_digest" in capsys.readouterr().out


# ---------- 拒絕：參數不合法 ----------

@pytest.mark.parametrize("argv", [[], ["../114020"], ["11402"], ["１１４０２０"], ["--force"], ["114020", "114090"], ["--all", "114020"]])
def test_backfill_rejects_bad_args(root, argv):
    before = _bytes(root)
    assert review_backfill.main(argv) == 2
    assert _bytes(root) == before


def test_backfill_rejects_missing_review(root):
    assert review_backfill.main(["114090"]) == 1


# ---------- 拒絕：前置檢查 ----------

@pytest.mark.parametrize("name,mutate", [
    ("revs 不符", lambda r: r["revs"]["P1"].update(Q="sha256:old")),
    ("樣本 id 不符", lambda r: r["items"][1].update(id="114-1-PHARM-P1-003")),
    ("樣本 id 重複", lambda r: r["items"].__setitem__(1, copy.deepcopy(r["items"][0]))),
    ("考試日期與 inputs 不符", lambda r: r.update(exam_date="2025-01-18")),
    ("未全部 pass", lambda r: r["items"][0].update(result=None)),
    ("有 fail", lambda r: r["items"][0].update(result="fail")),
    ("部分已有 digest", lambda r: r["items"][0].update(l2_digest=DIGESTS[SAMPLE[0]])),
])
def test_backfill_rejects_precondition(root, capsys, name, mutate):
    r = _legacy_review()
    mutate(r)
    jsonio.dump(r, root / "review" / "114020.json")
    before = _bytes(root)
    assert review_backfill.main(["114020"]) == 1, name
    assert _bytes(root) == before
    assert "拒絕" in capsys.readouterr().err


def test_backfill_all_validates_before_writing(root):
    """--all 任一檔不符 → 全部不寫（避免半套回填）。"""
    bad = _legacy_review("114090")
    bad["revs"] = {"P1": {**REVS["P1"], "Q": "sha256:old"}}
    jsonio.dump(bad, root / "review" / "114090.json")
    before = _bytes(root)
    assert review_backfill.main(["--all"]) == 1
    assert _bytes(root) == before


def test_backfill_atomic_on_write_failure(root, monkeypatch):
    before = _bytes(root)
    from pathlib import Path
    real = Path.write_bytes

    def partial(self, data):
        real(self, data[:10])
        raise OSError("No space left on device")

    monkeypatch.setattr(Path, "write_bytes", partial)
    with pytest.raises(OSError):
        review_backfill.main(["114020"])
    monkeypatch.setattr(Path, "write_bytes", real)
    assert _bytes(root) == before


def test_real_review_files_preconditions_hold(compiled):
    """repo 內 6 場審查檔：前置檢查（revs、樣本、日期來源、全部 pass）對本次 compile 成立。"""
    exams = run._load_exam_inputs()
    for f in sorted((run.ROOT / "review").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        mg1 = json.loads((compiled["out"] / "intermediate" / "mg1" / f.name).read_text(encoding="utf-8"))
        assert review_backfill.precondition_errors(r, mg1, exams.get(r["exam_code"]), require_missing=False) == [], f.name
