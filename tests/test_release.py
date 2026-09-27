"""AC-5、AC-6、AC-8、MG-1。"""

import copy
import hashlib
from datetime import date, timedelta

import pytest

from tped import manifest
from tped.build import derive, eligible, run
from tped.config import ROOT
from conftest import RELEASE_DATE

REVS = {"P1": {"Q": "q1"}}


def _st(**kw):
    base = dict(exam_code="114020", subject="P1", parked_reason=None, answer_status="corrected", revs={"Q": "q1"})
    base.update(kw)
    return eligible.TupleState(**base)


GOOD_REVIEW = {"revs": REVS, "result": "pass"}
EXAM = date(2025, 2, 8)


# ---------- AC-6：E1–E5 逐項翻轉，手寫預期 ----------

@pytest.mark.parametrize("state,exam_date,review,expect_status,expect_reasons", [
    (_st(), EXAM, GOOD_REVIEW, "released", []),
    (_st(parked_reason="parse_fail"), EXAM, GOOD_REVIEW, "parked", ["parse_fail"]),               # E1/E2
    (_st(answer_status="unverified"), EXAM, GOOD_REVIEW, "withheld", ["unverified"]),             # E3
    (_st(), None, GOOD_REVIEW, "withheld", ["exam_date_missing"]),                                # E4
    (_st(), RELEASE_DATE - timedelta(days=89), GOOD_REVIEW, "withheld", ["too_recent"]),          # E4 邊界
    (_st(), RELEASE_DATE - timedelta(days=90), GOOD_REVIEW, "released", []),                      # E4 邊界
    (_st(), EXAM, None, "withheld", ["mg1_missing"]),                                             # E5
    (_st(), EXAM, {"revs": {"P1": {"Q": "old"}}, "result": "pass"}, "withheld", ["mg1_stale"]),   # E5
    (_st(), EXAM, {"revs": REVS, "result": "fail"}, "withheld", ["mg1_failed"]),                  # E5
    (_st(), EXAM, {"revs": REVS, "result": "pending"}, "withheld", ["mg1_pending"]),              # E5 未審完≠不符
    (_st(), EXAM, {"revs": REVS, "result": "stale"}, "withheld", ["mg1_stale"]),                  # E5 樣本不符
    (_st(answer_status="unverified"), None, None, "withheld", ["exam_date_missing", "mg1_missing", "unverified"]),
])
def test_ac6_eligibility(state, exam_date, review, expect_status, expect_reasons):
    wh = [] if state.parked_reason else eligible.withheld_reasons(state, exam_date, RELEASE_DATE, review, REVS)
    rec = eligible.coverage_record(state, wh)
    assert (rec["status"], rec["reasons"]) == (expect_status, expect_reasons)


def test_ac6_release_equals_eligible(compiled):
    released = {(c["exam_code"], c["subject"]) for c in compiled["coverage"] if c["status"] == "released"}
    got = {(r["exam_code"], r["subject"]) for r in compiled["release"]}
    assert got == released
    # 不依賴審查進度：MG-1 證據未全數 pass 之場次，不得有任何科目放行
    import json
    mg1 = {c["exam_code"]: json.loads((compiled["out"] / "intermediate" / "mg1" / f"{c['exam_code']}.json").read_text(encoding="utf-8"))
           for c in compiled["coverage"]}
    for code, m in mg1.items():
        v = run._review_verdict(run._load_review(code), m["sample"])
        if v is None or v["result"] != "pass" or v["revs"] != m["revs"]:
            assert not any(e == code for e, _ in released), f"{code} MG-1 未通過卻放行"
    mg1_reasons = {"mg1_missing", "mg1_stale", "mg1_pending", "mg1_failed"}
    assert all(set(c["reasons"]) & mg1_reasons for c in compiled["coverage"]
               if c["status"] == "withheld" and not {"unverified", "exam_date_missing", "too_recent"} & set(c["reasons"]))


# ---------- AC-8：MOD 判定與 original ----------

def _t(m, code="114020", p="P4"):
    return copy.deepcopy(manifest.tuple_of(m, code, p))


def test_ac8_absent_and_present(m):
    assert derive.mod_judgement(m, _t(m, "114020", "P4")).result == "absent"
    assert derive.mod_judgement(m, _t(m, "114020", "P3")).result == "present"


