"""自動 AC 之可證偽斷言（spec §6.1）。皆為純函式：輸入資料結構、回傳錯誤訊息清單；空清單 = 通過。

測試以反例 fixture 注入違規資料，斷言這些函式必定回報錯誤。
"""

import re

from .. import textnorm
from .apdf import AnswerDoc

KEYS = ("A", "B", "C", "D")
_ID_RE = re.compile(r"^(\d{3})-(\d)-PHARM-(P[1-6])-(\d{3})$")


# ---------- AC-0 ----------

def ac0_universe(universe: set, tuples: set, coverage: list[tuple]) -> list[str]:
    errs = []
    if not universe:
        errs.append("universe 為空")
    if universe - tuples:
        errs.append(f"manifest 缺 tuple：{sorted(universe - tuples)[:6]}")
    if tuples - universe:
        errs.append(f"manifest 有 universe 外之 tuple：{sorted(tuples - universe)[:6]}")
    if sorted(coverage) != sorted(universe) or len(coverage) != len(set(coverage)):
        errs.append("coverage 與 universe 不一一對應")
    return errs


# ---------- AC-1 ----------

def ac1_numbers(q_numbers: list[int], docs: dict[str, AnswerDoc]) -> list[str]:
    errs = []
    if not docs:
        return ["無答案 PDF"]
    for kind, d in docs.items():
        n = d.count
        if n <= 0:
            errs.append(f"{kind} 題數 {n} ≤ 0")
            continue
        expect = list(range(1, n + 1))
        if sorted(d.table) != expect:
            errs.append(f"{kind} 答案表題號 ≠ 1..{n}")
        if q_numbers != expect:
            errs.append(f"試題題號（{len(q_numbers)} 題）≠ {kind} 之 1..{n}")
    return errs


# ---------- AC-2 ----------

def ac2_options(rec: dict, option_marker_order: list[str], option_graphics: dict[str, int]) -> list[str]:
    errs = []
    if option_marker_order != list(KEYS):
        errs.append(f"{rec['id']} 選項標記順序 {option_marker_order}")
    if list(rec["options"]) != list(KEYS):
        errs.append(f"{rec['id']} 選項鍵 {list(rec['options'])}")
    for k in KEYS:
        text = rec["options"].get(k, "")
        exempt = k in rec["empty_option_keys"]
        if not text and not (exempt and option_graphics.get(k, 0) > 0):
            errs.append(f"{rec['id']} 選項 {k} 為空且其範圍內無圖形物件")
        if exempt and text:
            errs.append(f"{rec['id']} 選項 {k} 列為空選項豁免但有文字")
    return errs


# ---------- AC-3 ----------

def ac3_shape(rec: dict) -> list[str]:
    acc, pol, rid = rec["accepted_answers"], rec["score_policy"], rec["id"]
    errs = []
    for s in acc:
        if not s or any(x not in KEYS for x in s) or s != sorted(set(s)):
            errs.append(f"{rid} 答案集合不合法或未排序：{s}")
    if acc != sorted(acc, key=lambda s: (len(s), s)) or len({tuple(s) for s in acc}) != len(acc):
        errs.append(f"{rid} 集合順序或重複：{acc}")
    if pol == "normal" and not (len(acc) == 1 and len(acc[0]) == 1):
        errs.append(f"{rid} normal 必須恰一個 singleton：{acc}")
    if pol == "multi_answer" and len(acc) < 2:
        errs.append(f"{rid} multi_answer 至少兩個集合：{acc}")
    if pol == "all_credit" and acc != []:
        errs.append(f"{rid} all_credit 必須為 []：{acc}")
    if pol not in ("normal", "multi_answer", "all_credit"):
        errs.append(f"{rid} score_policy 未知：{pol}")
    return errs


# ---------- AC-4 ----------

def ac4_ids(recs: list[dict]) -> list[str]:
    errs = []
    seen: dict[str, tuple] = {}
    natural: set[tuple] = set()
    for r in recs:
        m = _ID_RE.match(r["id"])
        if not m:
            errs.append(f"id 格式錯誤：{r['id']}")
            continue
        parsed = (int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)))
        if parsed != (r["year_roc"], r["session"], r["subject"], r["question_no"]):
            errs.append(f"id {r['id']} 與欄位不一致")
        if int(r["exam_code"][:3]) != r["year_roc"]:
            errs.append(f"{r['id']} exam_code 與 year_roc 不一致")
        nat = (r["exam_code"], r["subject"], r["question_no"])
        if r["id"] in seen or nat in natural:
            errs.append(f"id 或 (exam_code, subject, question_no) 重複：{r['id']}")
        seen[r["id"]] = nat
        natural.add(nat)
    return errs


