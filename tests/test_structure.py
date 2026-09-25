"""AC-0 ~ AC-4、AC-9、AC-11、AC-12、AC-14：真實資料通過 + 反例必定失敗。"""

import copy

import pytest

from tped import manifest
from tped.build import apdf, derive, validate
from tped.build.apdf import AnswerDoc, Correction
from conftest import RELEASE_DATE


# ---------- AC-0 ----------

def test_ac0_real(compiled, m):
    assert compiled["ac0"] == []
    u = derive.universe_keys(derive.universe(m, RELEASE_DATE))
    assert len(u) == 36


def _u(m):
    return derive.universe_keys(derive.universe(m, RELEASE_DATE))


def test_ac0_counterexamples(m):
    u = _u(m)
    cov = sorted(u)
    assert validate.ac0_universe(u, u - {("114020", "P3")}, cov), "刪除一科"
    assert validate.ac0_universe(u, {k for k in u if k[0] != "114090"}, cov), "刪除整場六科"
    latest = max(k[0] for k in u)
    assert validate.ac0_universe(u, {k for k in u if k[0] != latest}, cov), "漏掉最新一場"
    assert validate.ac0_universe(u, u, cov + [cov[0]]), "coverage 重複一科"
    assert validate.ac0_universe(set(), set(), []), "空 universe"


def test_ac0_year_page_missing(m_copy):
    del m_copy["discovery"]["year_list_revs"]["2025"]
    with pytest.raises(derive.DeriveError):
        derive.universe(m_copy, RELEASE_DATE)


# ---------- AC-1 ----------

def _doc(n, table=None, corrections=None, note=""):
    return AnswerDoc(n, table if table is not None else {i: "A" for i in range(1, n + 1)}, note, corrections or {})


def test_ac1_counterexamples():
    assert validate.ac1_numbers([], {"ANS": _doc(0, {})}), "題數 0"
    assert validate.ac1_numbers(list(range(1, 80)), {"ANS": _doc(80)}), "漏第 80 題"
    assert validate.ac1_numbers(list(range(1, 81)) + [80], {"ANS": _doc(80)}), "重複第 80 題"
    t = {i: "A" for i in range(1, 81)}
    del t[7]
    assert validate.ac1_numbers(list(range(1, 81)), {"ANS": _doc(80, t)}), "答案表漏題"
    assert validate.ac1_numbers(list(range(1, 81)), {"ANS": _doc(80)}) == []


# ---------- AC-2 ----------

def test_ac2_counterexamples(by_id):
    rec = copy.deepcopy(by_id["114-1-PHARM-P1-001"])
    assert validate.ac2_options(rec, list("ABCD"), {}) == []
    assert validate.ac2_options(rec, list("ABDC"), {}), "選項順序錯"
    rec["options"]["C"] = ""
    rec["empty_option_keys"] = ["C"]
    assert validate.ac2_options(rec, list("ABCD"), {"B": 1}), "空選項但圖在他選項"
    assert validate.ac2_options(rec, list("ABCD"), {"C": 1}) == []


def test_ac2_real_figure_options(by_id):
    """圖片選項題：空選項必須逐選項有圖形證據（M0 實測 115020 P1 有 11 題）。"""
    exempt = [r for r in by_id.values() if r["empty_option_keys"]]
    assert len(exempt) >= 40
    assert all(r["has_figure"] for r in exempt)


# ---------- AC-3 ----------

@pytest.mark.parametrize("acc,pol", [
    ([[]], "multi_answer"), ([["A"], ["B"]], "normal"), ([["B", "A"]], "normal"),
    ([["B"], ["A"]], "multi_answer"), ([["A"], ["A"]], "multi_answer"), ([["A"]], "all_credit"),
    ([["E"]], "normal"), ([["A"]], "multi_answer"),
])
def test_ac3_counterexamples(acc, pol):
    assert validate.ac3_shape({"id": "x", "accepted_answers": acc, "score_policy": pol})


def test_ac3_real(records):
    assert [e for r in records for e in validate.ac3_shape(r)] == []
    assert any(r["score_policy"] == "all_credit" for r in records)
    assert any(r["accepted_answers"] == [["A"], ["B"]] for r in records), "113-2 P5 第 24 題：答A或B（不含AB）"


# ---------- AC-4 ----------

def test_ac4(records):
    assert validate.ac4_ids(records) == []
    bad = copy.deepcopy(records[:2])
    bad[0]["question_no"] += 1
    assert validate.ac4_ids(bad), "ID 與 question_no 不一致"
    dup = copy.deepcopy([records[0], records[0]])
    assert validate.ac4_ids(dup), "同 ID 兩題"


# ---------- AC-9 ----------

def test_ac9_real(m, records):
    assert manifest.invariant_errors(m) == []
    assert validate.ac9_current(records, m) == []