def test_ac8_counterexamples(m):
    t = _t(m)
    t["current"]["Q"] = manifest.tuple_of(m, "114020", "P5")["current"]["Q"]
    t["revisions"] += manifest.tuple_of(m, "114020", "P5")["revisions"]
    assert derive.mod_judgement(m, t).result == "inconclusive", "positive control 之 Q ≠ current.Q"
    mc = copy.deepcopy(m)
    t2 = manifest.tuple_of(mc, "114020", "P4")
    manifest.page_by_rev(mc, t2["mod_page_rev"])["final_url"] = "https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx?y=2025&e=114010"
    assert derive.mod_judgement(mc, t2).result == "inconclusive", "頁面 redirect"
    manifest.page_by_rev(mc, t2["mod_page_rev"])["http_status"] = 404
    assert derive.mod_judgement(mc, t2).result == "inconclusive", "404 不是 absent"
    t3 = _t(m)
    t3["mod_page_rev"] = None
    assert derive.mod_judgement(m, t3).result == "inconclusive"


def test_ac8_ninety_day_window(m):
    jd = derive.mod_judgement(m, _t(m))
    assert derive.original_allowed(jd, jd.fetched_on - timedelta(days=90))
    assert not derive.original_allowed(jd, jd.fetched_on - timedelta(days=60)), "absent 觀測在考後第 60 天"
    assert not derive.original_allowed(jd, None)


def test_ac8_real_status(records):
    """original 必須附 mod_page_rev；115090（科目頁抓取時考後僅 68 天）之 ANS-only 科目不得為 original。"""
    assert {r["answer_status"] for r in records} <= {"corrected", "unverified", "original"}
    assert not any(r["answer_status"] == "original" and r["source"]["mod_page_rev"] is None for r in records)
    ans_only_115090 = [r for r in records if r["exam_code"] == "115090" and r["source"]["mod_rev"] is None]
    assert ans_only_115090 and all(r["answer_status"] == "unverified" for r in ans_only_115090)
    assert any(r["answer_status"] == "original" for r in records)


def test_ac8_too_recent(compiled):
    cov = [c for c in compiled["coverage"] if c["exam_code"] == "115090"]
    assert cov and all("too_recent" in c["reasons"] for c in cov)


# ---------- MG-1 ----------

def test_mg1_sample_deterministic_and_covering():
    labels = {f"q{i:03d}": (["figure"] if i == 7 else []) + (["edge"] if i in (1, 80) else []) for i in range(1, 81)}
    s1 = eligible.mg1_sample(labels, "seed")
    assert s1 == eligible.mg1_sample(labels, "seed") and len(s1) == 20
    assert "q007" in s1 and ({"q001", "q080"} & set(s1))
    assert eligible.mg1_sample(labels, "other") != s1
    assert "dedupe" in eligible.mg1_not_applicable(labels)


def test_mg1_review_verdict():
    sample = ["a", "b"]
    ok = {"revs": REVS, "exam_date_source_quote": "…", "items": [{"id": "a", "result": "pass", "reviewer": "r"}, {"id": "b", "result": "pass", "reviewer": "r"}]}
    assert run._review_verdict(ok, sample)["result"] == "pass"
    bad = copy.deepcopy(ok)
    bad["items"][1]["result"] = "fail"
    assert run._review_verdict(bad, sample)["result"] == "fail"
    wrong = copy.deepcopy(ok)
    wrong["items"] = wrong["items"][:1]
    assert run._review_verdict(wrong, sample)["result"] == "stale", "樣本與演算法重算不符"
    noquote = copy.deepcopy(ok)
    noquote["exam_date_source_quote"] = ""
    assert run._review_verdict(noquote, sample)["result"] == "pending", "未核對考試日期來源"
    blank = {"revs": REVS, "exam_date_source_quote": "", "items": [{"id": i, "result": None, "reviewer": "", "note": ""} for i in sample]}
    assert run._review_verdict(blank, sample)["result"] == "pending", "review-init 剛產生之空範本 = 未審，非不符"
    noreviewer = copy.deepcopy(ok)
    noreviewer["items"][0]["reviewer"] = ""
    assert run._review_verdict(noreviewer, sample)["result"] == "pending"
    mixed = copy.deepcopy(blank)
    mixed["items"][0]["result"] = "fail"
    assert run._review_verdict(mixed, sample)["result"] == "fail", "已有不符時優先於未審完"


# ---------- AC-5：兩次乾淨 compile 位元組相同，且不改動 snapshot ----------

def _hash_tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.mark.slow
def test_ac5_deterministic(tmp_path):
    snap = lambda: {**_hash_tree(ROOT / "raw"), "manifest.json": hashlib.sha256((ROOT / "manifest.json").read_bytes()).hexdigest(),
                    **({f"inputs/{k}": v for k, v in _hash_tree(ROOT / "inputs").items()} if (ROOT / "inputs").exists() else {})}
    before = snap()
    a, b = tmp_path / "a", tmp_path / "b"
    run.compile_all(RELEASE_DATE, out=a, render=True)
    run.compile_all(RELEASE_DATE, out=b, render=True)
    ha, hb = _hash_tree(a), _hash_tree(b)
    assert ha == hb
    assert any(k.startswith("data/figures/") for k in ha)
    assert snap() == before
