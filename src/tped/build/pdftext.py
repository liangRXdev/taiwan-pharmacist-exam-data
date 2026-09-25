"""L0 / L1 字元與自組行（spec §4.7）。

不使用 pdfplumber.extract_text_lines 的行切分：115 年起下標以小字型、略低之 baseline 排版，
extract_text_lines 會把它切成獨立一行並排到本行之後，造成「β₂ receptor」變成「β receptor … 2」。
本模組以本文字型定義行，小字型字元併入與其垂直重疊最多之本文行，再依 x 排序。
"""

import collections
from dataclasses import dataclass, field

import pdfplumber

GAP_SPACE = 2.0          # 無空白 glyph 時，視覺字距 ≥ 2pt 推定為詞間空白
SPURIOUS_OVERLAP = -1.0  # 空白 glyph 起點深入前一字元 > 1pt …
SPURIOUS_VISIBLE = 1.0   # … 且前後可見字元視覺間距 < 1pt → 假空白（Word 清單標記後之殘留）


def _is_word_space(a: "Ch", b: "Ch", spaces: list["Ch"]) -> bool:
    """詞間空白判定（2026-09 實測，見 spec §4.5）：
    - Word 2013/2021 產出之 PDF 在清單標記後第一字元處放一個與前字重疊之空白 glyph，
      渲染上無空隙（`A.g uanylyl` 實為 `A.guanylyl`）→ 丟棄。
    - 斜體學名之空白 glyph 視覺間距 ≈ 0 但未重疊（`Streptococcus pneumoniae`）→ 保留。
    - Skia 產出之 PDF 常省略空白 glyph，以視覺字距推定。
    """
    vis = b.x0 - a.x1
    if spaces:
        spurious = all(s.x0 - a.x1 < SPURIOUS_OVERLAP for s in spaces) and vis < SPURIOUS_VISIBLE
        return not spurious
    return vis >= GAP_SPACE
LINE_TOL = 2.0           # 本文字元 top 差 ≤ 2pt 視為同一行
SMALL_RATIO = 0.8        # 字型 < 本文 0.8 倍 → script（spec §4.5）
GRAPHIC_MAX_HEIGHT_RATIO = 0.5


@dataclass(frozen=True)
class Ch:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    page: int
    small: bool

    @property
    def key(self) -> tuple:
        return (self.page, round(self.x0, 2), round(self.top, 2), self.text)


@dataclass
class Line:
    page: int
    chars: list[Ch]
    top: float = 0.0
    bottom: float = 0.0
    x0: float = 0.0
    x1: float = 0.0
    text: str = ""
    text_chars: list[Ch | None] = field(default_factory=list)   # 與 text 逐位對應；None = 推定之詞間空白

    def finalize(self) -> "Line":
        self.chars.sort(key=lambda c: (c.x0, c.top))
        normal = [c for c in self.chars if not c.small] or self.chars
        self.top = min(c.top for c in normal)
        self.bottom = max(c.bottom for c in normal)
        self.x0 = min(c.x0 for c in self.chars)
        self.x1 = max(c.x1 for c in self.chars)
        text: list[str] = []
        tc: list[Ch | None] = []
        visible = [c for c in self.chars if c.text.strip()]
        glyph_spaces = [c for c in self.chars if not c.text.strip()]
        for i, c in enumerate(visible):
            if i > 0:
                a = visible[i - 1]
                between = [s for s in glyph_spaces if a.x0 - 0.5 <= s.x0 < c.x0]
                if _is_word_space(a, c, between):
                    text.append(" ")
                    tc.append(between[0] if between else None)
            text.append(c.text)
            tc.append(c)
        self.text = "".join(text)
        self.text_chars = tc
        return self


@dataclass
class Graphic:
    kind: str
    page: int
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass
class PageData:
    index: int
    width: float
    height: float
    lines: list[Line]
    l1_chars: list[Ch]
    removed: list[dict]          # L0 → L1 被移除字元
    graphics: list[Graphic]


