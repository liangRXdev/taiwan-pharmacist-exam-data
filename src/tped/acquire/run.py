"""acquire：只觀測並保存證據（HTML／PDF），不做判定（spec §5、D11）。

流程：
  1. 抓 113 年起各年度頁 → 存證 → 解析含藥師類科之 exam_code
  2. 逐場抓科目頁（e=code）→ 存證 → 列出 P1–P6 科目列
  3. 逐科下載 Q / ANS / MOD，驗證表頭身分後內容定址存放，append revision

任一 Retryable、年度頁非 200 或結構漂移 → 整次中止、不寫 manifest。
Unusable → 該科 parked；科目頁非 200 → 存證並記 problems（compile 判 inconclusive）；其餘繼續，結束時 exit 1。
"""

import sys
from collections.abc import Callable
from datetime import date, datetime

from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException

from .. import jsonio, manifest, moexhtml, pdfhead, subjects
from ..config import FIRST_YEAR_ROC, INPUTS_EXAMS_PATH, KINDS, MOD_RECHECK_MAX_AGE_DAYS, PAGES_DIR, RAW_DIR, RELEASE_MIN_AGE_DAYS, ROOT, TZ
from . import discover, http


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _digest(html: bytes, exam_code: str | None) -> str:
    return "sha256:" + manifest.sha256_hex(moexhtml.content_digest_source(html.decode("utf-8", "replace"), exam_code).encode("utf-8"))


def _exam_dates() -> dict[str, date]:
    if not INPUTS_EXAMS_PATH.exists():
        return {}
    return {e["exam_code"]: date.fromisoformat(e["exam_date"]) for e in jsonio.load(INPUTS_EXAMS_PATH)}


