"""答案 PDF（ANS／MOD）解析：題數、答案表、備註句型（spec §4.4）。"""

import re
from dataclasses import dataclass, field

import pdfplumber

from .. import textnorm

_ROW_NO = re.compile(r"^題[號序]\s+(.*)$")
_ROW_ANS = re.compile(r"^答案\s+(.*)$")
_COUNT = re.compile(r"題\s*數：\s*(\d+)\s*題")
_NOTE = re.compile(r"^備\s*註：(.*)$")

# 句型（L1 經相容漢字與全形英數正規化後），窮舉
_CLAUSES = [
    (re.compile(r"第(\d+)題答([A-D])或([A-D])或([A-D]{2})者均給分"), "xy_or_both"),
    (re.compile(r"第(\d+)題答([A-D])或([A-D])者均給分"), "x_or_y"),
    (re.compile(r"第(\d+)題一律給分"), "all_credit"),
]
_SEPARATORS = ("，", "、", "；")


class AnswerParseError(ValueError):
    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason


@dataclass
class Correction:
    no: int
    policy: str                         # multi_answer | all_credit
    accepted: list[list[str]]
    clause: str                         # 備註子句逐字（L1，未正規化）


@dataclass
class AnswerDoc:
    count: int
    table: dict[int, str]               # 題號 → A–D 或 ＃
    note_raw: str                       # 備註全文（L1）
    corrections: dict[int, Correction] = field(default_factory=dict)


def _norm(s: str) -> str:
    return "".join(textnorm.map_char(c) for c in s)


def parse_notes(note_raw: str) -> dict[int, Correction]:
    """備註必須被句型完全消耗；任何殘餘 → note_unparsed。"""
    text = re.sub(r"\s+", "", note_raw)
    norm = _norm(text)
    if len(norm) != len(text):
        raise AssertionError("逐字映射長度改變")
    out: dict[int, Correction] = {}
    i = 0
    while i < len(norm):
        for pat, kind in _CLAUSES:
            m = pat.match(norm, i)
            if not m:
                continue
            no = int(m.group(1))
            if kind == "xy_or_both":
                x, y, xy = m.group(2), m.group(3), m.group(4)
                if xy != x + y or x >= y:
                    raise AnswerParseError("note_unparsed", f"句型「答{x}或{y}或{xy}」不一致")
                corr = Correction(no, "multi_answer", [[x], [y], [x, y]], text[m.start():m.end()])
            elif kind == "x_or_y":
                x, y = m.group(2), m.group(3)
                if x >= y:
                    raise AnswerParseError("note_unparsed", f"句型「答{x}或{y}」順序非預期")
                corr = Correction(no, "multi_answer", [[x], [y]], text[m.start():m.end()])
            else:
                corr = Correction(no, "all_credit", [], text[m.start():m.end()])
            if no in out:
                raise AnswerParseError("note_unparsed", f"第{no}題於備註出現兩次")
            out[no] = corr
            i = m.end()
            if i < len(norm) and norm[i] in _SEPARATORS:
                i += 1
            break
        else:
            raise AnswerParseError("note_unparsed", f"備註無法解析之殘餘：{text[i:i + 30]!r}")
    return out


def parse(path) -> AnswerDoc:
    with pdfplumber.open(path) as pdf:
        lines = [textnorm.compat(ln).strip() for p in pdf.pages for ln in (p.dedupe_chars().extract_text() or "").splitlines()]
    counts = [int(m.group(1)) for ln in lines if (m := _COUNT.search(ln))]
    if len(counts) != 1 or counts[0] <= 0:
        raise AnswerParseError("parse_fail", f"題數欄位異常：{counts}")
    nos: list[str] = []
    ans: list[str] = []
    note_idx = None
    for i, ln in enumerate(lines):
        if (m := _ROW_NO.match(ln)):
            nos += m.group(1).split()
        elif (m := _ROW_ANS.match(ln)):
            ans += m.group(1).split()
        elif _NOTE.match(ln):
            note_idx = i
            break
    if note_idx is None:
        raise AnswerParseError("parse_fail", "找不到「備註」欄")
    note_raw = "".join([_NOTE.match(lines[note_idx]).group(1)] + lines[note_idx + 1:])
    if len(nos) != len(ans):
        raise AnswerParseError("parse_fail", f"題號 {len(nos)} 格、答案 {len(ans)} 格不等")
    table: dict[int, str] = {}
    for n, a in zip(nos, ans):
        if not n.isdigit():
            raise AnswerParseError("parse_fail", f"題號格非數字：{n!r}")
        a = _norm(a)
        if a not in ("A", "B", "C", "D", "＃"):
            raise AnswerParseError("parse_fail", f"第{int(n)}題答案格非預期：{a!r}")
        if int(n) in table:
            raise AnswerParseError("parse_fail", f"題號 {int(n)} 重複")
        table[int(n)] = a
    doc = AnswerDoc(counts[0], table, note_raw)
    doc.corrections = parse_notes(note_raw) if note_raw.strip() else {}
    return doc