@dataclass
class DocText:
    pages: list[PageData]
    body_size: float

    @property
    def lines(self) -> list[Line]:
        return [ln for p in self.pages for ln in p.lines]

    @property
    def removed(self) -> list[dict]:
        return [r for p in self.pages for r in p.removed]


def _body_size(pdf: pdfplumber.PDF) -> float:
    sizes = collections.Counter(round(c["size"] * 2) / 2 for p in pdf.pages for c in p.dedupe_chars().chars if c["text"].strip())
    if not sizes:
        raise ValueError("PDF 無文字層字元")
    return sizes.most_common(1)[0][0]


def _removed(page, dedup) -> list[dict]:
    k = lambda c: (c["text"], round(c["x0"], 2), round(c["top"], 2))
    diff = collections.Counter(k(c) for c in page.chars) - collections.Counter(k(c) for c in dedup.chars)
    return [{"page": page.page_number - 1, "text": t, "x0": x, "top": y, "count": n} for (t, x, y), n in sorted(diff.items(), key=lambda kv: (kv[0][2], kv[0][1], kv[0][0]))]


def _build_lines(chars: list[Ch]) -> list[Line]:
    """PDF 內之空白字元保留（Word 產出之 PDF 含真實空白 glyph）；另於字距 > GAP_SPACE 處推定空白。"""
    normal = sorted((c for c in chars if not c.small), key=lambda c: (c.top, c.x0))
    lines: list[Line] = []
    span: list[tuple[float, float]] = []
    for c in normal:
        if lines:
            lo, hi = span[-1]
            if min(c.bottom, hi) - max(c.top, lo) > 0.5 * max(c.bottom - c.top, 0.1):
                lines[-1].chars.append(c)
                span[-1] = (min(lo, c.top), max(hi, c.bottom))
                continue
        if c.text.strip():
            lines.append(Line(c.page, [c]))
            span.append((c.top, c.bottom))
    for ln in lines:
        ln.finalize()
    orphans: list[Ch] = []
    for c in (c for c in chars if c.small):
        best, best_ov = None, 0.0
        for ln in lines:
            ov = min(c.bottom, ln.bottom) - max(c.top, ln.top)
            if ov > best_ov:
                best, best_ov = ln, ov
        if best is not None:
            best.chars.append(c)
        elif c.text.strip():
            orphans.append(c)
    orphans.sort(key=lambda c: (c.top, c.x0))
    for c in orphans:
        if lines and all(x.small for x in lines[-1].chars) and abs(c.top - lines[-1].chars[0].top) <= LINE_TOL:
            lines[-1].chars.append(c)
        else:
            lines.append(Line(c.page, [c]))
    for ln in lines:
        _trim_spaces(ln)
        ln.finalize()
    lines.sort(key=lambda ln: (ln.top, ln.x0))
    return lines


def _trim_spaces(ln: Line) -> None:
    ln.chars.sort(key=lambda c: (c.x0, c.top))
    while ln.chars and not ln.chars[0].text.strip():
        ln.chars.pop(0)
    while ln.chars and not ln.chars[-1].text.strip():
        ln.chars.pop()


def load(path) -> DocText:
    pages: list[PageData] = []
    with pdfplumber.open(path) as pdf:
        body = _body_size(pdf)
        for page in pdf.pages:
            idx = page.page_number - 1
            dedup = page.dedupe_chars()
            chars = [Ch(c["text"], c["x0"], c["x1"], c["top"], c["bottom"], c["size"], idx, c["size"] < body * SMALL_RATIO) for c in dedup.chars]
            h = page.height
            graphics = [
                Graphic(kind, idx, o["x0"], o["x1"], o["top"], o["bottom"])
                for kind in ("images", "curves", "lines", "rects")
                for o in getattr(page, kind)
                if (o["bottom"] - o["top"]) < GRAPHIC_MAX_HEIGHT_RATIO * h
            ]
            pages.append(PageData(idx, page.width, h, _build_lines(chars), [c for c in chars if c.text.strip()], _removed(page, dedup), graphics))
    return DocText(pages, body)
