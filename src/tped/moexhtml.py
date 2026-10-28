"""考選部考畢試題頁面解析（純函式）。acquire 與 compile 共用，compile 據此重算 universe 與 MOD 判定。

頁面結構（2026-09 實測）：
  tr > td.level1          考試名稱
  tr > td.level2          類科名稱，如「專技高考_藥師(一)」
  tr（含 input#…chk_{code}_{c}_{s}）
      label.exam-title    科目名稱
      td.exam-question-ans × 3   依序 Q / S / M；無更正答案時 M 格存在但 <a> 無 href
每列同時有桌機版（td.exam-question-ans）與手機版（a.exam-question-ans-mobile）連結，只讀桌機版。
"""

import dataclasses
import json
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

_CHK_RE = re.compile(r"chk_(\d{6})_(\d+)_(\d+)$")
_PHARM_CAT_RE = re.compile(r"(?:^|_)(藥師\((?:一|二)\))$")
_EXAM_NAME_RE = re.compile(r"^(\d+)年第([一二三四])次")
_SESSION = {"一": 1, "二": 2, "三": 3, "四": 4}
_T_TO_KIND = {"Q": "Q", "S": "ANS", "M": "MOD"}


class PageStructureError(ValueError):
    """頁面結構不符預期——不得視為「沒有資料」。"""


@dataclass
class SubjectRow:
    exam_code: str
    category_code: str
    subject_file_code: str
    category_name: str          # 原文，如「專技高考_藥師(一)」
    subject_name: str
    links: dict[str, str | None] = field(default_factory=dict)  # kind → 相對 URL
    cells: int = 0              # td.exam-question-ans 數量（positive control 用）

    @property
    def pharm_category(self) -> str | None:
        m = _PHARM_CAT_RE.search(self.category_name)
        return m.group(1) if m else None


@dataclass
class ExamBlock:
    exam_code: str
    name: str
    rows: list[SubjectRow] = field(default_factory=list)

    @property
    def year_roc(self) -> int | None:
        m = _EXAM_NAME_RE.match(self.name)
        return int(m.group(1)) if m else None

    @property
    def session(self) -> int | None:
        m = _EXAM_NAME_RE.match(self.name)
        return _SESSION[m.group(2)] if m else None

    def pharm_rows(self) -> list[SubjectRow]:
        return [r for r in self.rows if r.pharm_category]


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def parse_exam_options(html: str) -> list[tuple[str, str]]:
    """年度頁之考試下拉選單 (code, 名稱)。"""
    sel = _soup(html).find(id="ctl00_holderContent_ddlExamCode")
    if sel is None:
        raise PageStructureError("找不到考試下拉選單 ddlExamCode")
    out = []
    for opt in sel.find_all("option"):
        v = (opt.get("value") or "").strip()
        if v:
            if not re.fullmatch(r"\d{6}", v):
                raise PageStructureError(f"非預期之 exam_code option：{v!r}")
            out.append((v, opt.get_text(strip=True)))
    return out


def _link_kind(href: str) -> tuple[str, dict[str, str]]:
    q = {k: v[0] for k, v in parse_qs(urlparse(href).query).items()}
    t = q.get("t", "")
    if t not in _T_TO_KIND:
        raise PageStructureError(f"非預期之檔案連結類型 t={t!r}：{href}")
    return _T_TO_KIND[t], q


def _parse_subject_tr(tr, exam_code_hint: str | None, category: str | None) -> SubjectRow:
    chk = tr.find("input", id=_CHK_RE)
    code, c, s = _CHK_RE.search(chk["id"]).groups()
    if category is None:
        raise PageStructureError(f"科目列 {chk['id']} 前沒有類科列")
    label = tr.find("label", class_="exam-title")
    if label is None:
        raise PageStructureError(f"科目列 {chk['id']} 沒有 exam-title")
    cells = tr.find_all("td", class_="exam-question-ans", recursive=False)
    row = SubjectRow(code, c, s, category, label.get_text(strip=True), {k: None for k in _T_TO_KIND.values()}, len(cells))
    for td in cells:
        a = td.find("a")
        href = a.get("href") if a is not None else None
        if not href:
            continue
        kind, q = _link_kind(href)
        if (q.get("code"), q.get("c"), q.get("s")) != (code, c, s):
            raise PageStructureError(f"連結參數與列身分不符：{href} vs chk_{code}_{c}_{s}")
        if row.links[kind] is not None and row.links[kind] != href:
            raise PageStructureError(f"同列重複 {kind} 連結且不同：{href}")
        row.links[kind] = href
    return row


