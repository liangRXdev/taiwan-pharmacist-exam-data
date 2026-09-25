"""試題 PDF → 題目（spec §4.5、§4.7、§5.5）。

切分規則（決定性）：
  - 題號：行首 `{n}.`（n 必須等於下一個預期題號、`.` 後不得緊接數字）
  - 選項：行首 `{K}.`，K 必須等於下一個預期選項；同行內以「空白 + K.」切出後續選項
  - 首題之前的行：`※` 開頭 → instruction，其餘 → header
  - 行接合：前一行右端 ≥ 版心右界 − 2 × 本文字級 → 軟換行（接合），否則硬換行（保留 \\n）
"""

import re
from dataclasses import dataclass, field

from .. import textnorm
from .pdftext import Ch, DocText, Graphic, Line

OPTION_KEYS = ("A", "B", "C", "D")
_QNO_RE = re.compile(r"^(\d{1,3})[.．]")
LEFT_MARGIN_TOL = 2.0   # 題號行位於最左邊界；題幹續行與選項為懸掛縮排（實測縮排 ≥ 10pt）


class ParseError(ValueError):
    pass


@dataclass
class Frag:
    """一段屬於某欄位之行片段。"""
    line: Line
    start: int      # line.text 內起始位置（不含標記）
    end: int


@dataclass
class Rect:
    page: int
    top: float
    bottom: float
    x0: float
    x1: float

    def hits(self, g: Graphic) -> bool:
        return g.page == self.page and g.top < self.bottom and g.bottom > self.top and g.x0 < self.x1 and g.x1 > self.x0


@dataclass
class Marker:
    key: str
    line: Line
    pos: int        # line.text 內位置

    @property
    def x0(self) -> float:
        ch = self.line.text_chars[self.pos]
        return ch.x0 if ch else self.line.x0


@dataclass
class QDraft:
    no: int
    start_line: Line
    stem: list[Frag] = field(default_factory=list)
    options: dict[str, list[Frag]] = field(default_factory=dict)
    markers: list[Marker] = field(default_factory=list)
    marker_spans: list[tuple[Line, int, int]] = field(default_factory=list)
    region: list[Rect] = field(default_factory=list)
    option_regions: dict[str, list[Rect]] = field(default_factory=dict)


@dataclass
class Segment:
    """L1 文字 + 逐字 small 旗標。"""
    text: str
    small: list[bool]


@dataclass
class ParsedQuestion:
    no: int
    stem_l1: Segment
    options_l1: dict[str, Segment]
    region: list[Rect]
    option_regions: dict[str, list[Rect]]
    graphics: list[Graphic]
    option_graphics: dict[str, list[Graphic]]


@dataclass
class ParsedDoc:
    questions: list[ParsedQuestion]
    attribution: dict[tuple, str]     # Ch.key → 歸屬
    unattributed: list[tuple]
    removed: list[dict]


def _option_markers_in_line(line: Line, expect: str, from_pos: int) -> list[tuple[str, int]]:
    """行首（from_pos）必須為 expect；之後以「空白 + 下一個 K.」切分。"""
    text = line.text
    if not (text[from_pos:from_pos + 1] == expect and text[from_pos + 1:from_pos + 2] in (".", "．")):
        return []
    found = [(expect, from_pos)]
    nxt = OPTION_KEYS.index(expect) + 1
    i = from_pos + 2
    while nxt < len(OPTION_KEYS):
        k = OPTION_KEYS[nxt]
        m = re.compile(r"(?<= )" + k + r"[.．]").search(text, i)
        if not m:
            break
        found.append((k, m.start()))
        nxt += 1
        i = m.end()
    return found


def _split(doc: DocText) -> tuple[list[QDraft], list[Line], list[Line]]:
    questions: list[QDraft] = []
    header: list[Line] = []
    instruction: list[Line] = []
    cur: QDraft | None = None
    target: list[Frag] | None = None
    left = min(ln.x0 for ln in doc.lines)
    for line in doc.lines:
        text = line.text
        m = _QNO_RE.match(text)
        if m and int(m.group(1)) == len(questions) + 1 and line.x0 <= left + LEFT_MARGIN_TOL:
            cur = QDraft(int(m.group(1)), line)
            questions.append(cur)
            cur.marker_spans.append((line, 0, m.end()))
            target = cur.stem
            rest = m.end()
            if rest < len(text):
                target.append(Frag(line, rest, len(text)))
            continue
        if cur is None:
            (instruction if text.startswith("※") else header).append(line)
            continue
        expect = OPTION_KEYS[len(cur.options)] if len(cur.options) < len(OPTION_KEYS) else None
        found = _option_markers_in_line(line, expect, 0) if expect else []
        if found:
            for i, (k, pos) in enumerate(found):
                end = found[i + 1][1] if i + 1 < len(found) else len(text)
                cur.options[k] = []
                cur.markers.append(Marker(k, line, pos))
                cur.marker_spans.append((line, pos, pos + 2))
                if pos + 2 < end:
                    cur.options[k].append(Frag(line, pos + 2, end))
            target = cur.options[found[-1][0]]
            continue
        target.append(Frag(line, 0, len(text)))
    return questions, header, instruction


