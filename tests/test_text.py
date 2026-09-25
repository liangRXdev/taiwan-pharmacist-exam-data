"""AC-7、AC-13、AC-15、AC-16：文字忠實度。"""

import copy
import json
from functools import lru_cache

import pytest

from tped import manifest, textnorm
from tped.build import crosscheck, pdftext, qparse, validate


@lru_cache(maxsize=None)
def _q_path(code: str, subject: str):
    m = manifest.load()
    t = manifest.tuple_of(m, code, subject)
    return manifest.ROOT / manifest.revision(t, t["current"]["Q"])["raw_path"]


@lru_cache(maxsize=None)
def _parsed(code: str, subject: str):
    doc = pdftext.load(_q_path(code, subject))
    return doc, qparse.parse(doc)


def _l1(q: qparse.ParsedQuestion) -> dict:
    return {"stem": (q.stem_l1.text, q.stem_l1.small), **{k: (s.text, s.small) for k, s in q.options_l1.items()}}


# ---------- AC-7 ----------

def test_ac7_real(compiled):
    for (code, p), res in compiled["results"].items():
        if (code, p) == ("113020", "P1"):
            continue
        assert not res.errors, (code, p, res.errors[:3])


def test_ac7_counterexamples(by_id):
    doc, parsed = _parsed("114020", "P2")
    q = parsed.questions[4]
    rec = copy.deepcopy(by_id["114-1-PHARM-P2-005"])
    assert validate.ac7_text(rec, _l1(q)) == []
    trunc = copy.deepcopy(rec)
    trunc["stem"] = rec["stem"][:-5]
    assert validate.ac7_text(trunc, _l1(q)), "L2 被截斷"
    changed = copy.deepcopy(rec)
    changed["options"]["A"] = changed["options"]["A"] + "毫克"
    assert validate.ac7_text(changed, _l1(q)), "T 以外改字"
    empty = copy.deepcopy(rec)
    empty["stem"] = ""
    assert validate.ac7_text(empty, {**_l1(q), "stem": ("", [])}), "stem 為空"


def test_ac7_truncated_l1_and_l2(monkeypatch):
    """L1 與 L2 同時截斷（L0 不變）→ 字元歸屬必定失敗。"""
    doc = pdftext.load(_q_path("114020", "P2"))
    orig = qparse._split

    def lossy(d):
        qs, h, ins = orig(d)
        qs[4].stem = qs[4].stem[:-1]
        return qs, h, ins

    monkeypatch.setattr(qparse, "_split", lossy)
    parsed = qparse.parse(doc)
    assert validate.ac7_attribution(parsed.unattributed)


def test_ac7_t_properties():
    s = "Ｎａ＋　與  K+ 之 比\x81較 列"   # 全形英數、全形空白、雙空白、CJK 間空白、控制字元、相容漢字
    l2, _ = textnorm.apply_t(s)
    assert textnorm.apply_t(l2)[0] == l2
    assert textnorm.residue(l2) == []
    assert "\x81" not in l2 and "列" in l2 and "Na" in l2
    assert "C-14" == textnorm.apply_t("C-14")[0]


def test_space_rule_real(records):
    """Word 版 PDF 之假空白：`A.g uanylyl` 實為 `A.guanylyl`；斜體學名空白必須保留。"""
    txt = json.dumps(records, ensure_ascii=False)
    assert "a spirin" not in txt and "aspirin" in txt
    assert "g uanylyl" not in txt and "guanylyl cyclase" in txt
    assert "Streptococcus pneumoniae" in txt
    assert "M. tuberculosis" in txt


# ---------- AC-13 ----------

def test_ac13_overprint():
    doc, parsed = _parsed("113020", "P1")
    q54 = parsed.questions[53]
    stem = textnorm.apply_t(q54.stem_l1.text)[0]
    assert "C-14" in stem and "C-1144" not in stem
    assert sum(r["count"] for r in parsed.removed) == 696    # 首頁表頭 480 + 題幹 216


def test_ac13_legit_repeats_kept(records):
    """同座標才去重：不同座標之合法相鄰重複字元不得被移除（以字串層級去重必定破壞這些字）。"""
    txt = json.dumps(records, ensure_ascii=False)
    for word in ("allosteric", "cellulose", "Staphylococcus"):
        if word in txt:
            break
    else:
        pytest.fail("找不到含合法重複字母之詞")
    import re
    assert re.sub(r"(.)\1", r"\1", word) != word


# ---------- AC-15 ----------

def test_ac15_regression_floors(compiled):
    labels = {rid: labs for res in compiled["results"].values() for rid, labs in res.labels.items()}
    figs = {rid for rid, labs in labels.items() if "figure" in labs}
    # 純向量圖題（無 image 物件）。114-2 P3 第 8 題於 M0 之 oracle 版本為帶框線之配方表，
    # 站方替換後之現行版本已無框線，故不列入（下限以 current revision 為準）。
    assert "113-2-PHARM-P3-066" in figs, "純向量圖題"
    assert len(figs) >= 100
    compat_files = {rid.rsplit("-", 1)[0] for rid, labs in labels.items() if "compat" in labs}
    assert len(compat_files) >= 12
    script_115 = {rid.rsplit("-", 1)[0] for rid, labs in labels.items() if "script" in labs and rid.startswith("115-1")}
    assert script_115 == {f"115-1-PHARM-P{i}" for i in range(1, 7)}


def test_ac15_detectors_not_empty(compiled):
    present = {lab for res in compiled["results"].values() for labs in res.labels.values() for lab in labs}
    assert {"figure", "compat", "script", "table", "crosspage", "corrected", "edge"} <= present
    # 題幹疊印僅見於 113020 P1（已因 text_layer_loss parked），直接對其執行偵測器
    from tped.build import assemble
    doc, parsed = _parsed("113020", "P1")
    dedupe = [q.no for q in parsed.questions if "dedupe" in assemble._labels(q, doc, parsed, set(), len(parsed.questions))]
    assert 54 in dedupe and len(dedupe) >= 5


# ---------- AC-16 ----------

def test_ac16_detects_dropped_glyphs():
    doc, _ = _parsed("113020", "P1")
    l1 = {p.index: [c.text for c in p.l1_chars] for p in doc.pages}
    errs = crosscheck.page_mismatches(_q_path("113020", "P1"), l1)
    assert errs and "U+F00D" in errs[0]


def test_ac16_clean_and_injected():
    doc, _ = _parsed("114020", "P4")
    l1 = {p.index: [c.text for c in p.l1_chars] for p in doc.pages}
    assert crosscheck.page_mismatches(_q_path("114020", "P4"), l1) == []
    drop = next(ch for ch in l1[2] if "一" <= ch <= "鿿")
    injected = dict(l1)
    injected[2] = [c for c in l1[2] if c != drop]
    assert crosscheck.page_mismatches(_q_path("114020", "P4"), injected), "某字元自 L1 完全消失"


def test_parked_tuple_not_in_canonical(compiled, records):
    cov = {(c["exam_code"], c["subject"]): c for c in compiled["coverage"]}
    assert cov[("113020", "P1")]["status"] == "parked"
    assert cov[("113020", "P1")]["reasons"] == ["text_layer_loss"]
    assert not any(r["exam_code"] == "113020" and r["subject"] == "P1" for r in records)
