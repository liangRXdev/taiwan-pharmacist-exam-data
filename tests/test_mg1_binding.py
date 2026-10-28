"""MG-1 證據綁定（spec §5.4 E5、§6.2）：審查結果必須綁 L2 內容與考試日期來源，否則人工判定可被靜默沿用。"""

import copy
import json

import pytest

from tped import jsonio
from tped.build import eligible, review, run

REVS = {"P1": {"Q": "q1"}}
SAMPLE = ["a", "b"]
DIGESTS = {"a": "sha256:aa", "b": "sha256:bb"}
EXAM = {"exam_code": "114020", "exam_date": "2025-01-19", "exam_date_source_url": "https://example/114020", "exam_date_source_quote": "…"}


def _review(**kw):
    r = {"revs": REVS, "exam_date": EXAM["exam_date"], "exam_date_source_url": EXAM["exam_date_source_url"],
         "exam_date_source_quote": "考試日期： 114/1/17~1/19",
         "items": [{"id": i, "labels": [], "l2_digest": DIGESTS[i], "result": "pass", "reviewer": "LG", "note": ""} for i in SAMPLE]}
    r.update(kw)
    return r


def _v(r, digests=DIGESTS, exam=EXAM):
    return run._review_verdict(r, SAMPLE, digests=digests, exam=exam)["result"]


def test_bound_review_passes():
    assert _v(_review()) == "pass"


# ---------- #2 l2_digest ----------

def test_l2_digest_mismatch_is_stale():
    """L2（題幹／選項／答案）改變而 revs 與樣本集合不變：舊人工判定不得沿用。"""
    assert _v(_review(), digests={**DIGESTS, "b": "sha256:changed"}) == "stale"


def test_partial_l2_digest_is_stale():
    r = _review()
    del r["items"][0]["l2_digest"]
    assert _v(r) == "stale"


def test_missing_l2_digest_is_stale():
    """legacy 分支已移除（v0.11）：全部缺 l2_digest 亦判 stale，須以 review-backfill-digest 回填。"""
    r = _review()
    for it in r["items"]:
        del it["l2_digest"]
    assert _v(r) == "stale"


def test_l2_digest_definition():
    rec = {"stem": "題幹", "options": {"A": "甲", "B": "乙", "C": "丙", "D": "丁"}, "accepted_answers": [["A"]], "id": "x", "flags": []}
    d = eligible.l2_digest(rec)
    assert d.startswith("sha256:") and len(d) == 71
    assert eligible.l2_digest({**rec, "flags": ["script_chars"], "id": "y"}) == d, "只涵蓋 stem/options/accepted_answers"
    for k, v in (("stem", "題幹。"), ("options", {**rec["options"], "D": "戊"}), ("accepted_answers", [["B"]])):
        assert eligible.l2_digest({**rec, k: v}) != d, k


# ---------- #5 考試日期來源 ----------

@pytest.mark.parametrize("field,value", [("exam_date", "2025-01-18"), ("exam_date_source_url", "https://example/other")])
def test_exam_date_source_mismatch_is_stale(field, value):
    assert _v(_review(**{field: value})) == "stale"


def test_exam_inputs_missing_but_review_has_date_is_stale():
    assert _v(_review(), exam=None) == "stale"


# ---------- Low：items 重複、空白審查者 ----------

def test_duplicate_item_ids_is_stale():
    r = _review()
    r["items"].append(copy.deepcopy(r["items"][1]))
    assert _v(r) == "stale"


def test_whitespace_reviewer_is_pending():
    r = _review()
    r["items"][0]["reviewer"] = "  "
    assert _v(r) == "pending"


# ---------- compile 產出與 review-init ----------

def test_compile_mg1_carries_l2_digest(compiled, by_id):
    for f in sorted((compiled["out"] / "intermediate" / "mg1").glob("*.json")):
        mg1 = json.loads(f.read_text(encoding="utf-8"))
        assert sorted(mg1["l2_digest"]) == mg1["sample"]
        for qid, d in mg1["l2_digest"].items():
            assert d == eligible.l2_digest(by_id[qid])


@pytest.fixture
def init_root(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ROOT", tmp_path)
    monkeypatch.setattr(review, "INPUTS_EXAMS_PATH", tmp_path / "inputs" / "exams.json")
    jsonio.dump([EXAM], tmp_path / "inputs" / "exams.json")
    jsonio.dump({"exam_code": "114020", "revs": REVS, "sample": SAMPLE, "labels": {"a": [], "b": ["edge"]},
                 "l2_digest": DIGESTS, "not_applicable": []}, tmp_path / "intermediate" / "mg1" / "114020.json")
    return tmp_path


def test_review_init_writes_l2_digest(init_root):
    assert review.main(["114020"]) == 0
    r = jsonio.load(init_root / "review" / "114020.json")
    assert {it["id"]: it["l2_digest"] for it in r["items"]} == DIGESTS
    assert run._review_verdict(r, SAMPLE, digests=DIGESTS, exam=EXAM)["result"] == "pending"


@pytest.mark.parametrize("code", ["../114020", "11402", "114020.json", "１１４０２０"])
def test_review_init_rejects_bad_exam_code(init_root, code, capsys):
    assert review.main([code]) == 2
    assert not (init_root / "review").exists()