def test_ac9_counterexamples(m, records):
    mc = copy.deepcopy(m)
    t = mc["tuples"][0]
    t["current"]["ANS"], t["current"]["Q"] = t["current"]["Q"], t["current"]["ANS"] or t["current"]["MOD"]
    assert manifest.invariant_errors(mc, check_files=False), "current 指向他 kind"
    mc = copy.deepcopy(m)
    mc["tuples"][0]["current"]["Q"] = "sha256:" + "0" * 64
    assert manifest.invariant_errors(mc, check_files=False), "current 指向不存在之 rev"
    mc = copy.deepcopy(m)
    mc["tuples"][1]["revisions"].append(copy.deepcopy(mc["tuples"][0]["revisions"][0]))
    assert manifest.invariant_errors(mc, check_files=False), "rev 重複"
    mc = copy.deepcopy(m)
    rec = next(r for r in records if (r["exam_code"], r["subject"]) == (mc["tuples"][5]["exam_code"], mc["tuples"][5]["subject"]))
    mc["tuples"][5]["current"]["Q"] = "sha256:new"
    assert validate.ac9_current([rec], mc), "新增 current 後 canonical 仍指舊 rev"


# ---------- AC-11 ----------

def test_ac11_counterexamples():
    mod = _doc(3, {1: "A", 2: "＃", 3: "C"}, {2: Correction(2, "all_credit", [], "第2題一律給分")}, "第2題一律給分")
    assert validate.ac11_mod(None, mod) == []
    assert validate.ac11_mod(None, _doc(3, {1: "A", 2: "＃", 3: "C"}, {}, "")), "MOD-only 備註缺一句"
    extra = copy.deepcopy(mod)
    extra.corrections[3] = Correction(3, "all_credit", [], "第3題一律給分")
    assert validate.ac11_mod(None, extra), "備註多一題"
    ans = _doc(3, {1: "A", 2: "B", 3: "D"})
    assert validate.ac11_mod(ans, mod), "ANS/MOD 非＃題不同"
    assert validate.ac11_mod(_doc(3, {1: "A", 2: "B", 3: "C"}), mod) == []


def test_ac11_note_grammar():
    assert apdf.parse_notes("第67題答Ｂ或Ｃ或BC者均給分")[67].accepted == [["B"], ["C"], ["B", "C"]]
    assert apdf.parse_notes("第24題答A或B者均給分，第27題答A或B或AB者均給分")[24].accepted == [["A"], ["B"]]
    for bad in ["第5題答A或B或C者均給分", "第5題送分", "第5題一律給分。其他說明", "第5題答A或B或BA者均給分"]:
        with pytest.raises(apdf.AnswerParseError):
            apdf.parse_notes(bad)


# ---------- AC-12 ----------

def test_ac12_counterexamples(m):
    blocks = derive.universe(m, RELEASE_DATE)
    t = manifest.tuple_of(m, "114020", "P2")
    hs = derive.headers(m, t)
    assert derive.identity_errors(t, hs, blocks["114020"]) == []
    wrong = copy.deepcopy(t)
    wrong["exam_code"] = "114090"
    assert derive.identity_errors(wrong, hs, blocks["114090"]), "Q 屬 114020 但 tuple 記為 114090"
    swapped = {"Q": hs["Q"], "ANS": hs["MOD"], "MOD": hs["ANS"]}
    assert derive.identity_errors(t, swapped, blocks["114020"]), "ANS/MOD 互換"
    other = derive.headers(m, manifest.tuple_of(m, "114020", "P3"))
    assert derive.identity_errors(t, {"Q": other["Q"], "ANS": hs["ANS"]}, blocks["114020"]), "Q 指向他科"


def test_ac12_distinct_q(m):
    qs = [t["current"]["Q"] for t in m["tuples"]]
    assert len(qs) == len(set(qs))


# ---------- AC-14 ----------

def test_ac14(m, by_id):
    t = manifest.tuple_of(m, "114020", "P3")
    ans = apdf.parse(manifest.ROOT / manifest.revision(t, t["current"]["ANS"])["raw_path"]) if t["current"]["ANS"] else None
    mod = apdf.parse(manifest.ROOT / manifest.revision(t, t["current"]["MOD"])["raw_path"])
    rec = copy.deepcopy(by_id["114-1-PHARM-P3-010"])
    assert validate.ac14_values(rec, ans, mod) == []
    rec["accepted_answers"] = [["A"]] if rec["accepted_answers"] != [["A"]] else [["B"]]
    assert validate.ac14_values(rec, ans, mod), "改一題答案值但形狀合法"
    assert by_id["114-1-PHARM-P3-073"]["score_policy"] == "all_credit", "站方 2025-04-02 追加之更正"
    wrong = copy.deepcopy(by_id["114-1-PHARM-P3-002"])
    wrong["accepted_answers"], wrong["score_policy"] = [], "all_credit"
    assert validate.ac14_values(wrong, ans, mod), "＃題展開成他題之備註"