def parse_exam_blocks(html: str) -> dict[str, ExamBlock]:
    """解析頁面中所有考試區塊。年度頁含全年所有考試；科目頁（e=）只含一場。"""
    soup = _soup(html)
    blocks: dict[str, ExamBlock] = {}
    exam_name: str | None = None
    category: str | None = None
    seen: set[str] = set()
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        classes = [c for td in tds for c in (td.get("class") or [])]
        if "level1" in classes:
            exam_name = tr.get_text(" ", strip=True)
            category = None
            continue
        if "level2" in classes:
            category = tr.get_text(" ", strip=True)
            continue
        chk = tr.find("input", id=_CHK_RE, recursive=True)
        if chk is None or tr.find("td", class_="link_3Ua", recursive=False) is None:
            continue
        if chk["id"] in seen:
            raise PageStructureError(f"科目列重複：{chk['id']}")
        seen.add(chk["id"])
        row = _parse_subject_tr(tr, None, category)
        if exam_name is None:
            raise PageStructureError(f"科目列 {chk['id']} 前沒有考試列")
        blk = blocks.setdefault(row.exam_code, ExamBlock(row.exam_code, exam_name))
        if blk.name != exam_name:
            raise PageStructureError(f"{row.exam_code} 出現於兩個不同考試名稱下")
        blk.rows.append(row)
    return blocks


def year_page_blocks(html: str, year_ce: int) -> dict[str, ExamBlock]:
    """年度頁（y=）：下拉選單 ddlExamCode 與表格區塊之 exam_code 集合必須相等，且皆屬請求年度。

    表格區塊消失或改版會使 universe 靜默縮小；站方 session 狀態可能回傳他年度之頁面。
    """
    opts = {code for code, _ in parse_exam_options(html)}
    blocks = parse_exam_blocks(html)
    wrong = sorted(c for c in opts | set(blocks) if int(c[:3]) + 1911 != year_ce)
    if wrong:
        raise PageStructureError(f"年度頁 {year_ce} 含他年度 exam_code：{wrong}")
    if opts != set(blocks):
        raise PageStructureError(f"年度頁 {year_ce} 下拉選單與表格區塊不符：僅選單 {sorted(opts - set(blocks))}、僅表格 {sorted(set(blocks) - opts)}")
    return blocks


def pharm_exam_codes(html: str, year_ce: int) -> list[str]:
    """年度頁中含藥師類科之考試 code（依 code 排序）。"""
    return sorted(code for code, b in year_page_blocks(html, year_ce).items() if b.pharm_rows())


def subject_page_block(html: str, exam_code: str) -> ExamBlock:
    """科目頁（e=code）必須恰只含請求之考試；無效 code 時站方回傳整份年度頁。"""
    blocks = parse_exam_blocks(html)
    if set(blocks) != {exam_code}:
        raise PageStructureError(f"科目頁應只含 {exam_code}，實際含 {sorted(blocks)}")
    return blocks[exam_code]


_VOLATILE_RE = re.compile(r'(id="__(?:VIEWSTATE|VIEWSTATEGENERATOR|EVENTVALIDATION)" value=")[^"]*(")')


def content_digest_source(html: str, exam_code: str | None = None) -> str:
    """僅供「內容是否變更」判斷；存證仍為原始位元組。

    科目頁（給 exam_code）只取該場考試名稱與藥師科目列之解析結果——compile 之 MOD 判定與身分比對只讀這些；
    頁面其他部分（年度考試下拉選單新增他場考試、同場他類科更正）變動不得換 rev，否則 MG-1 全數 stale。
    解析失敗退回整頁，異常頁一律另存新證據。年度頁去除 ASP.NET 每次請求都會變的隱藏欄位後整頁比對。
    """
    if exam_code is not None:
        try:
            block = subject_page_block(html, exam_code)
        except PageStructureError:
            pass
        else:
            scope = {"exam_code": block.exam_code, "name": block.name, "rows": [dataclasses.asdict(r) for r in block.pharm_rows()]}
            return json.dumps(scope, ensure_ascii=False, sort_keys=True)
    return _VOLATILE_RE.sub(r"\1\2", html)
