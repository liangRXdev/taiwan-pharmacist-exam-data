"""PDF 表頭身分解析（L1 = dedupe_chars 後文字，並做相容漢字正規化）。

試題 PDF 首頁：
  {考試名稱，可能跨兩行}
  代 號：1305
  類科名稱：藥師(一)
  科目名稱：藥學(一)(包括藥理學與藥物化學)
答案 PDF 首頁：
  測驗式試題標準答案 | 測驗題標準答案更正
  {考試名稱，中間夾「考試名稱：」標籤}
  類科名稱：藥師(一)
  科目名稱：藥學(一)(包括藥理學與藥物化學)(試題代號：1305)
  題 數：80題
"""

import re
from dataclasses import asdict, dataclass

import pdfplumber

from .textnorm import compat

DOC_TITLES = {"測驗式試題標準答案": "ANS", "測驗題標準答案更正": "MOD"}
_NAME_RE = re.compile(r"^(\d+)年第([一二三四])次")
_SESSION = {"一": 1, "二": 2, "三": 3, "四": 4}


class HeaderError(ValueError):
    pass


@dataclass(frozen=True)
class Header:
    kind: str            # Q | ANS | MOD（由文件本身判定）
    exam_name: str       # 去空白
    year_roc: int
    session: int
    category_name: str   # 藥師(一)
    subject_name: str    # 去除 (試題代號：…)
    paper_code: str

    def as_dict(self) -> dict:
        return asdict(self)


def first_page_lines(pdf: pdfplumber.PDF) -> list[str]:
    text = pdf.pages[0].dedupe_chars().extract_text() or ""
    return [compat(line).strip() for line in text.splitlines() if line.strip()]


def _nows(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _field(lines: list[str], label: str) -> tuple[int, str]:
    pat = re.compile(r"^" + r"\s*".join(label) + r"\s*：\s*(.*)$")
    hits = [(i, m.group(1).strip()) for i, ln in enumerate(lines) if (m := pat.match(ln))]
    if len(hits) != 1:
        raise HeaderError(f"表頭欄位「{label}」出現 {len(hits)} 次")
    return hits[0]


def _name_parts(name: str) -> tuple[int, int]:
    m = _NAME_RE.match(name)
    if not m:
        raise HeaderError(f"考試名稱無法解析年度／場次：{name[:40]!r}")
    return int(m.group(1)), _SESSION[m.group(2)]


def parse_header(lines: list[str]) -> Header:
    title = _nows(lines[0]) if lines else ""
    if title in DOC_TITLES:
        kind = DOC_TITLES[title]
        i_cat, cat = _field(lines, "類科名稱")
        name_lines = [ln for ln in lines[1:i_cat] if _nows(ln) != "考試名稱："]
        name = _nows("".join(name_lines)).replace("考試名稱：", "")
        _, subj_raw = _field(lines, "科目名稱")
        m = re.fullmatch(r"(.*)\(試題代號：(\d+)\)", _nows(subj_raw))
        if not m:
            raise HeaderError(f"答案 PDF 科目名稱缺試題代號：{subj_raw!r}")
        subject, paper = m.group(1), m.group(2)
    else:
        kind = "Q"
        i_code, code_raw = _field(lines, "代號")
        name = _nows("".join(lines[:i_code]))
        paper = _nows(code_raw)
        _, cat = _field(lines, "類科名稱")
        _, subject = _field(lines, "科目名稱")
        subject = _nows(subject)
    if not re.fullmatch(r"\d{4}", paper):
        raise HeaderError(f"試題代號格式不符：{paper!r}")
    year, session = _name_parts(name)
    return Header(kind, name, year, session, _nows(cat), subject, paper)


def read_header(path) -> Header:
    with pdfplumber.open(path) as pdf:
        return parse_header(first_page_lines(pdf))