def _right_margin(doc: DocText) -> float:
    return max(ln.x1 for ln in doc.lines)


def _join(frags: list[Frag], soft_edge: float) -> Segment:
    out: list[str] = []
    small: list[bool] = []
    prev: Frag | None = None
    for f in frags:
        piece = f.line.text[f.start:f.end]
        chars = f.line.text_chars[f.start:f.end]
        # 去除片段首尾空白
        lo, hi = 0, len(piece)
        while lo < hi and piece[lo] == " ":
            lo += 1
        while hi > lo and piece[hi - 1] == " ":
            hi -= 1
        piece, chars = piece[lo:hi], chars[lo:hi]
        if not piece:
            continue
        if prev is not None and out:
            if prev.line.x1 >= soft_edge:
                a, b = out[-1], piece[0]
                if a.isascii() and a != "-" and textnorm.is_ascii_alnum(b):
                    out.append(" ")
                    small.append(False)
            else:
                out.append("\n")
                small.append(False)
        out.extend(piece)
        small.extend(bool(c and c.small) for c in chars)
        prev = f
    return Segment("".join(out), small)


def _regions(qs: list[QDraft], doc: DocText) -> None:
    page_h = {p.index: p.height for p in doc.pages}
    page_w = {p.index: p.width for p in doc.pages}
    last_page = doc.pages[-1].index
    for i, q in enumerate(qs):
        start = (q.start_line.page, q.start_line.top)
        end = (qs[i + 1].start_line.page, qs[i + 1].start_line.top) if i + 1 < len(qs) else (last_page, page_h[last_page])
        q.region = _span(start, end, page_h, page_w)
        for j, mk in enumerate(q.markers):
            if j + 1 < len(q.markers) and q.markers[j + 1].line is mk.line:
                row_end = _next_row_top(q, mk, end)
                q.option_regions[mk.key] = [Rect(mk.line.page, mk.line.top, row_end, mk.x0, q.markers[j + 1].x0)]
            elif j > 0 and q.markers[j - 1].line is mk.line:
                row_end = _next_row_top(q, mk, end)
                q.option_regions[mk.key] = [Rect(mk.line.page, mk.line.top, row_end, mk.x0, page_w[mk.line.page])]
            else:
                nxt = q.markers[j + 1] if j + 1 < len(q.markers) else None
                stop = (nxt.line.page, nxt.line.top) if nxt else end
                q.option_regions[mk.key] = _span((mk.line.page, mk.line.top), stop, page_h, page_w)


def _next_row_top(q: QDraft, mk: Marker, end: tuple[int, float]) -> float:
    later = [m.line.top for m in q.markers if m.line.page == mk.line.page and m.line.top > mk.line.top + 1]
    if later:
        return min(later)
    return end[1] if end[0] == mk.line.page else float("inf")


def _span(start: tuple[int, float], end: tuple[int, float], page_h: dict, page_w: dict) -> list[Rect]:
    out = []
    for p in range(start[0], end[0] + 1):
        top = start[1] if p == start[0] else 0.0
        bottom = end[1] if p == end[0] else page_h[p]
        if bottom > top:
            out.append(Rect(p, top, bottom, 0.0, page_w[p]))
    return out


def parse(doc: DocText) -> ParsedDoc:
    drafts, header, instruction = _split(doc)
    if not drafts:
        raise ParseError("找不到第 1 題")
    _regions(drafts, doc)
    soft = _right_margin(doc) - 2 * doc.body_size
    graphics = [g for p in doc.pages for g in p.graphics]
    attribution: dict[tuple, str] = {}
    duplicate: list[tuple] = []

    def assign(ch: Ch | None, label: str) -> None:
        if ch is None or not ch.text.strip():
            return
        if ch.key in attribution:
            duplicate.append(ch.key)
        attribution[ch.key] = label

    for ln in header:
        for c in ln.chars:
            assign(c, "header")
    for ln in instruction:
        for c in ln.chars:
            assign(c, "instruction")
    out: list[ParsedQuestion] = []
    for q in drafts:
        for ln, a, b in q.marker_spans:
            for c in ln.text_chars[a:b]:
                assign(c, f"q:{q.no}:marker")
        for f in q.stem:
            for c in f.line.text_chars[f.start:f.end]:
                assign(c, f"q:{q.no}:stem")
        for k, frags in q.options.items():
            for f in frags:
                for c in f.line.text_chars[f.start:f.end]:
                    assign(c, f"q:{q.no}:opt:{k}")
        q_graphics = [g for g in graphics if any(r.hits(g) for r in q.region)]
        opt_graphics = {k: [g for g in q_graphics if any(r.hits(g) for r in q.option_regions.get(k, []))] for k in q.options}
        out.append(ParsedQuestion(
            q.no, _join(q.stem, soft), {k: _join(v, soft) for k, v in q.options.items()},
            q.region, q.option_regions, q_graphics, opt_graphics,
        ))
    all_keys = {c.key for p in doc.pages for c in p.l1_chars}
    unattributed = sorted(all_keys - set(attribution)) + sorted(set(duplicate))
    return ParsedDoc(out, attribution, unattributed, doc.removed)