class Acquirer:
    def __init__(self, m: dict, today: date):
        self.m = m
        self.today = today
        self.exam_dates = _exam_dates()
        self.problems: list[str] = []
        self.changes: list[str] = []

    # ---------- 頁面 ----------

    def _store_page(self, role: str, url: str, prev_rev: str | None, exam_code: str | None,
                    check: Callable[[http.Response], None] | None = None) -> tuple[str, bytes]:
        r = http.get(url)
        if check is not None:
            check(r)        # 於寫入 raw 前驗證：不通過即中止，不留孤兒檔
        html = r.content
        digest = _digest(html, exam_code)
        if prev_rev is not None:
            prev = manifest.page_by_rev(self.m, prev_rev)
            prev_html = manifest.read_page(self.m, prev_rev)
            # 舊頁 digest 由原始存證重算，不讀 manifest 之 content_digest：定義改過時不會整批誤判為變更
            if (_digest(prev_html, exam_code) == digest and prev["http_status"] == r.status
                    and prev["final_url"] == r.final_url and not self._crosses_window(prev, exam_code)):
                return prev_rev, prev_html
        rev = manifest.rev_of(html)
        path = PAGES_DIR / f"{rev[7:15]}.html.gz"
        manifest.write_immutable(path, manifest.page_blob(html))
        if all(p["rev"] != rev for p in self.m["pages"]):
            self.m["pages"].append({
                "rev": rev, "role": role, "url": url, "fetched_at": _now(),
                "http_status": r.status, "final_url": r.final_url,
                "content_digest": digest,
                "raw_path": path.relative_to(ROOT).as_posix(),
            })
            self.changes.append(f"page {role} {url}")
        return rev, html

    def _crosses_window(self, prev_page: dict, exam_code: str | None) -> bool:
        """舊頁抓於更正窗口內、今日已過窗口 → 必須重新存證，否則 original 永遠無法成立（D12）。"""
        if exam_code is None or exam_code not in self.exam_dates:
            return False
        threshold = self.exam_dates[exam_code].toordinal() + RELEASE_MIN_AGE_DAYS
        fetched = datetime.fromisoformat(prev_page["fetched_at"]).date().toordinal()
        return fetched < threshold <= self.today.toordinal()

    # ---------- 流程 ----------

    def run(self) -> None:
        codes: list[str] = []
        disc = self.m["discovery"]
        for year_ce in range(FIRST_YEAR_ROC + 1911, self.today.year + 1):
            key = str(year_ce)
            rev, html = self._store_page("year_list", discover.year_list_url(year_ce), disc["year_list_revs"].get(key), None,
                                         check=lambda r, y=year_ce: _check_year_page(r, y))
            disc["year_list_revs"][key] = rev
            codes += moexhtml.pharm_exam_codes(html.decode("utf-8"), year_ce)
        for code in sorted(set(codes)):
            self._exam(code)

    def _in_recheck_window(self, code: str) -> bool:
        d = self.exam_dates.get(code)
        return d is None or (self.today - d).days <= MOD_RECHECK_MAX_AGE_DAYS

    def _exam(self, code: str) -> None:
        disc = self.m["discovery"]["subject_list_revs"]
        rev, html = self._store_page("subject_list", discover.subject_list_url(code), disc.get(code), code)
        disc[code] = rev
        page = manifest.page_by_rev(self.m, rev)
        if page["http_status"] != 200:
            # 單場科目頁異常不中止整次 acquire：存證並指向此頁，compile 之 MOD 判定為 inconclusive（spec §5.2）
            for t in self.m["tuples"]:
                if t["exam_code"] == code:
                    t["mod_page_rev"] = rev
            self.problems.append(f"{code} 科目頁 HTTP {page['http_status']}（Location={page['final_url']}）：已存證、未下載 PDF")
            return
        block = moexhtml.subject_page_block(html.decode("utf-8"), code)
        seen: dict[str, moexhtml.SubjectRow] = {}
        for row in block.pharm_rows():
            p = subjects.subject_code(row.subject_name)
            if p is None:
                self._park(code, "?", "identity_mismatch", f"科目名稱無法對應 subjects.json：{row.subject_name}")
                continue
            if p in seen:
                raise moexhtml.PageStructureError(f"{code} 科目 {p} 出現兩列")
            seen[p] = row
            self._tuple(block, row, p, rev)

    def _tuple(self, block: moexhtml.ExamBlock, row: moexhtml.SubjectRow, p: str, page_rev: str) -> None:
        t = manifest.tuple_of(self.m, block.exam_code, p)
        if t is None:
            t = {"exam_code": block.exam_code, "subject": p, "category_code": row.category_code,
                 "subject_file_code": row.subject_file_code, "revisions": [],
                 "current": {k: None for k in KINDS}, "mod_page_rev": None, "parked": None}
            self.m["tuples"].append(t)
        elif (t["category_code"], t["subject_file_code"]) != (row.category_code, row.subject_file_code):
            self._park(block.exam_code, p, "identity_mismatch", f"官方代碼變更 {t['category_code']}/{t['subject_file_code']} → {row.category_code}/{row.subject_file_code}")
            return
        t["mod_page_rev"] = page_rev
        # acquire 期 parked 一律重抓：否則超過複查窗口後永遠無法解除
        need_fetch = (self._in_recheck_window(block.exam_code) or any(t["current"][k] is None and row.links[k] for k in KINDS)
                      or (t["parked"] is not None and t["parked"]["stage"] == "acquire"))
        if not need_fetch:
            return
        try:
            for kind in KINDS:
                href = row.links[kind]
                if href is None:
                    continue
                self._fetch_pdf(t, block, row, p, kind, href)
        except http.Unusable as e:
            self._park(block.exam_code, p, "fetch_fail", str(e))
            return
        except (pdfhead.HeaderError, IdentityError) as e:
            self._park(block.exam_code, p, "identity_mismatch", str(e))
            return
        if t["parked"] and t["parked"]["stage"] == "acquire":
            t["parked"] = None
            self.changes.append(f"unpark {block.exam_code}/{p}")

    def _fetch_pdf(self, t: dict, block, row, p: str, kind: str, href: str) -> None:
        if href != discover.expected_file_href(kind, block.exam_code, row.category_code, row.subject_file_code):
            raise IdentityError(f"連結格式不符端點契約：{href}")
        url = discover.file_url(href)
        data = http.get_pdf(url)
        path = RAW_DIR / str(block.year_roc) / block.exam_code / f"{p}_{kind}_{manifest.sha256_hex(data)[:8]}.pdf"
        tmp = path.with_suffix(".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        try:
            h = pdfhead.read_header(tmp)
        except (PdfminerException, MalformedPDFException) as e:
            raise http.Unusable(f"{url}：PDF 無法開啟（{e}）") from e
        finally:
            tmp.unlink()
        check_identity(h, kind, block, row, p)
        rev = manifest.rev_of(data)
        manifest.write_immutable(path, data)
        if all(r["rev"] != rev for r in t["revisions"]):
            t["revisions"].append({"rev": rev, "kind": kind, "url": url, "fetched_at": _now(), "raw_path": path.relative_to(ROOT).as_posix()})
            self.changes.append(f"revision {block.exam_code}/{p}/{kind} {rev[7:15]}")
        t["current"][kind] = rev

    def _park(self, code: str, p: str, reason: str, detail: str) -> None:
        self.problems.append(f"{code}/{p} {reason}: {detail}")
        t = manifest.tuple_of(self.m, code, p)
        if t is not None:
            t["parked"] = {"reason": reason, "stage": "acquire", "detail": detail, "since": _now()}


class IdentityError(ValueError):
    pass


def _check_year_page(r: http.Response, year_ce: int) -> None:
    """年度頁決定 universe：非 200 或下拉選單／表格區塊不一致 → 整次中止（spec §4.6）。"""
    if r.status != 200:
        raise moexhtml.PageStructureError(f"年度頁 {year_ce} HTTP {r.status}（Location={r.final_url}）")
    moexhtml.year_page_blocks(r.content.decode("utf-8"), year_ce)


def check_identity(h: pdfhead.Header, kind: str, block: moexhtml.ExamBlock, row: moexhtml.SubjectRow, p: str) -> None:
    """PDF 表頭必須與請求 tuple 一致（spec AC-12；session 錯置之防線）。"""
    errs = []
    if h.kind != kind:
        errs.append(f"文件類型 {h.kind} ≠ 請求 {kind}")
    if (h.year_roc, h.session) != (block.year_roc, block.session):
        errs.append(f"年度場次 {h.year_roc}-{h.session} ≠ 頁面 {block.year_roc}-{block.session}")
    if int(block.exam_code[:3]) != h.year_roc:
        errs.append(f"年度 {h.year_roc} ≠ exam_code {block.exam_code}")
    if h.category_name != row.pharm_category:
        errs.append(f"類科 {h.category_name} ≠ {row.pharm_category}")
    if subjects.subject_code(h.subject_name) != p:
        errs.append(f"科目 {h.subject_name} 不對應 {p}")
    if subjects.CATEGORY_STAGE.get(h.category_name) != subjects.stage_of(p):
        errs.append(f"類科 {h.category_name} 與 {p} 階段不符")
    if errs:
        raise IdentityError(f"{block.exam_code}/{p}/{kind}：" + "；".join(errs))


def main(argv: list[str]) -> int:
    today = datetime.now(TZ).date()
    m = manifest.load()
    acq = Acquirer(m, today)
    try:
        acq.run()
    except http.Retryable as e:
        print(f"[acquire] 中止（未寫入 manifest）：{e}", file=sys.stderr)
        return 1
    except moexhtml.PageStructureError as e:
        print(f"[acquire] 頁面結構不符，中止（未寫入 manifest）：{e}", file=sys.stderr)
        return 1
    manifest.normalize(m)
    errs = manifest.invariant_errors(m)
    if errs:
        print("[acquire] manifest 不變量失敗，未寫入：\n  " + "\n  ".join(errs), file=sys.stderr)
        return 1
    manifest.save(m)
    print(f"[acquire] 變更 {len(acq.changes)} 項")
    for c in acq.changes:
        print("  ", c)
    if acq.problems:
        print("[acquire] parked：\n  " + "\n  ".join(acq.problems), file=sys.stderr)
        return 1
    return 0
