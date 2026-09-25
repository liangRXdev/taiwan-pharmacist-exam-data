"""compile 端重算：universe、MOD 判定、表頭身分（D11：manifest 不存判定結果）。"""

from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlparse

from .. import manifest, moexhtml, pdfhead, subjects
from ..acquire import discover
from ..config import FIRST_YEAR_ROC, KINDS, RELEASE_MIN_AGE_DAYS, ROOT

SUBJECTS = ("P1", "P2", "P3", "P4", "P5", "P6")


class DeriveError(ValueError):
    """整次 compile 失敗（非單科 parked）。"""


def universe(m: dict, release_date: date) -> dict[str, moexhtml.ExamBlock]:
    """自 discovery 所指年度頁重算含藥師類科之考試；任一年度頁缺失 → 整次失敗。"""
    years = [str(y) for y in range(FIRST_YEAR_ROC + 1911, release_date.year + 1)]
    revs = m["discovery"]["year_list_revs"]
    missing = [y for y in years if y not in revs]
    if missing:
        raise DeriveError(f"discovery 缺年度頁：{missing}")
    out: dict[str, moexhtml.ExamBlock] = {}
    for y in years:
        page = manifest.page_by_rev(m, revs[y])
        if page["http_status"] != 200:
            raise DeriveError(f"年度頁 {y} HTTP {page['http_status']}")
        blocks = moexhtml.parse_exam_blocks(manifest.read_page(m, revs[y]).decode("utf-8"))
        for code, blk in blocks.items():
            if blk.pharm_rows() and int(code[:3]) >= FIRST_YEAR_ROC:
                out[code] = blk
    if not out:
        raise DeriveError("universe 為空")
    return out


def universe_keys(blocks: dict[str, moexhtml.ExamBlock]) -> set[tuple[str, str]]:
    return {(code, p) for code in blocks for p in SUBJECTS}


@dataclass
class ModJudgement:
    result: str             # present | absent | inconclusive
    reason: str
    page_rev: str | None
    fetched_on: date | None


def mod_judgement(m: dict, t: dict) -> ModJudgement:
    rev = t.get("mod_page_rev")
    if rev is None:
        return ModJudgement("inconclusive", "無 mod_page_rev", None, None)
    page = manifest.page_by_rev(m, rev)
    fetched_on = datetime.fromisoformat(page["fetched_at"]).date()
    j = lambda res, why: ModJudgement(res, why, rev, fetched_on)
    if page["http_status"] != 200:
        return j("inconclusive", f"HTTP {page['http_status']}")
    if urlparse(page["final_url"]).query != urlparse(discover.subject_list_url(t["exam_code"])).query:
        return j("inconclusive", f"final_url 不符：{page['final_url']}")
    try:
        block = moexhtml.subject_page_block(manifest.read_page(m, rev).decode("utf-8"), t["exam_code"])
    except moexhtml.PageStructureError as e:
        return j("inconclusive", f"頁面結構：{e}")
    rows = [r for r in block.pharm_rows() if (r.category_code, r.subject_file_code) == (t["category_code"], t["subject_file_code"])]
    if len(rows) != 1:
        return j("inconclusive", f"科目列 {len(rows)} 筆")
    row = rows[0]
    if row.links["MOD"] is not None:
        return j("present", "頁面含更正答案連結")
    q_rev = t["current"]["Q"]
    q_url = manifest.revision(t, q_rev)["url"] if q_rev else None
    if row.cells != 3 or row.links["Q"] is None or discover.file_url(row.links["Q"]) != q_url:
        return j("inconclusive", "positive control 失敗（Q 連結缺或與 current.Q 不符、或欄位數 ≠ 3）")
    return j("absent", "positive control 通過且無更正答案連結")


def original_allowed(jd: ModJudgement, exam_date: date | None) -> bool:
    return jd.result == "absent" and exam_date is not None and jd.fetched_on is not None and (jd.fetched_on - exam_date).days >= RELEASE_MIN_AGE_DAYS


def headers(m: dict, t: dict) -> dict[str, pdfhead.Header]:
    return {k: pdfhead.read_header(ROOT / manifest.revision(t, t["current"][k])["raw_path"]) for k in KINDS if t["current"][k]}


def identity_errors(t: dict, hs: dict[str, pdfhead.Header], block: moexhtml.ExamBlock) -> list[str]:
    """AC-12：表頭與 tuple 一致、Q/ANS/MOD 互相一致。"""
    errs = []
    p = t["subject"]
    for k, h in hs.items():
        if h.kind != k:
            errs.append(f"{k} 文件類型為 {h.kind}")
        if h.year_roc != int(t["exam_code"][:3]) or (h.year_roc, h.session) != (block.year_roc, block.session):
            errs.append(f"{k} 年度場次 {h.year_roc}-{h.session} ≠ {t['exam_code']}（頁面 {block.year_roc}-{block.session}）")
        if subjects.subject_code(h.subject_name) != p:
            errs.append(f"{k} 科目 {h.subject_name} ≠ {p}")
        if subjects.CATEGORY_STAGE.get(h.category_name) != subjects.stage_of(p):
            errs.append(f"{k} 類科 {h.category_name} 與 {p} 階段不符")
    # 考試名稱全文不比：答案 PDF 會列入同場併考之其他類科，與試題 PDF 不同長
    ids = {(h.year_roc, h.session, h.category_name, h.subject_name, h.paper_code) for h in hs.values()}
    if len(ids) > 1:
        errs.append(f"Q/ANS/MOD 表頭互不一致：{sorted(ids)}")
    return errs