# ---------- AC-7 ----------

def ac7_text(rec: dict, l1: dict[str, tuple[str, list[bool]]]) -> list[str]:
    """l1：欄位（stem、A–D）→ (L1 文字, small 旗標)。L2 必須恰等於 T(L1)。"""
    errs = []
    fields = {"stem": rec["stem"], **rec["options"]}
    offsets = rec["script_char_offsets"]
    for name, l2 in fields.items():
        text, flags = l1[name]
        expect, offs = textnorm.apply_t(text, flags)
        if l2 != expect:
            errs.append(f"{rec['id']} {name}：L2 ≠ T(L1)")
        if offsets.get(name, []) != offs:
            errs.append(f"{rec['id']} {name}：script offset ≠ T 計算值")
        if textnorm.apply_t(l2)[0] != l2:
            errs.append(f"{rec['id']} {name}：T 非冪等")
        bad = textnorm.residue(l2)
        if bad:
            errs.append(f"{rec['id']} {name}：殘留 {bad[:3]}")
    if not rec["stem"]:
        errs.append(f"{rec['id']} stem 為空")
    return errs


def ac7_attribution(unattributed: list) -> list[str]:
    return [f"字元未歸屬或重複歸屬：{len(unattributed)} 個，例 {unattributed[:3]}"] if unattributed else []


# ---------- AC-9 ----------

def ac9_current(recs: list[dict], m: dict) -> list[str]:
    """canonical 之來源 rev 必須等於 manifest current（compile 只讀 current）。"""
    cur = {(t["exam_code"], t["subject"]): t["current"] for t in m["tuples"]}
    errs = []
    for r in recs:
        c = cur.get((r["exam_code"], r["subject"]))
        if c is None:
            errs.append(f"{r['id']} 無對應 tuple")
            continue
        s = r["source"]
        if (s["question_rev"], s["ans_rev"], s["mod_rev"]) != (c["Q"], c["ANS"], c["MOD"]):
            errs.append(f"{r['id']} 來源 rev ≠ current")
    return errs


# ---------- AC-11 ----------

def ac11_mod(ans: AnswerDoc | None, mod: AnswerDoc | None) -> list[str]:
    errs = []
    if ans is not None:
        if any(v == "＃" for v in ans.table.values()):
            errs.append("ANS 含 ＃")
        if ans.note_raw.strip():
            errs.append(f"ANS 備註非空：{ans.note_raw[:40]!r}")
    if mod is None:
        return errs
    sharp = sorted(n for n, v in mod.table.items() if v == "＃")
    if sharp != sorted(mod.corrections):
        errs.append(f"MOD ＃ 題號 {sharp} ≠ 備註題號 {sorted(mod.corrections)}")
    if any(n < 1 or n > mod.count for n in mod.corrections):
        errs.append("MOD 備註題號越界")
    if ans is not None:
        if ans.count != mod.count:
            errs.append(f"ANS 題數 {ans.count} ≠ MOD {mod.count}")
        diff = [n for n, v in mod.table.items() if v != "＃" and ans.table.get(n) != v]
        if diff:
            errs.append(f"非 ＃ 題 ANS ≠ MOD：{diff[:6]}")
    return errs


# ---------- AC-14 ----------

def expected_answer(no: int, ans: AnswerDoc | None, mod: AnswerDoc | None) -> tuple[list[list[str]], str]:
    src = mod if mod is not None else ans
    v = src.table[no]
    if v == "＃":
        c = mod.corrections[no]
        return c.accepted, c.policy
    return [[v]], "normal"


def ac14_values(rec: dict, ans: AnswerDoc | None, mod: AnswerDoc | None) -> list[str]:
    try:
        acc, pol = expected_answer(rec["question_no"], ans, mod)
    except (KeyError, AttributeError) as e:
        return [f"{rec['id']} 無法自來源表取得答案：{e}"]
    errs = []
    if rec["accepted_answers"] != acc or rec["score_policy"] != pol:
        errs.append(f"{rec['id']} 答案值 {rec['accepted_answers']}/{rec['score_policy']} ≠ 來源 {acc}/{pol}")
    return errs
