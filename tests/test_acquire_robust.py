"""acquire 端點結果分類（spec §4.6 Universe、§5.2）與 compile universe 交叉驗證。

離線：http.get 以真實已存證頁面（或其改寫）回放，寫檔導向 tmp；不連考選部。
"""

import copy
import re
from datetime import date

import pytest
import requests

from tped import manifest, moexhtml
from tped.acquire import http, run
from tped.build import derive
from conftest import RELEASE_DATE

TODAY = date(2026, 10, 28)
YEAR_URL = re.compile(r"\?y=(\d{4})$")
OPTION_115090 = '<option value="115090">'


def _year_html(m, y: str) -> str:
    return manifest.read_page(m, m["discovery"]["year_list_revs"][y]).decode("utf-8")


def _subject_html(m, code: str) -> str:
    return manifest.read_page(m, m["discovery"]["subject_list_revs"][code]).decode("utf-8")


@pytest.fixture
def acq(m_copy, tmp_path, monkeypatch):
    """routes(url) → (status, html)；未列之 URL 一律失敗（證明流程未繼續往下抓）。"""
    monkeypatch.setattr(run, "PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr(run, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(run, "ROOT", tmp_path)

    def make(routes, today: date = TODAY):
        def get(url):
            status, html = routes(url)
            return http.Response(url, status, url, "text/html", html.encode("utf-8"))
        monkeypatch.setattr(http, "get", get)
        monkeypatch.setattr(http, "get_pdf", lambda url: pytest.fail(f"不應下載 PDF：{url}"))
        return run.Acquirer(m_copy, today)
    return make


def _only_years(m, mutate=lambda y, html: html, status=lambda y: 200):
    def routes(url):
        mm = YEAR_URL.search(url)
        if not mm:
            pytest.fail(f"年度頁驗證失敗時不應繼續抓：{url}")
        y = mm.group(1)
        return status(y), mutate(y, _year_html(m, y))
    return routes


# ---------- #3 年度頁：非 200、下拉選單與表格區塊交叉驗證 ----------

def test_year_page_blocks_real(m):
    for y in m["discovery"]["year_list_revs"]:
        blocks = moexhtml.year_page_blocks(_year_html(m, y), int(y))
        assert blocks and set(blocks) == {c for c, _ in moexhtml.parse_exam_options(_year_html(m, y))}


@pytest.mark.parametrize("name,mutate", [
    ("ddlExamCode 缺失", lambda html: html.replace("ctl00_holderContent_ddlExamCode", "ctl00_holderContent_ddlRenamed")),
    ("表格有、選單無", lambda html: html.replace(OPTION_115090, '<option value="">')),
    ("選單有、表格無", lambda html: html.replace(OPTION_115090, '<option value="115999"></option>' + OPTION_115090)),
    ("選單含他年度 code（session 錯置）", lambda html: html.replace(OPTION_115090, '<option value="114090"></option>' + OPTION_115090)),
])
def test_year_page_blocks_drift(m, name, mutate):
    html = _year_html(m, "2026")
    assert OPTION_115090 in html
    with pytest.raises(moexhtml.PageStructureError):
        moexhtml.year_page_blocks(mutate(html), 2026)


def test_acquire_year_page_non_200_aborts(acq, m_copy, tmp_path):
    n_pages = len(m_copy["pages"])
    a = acq(_only_years(m_copy, status=lambda y: 404))
    with pytest.raises(moexhtml.PageStructureError, match="HTTP 404"):
        a.run()
    assert len(a.m["pages"]) == n_pages
    assert not (tmp_path / "pages").exists(), "非 200 年度頁不得寫入 raw"


def test_acquire_year_page_drift_aborts(acq, m_copy):
    a = acq(_only_years(m_copy, mutate=lambda y, html: html.replace("ctl00_holderContent_ddlExamCode", "x")))
    with pytest.raises(moexhtml.PageStructureError, match="ddlExamCode"):
        a.run()


def test_acquire_wrong_year_page_aborts(acq, m_copy):
    """session 狀態：y=2026 回傳 2025 年度頁 → 不得以 114 年考試當作 2026 之 universe。"""
    a = acq(_only_years(m_copy, mutate=lambda y, html: _year_html(m_copy, "2025") if y == "2026" else html))
    with pytest.raises(moexhtml.PageStructureError):
        a.run()


def test_compile_universe_cross_validates(m, monkeypatch):
    rev26 = m["discovery"]["year_list_revs"]["2026"]
    orig = manifest.read_page

    def fake(mm, rev):
        data = orig(mm, rev)
        return data.decode("utf-8").replace(OPTION_115090, '<option value="">').encode("utf-8") if rev == rev26 else data

    monkeypatch.setattr(derive.manifest, "read_page", fake)
    with pytest.raises(derive.DeriveError, match="2026"):
        derive.universe(m, RELEASE_DATE)


# ---------- #4 科目頁非 200：存證、更新 mod_page_rev、記 problems，不中止 ----------

def test_subject_page_non_200_does_not_abort(acq, m_copy):
    code = "115090"
    before = {t["subject"]: t["mod_page_rev"] for t in m_copy["tuples"] if t["exam_code"] == code}
    a = acq(lambda url: (302, "") if url.endswith(f"e={code}") else pytest.fail(url))
    a._exam(code)
    rev = a.m["discovery"]["subject_list_revs"][code]
    page = manifest.page_by_rev(a.m, rev)
    assert page["http_status"] == 302 and page["role"] == "subject_list"
    tuples = [t for t in a.m["tuples"] if t["exam_code"] == code]
    assert len(tuples) == 6 and all(t["mod_page_rev"] == rev != before[t["subject"]] for t in tuples)
    assert any(code in p and "302" in p for p in a.problems)
    jd = derive.mod_judgement(a.m, copy.deepcopy(tuples[0]))
    assert jd.result == "inconclusive" and jd.page_rev == rev


# ---------- Low：acquire parked 強制重抓、requests 例外、PDF 開檔例外 ----------

def _row(m, code="113020", p="P4"):
    block = moexhtml.subject_page_block(_subject_html(m, code), code)
    t = manifest.tuple_of(m, code, p)
    row = next(r for r in block.pharm_rows() if (r.category_code, r.subject_file_code) == (t["category_code"], t["subject_file_code"]))
    return block, row, t


def test_acquire_parked_forces_refetch(acq, m_copy, monkeypatch):
    """考後 > 180 天且 current 齊全：acquire 期 parked 若不強制重抓，將永久 parked。"""
    a = acq(lambda url: pytest.fail(url))
    block, row, t = _row(m_copy)
    t["parked"] = {"reason": "fetch_fail", "stage": "acquire", "detail": "x", "since": "2024-03-01T00:00:00+08:00"}
    assert not a._in_recheck_window("113020")
    fetched = []
    monkeypatch.setattr(a, "_fetch_pdf", lambda t, block, row, p, kind, href: fetched.append(kind))
    a._tuple(block, row, "P4", t["mod_page_rev"])
    assert fetched and t["parked"] is None


def test_acquire_compile_parked_not_refetched_outside_window(acq, m_copy, monkeypatch):
    a = acq(lambda url: pytest.fail(url))
    block, row, t = _row(m_copy)
    monkeypatch.setattr(a, "_fetch_pdf", lambda *args: pytest.fail("current 齊全且不在複查窗口、非 acquire parked：不應重抓"))
    a._tuple(block, row, "P4", t["mod_page_rev"])


def test_http_request_exception_is_retryable(monkeypatch):
    calls = []

    def boom(*a, **kw):
        calls.append(1)
        raise requests.exceptions.ChunkedEncodingError("連線中斷")

    monkeypatch.setattr(http.requests, "get", boom)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(http.Retryable):
        http.get("https://example.invalid/")
    assert len(calls) == http.RETRIES


@pytest.mark.parametrize("data", [b"%PDF-1.4\ngarbage\n%%EOF\n", b"%PDF-1.7\n1 0 obj << /Type /Catalog >>\n%%EOF"])
def test_fetch_pdf_unopenable_is_unusable(acq, m_copy, monkeypatch, tmp_path, data):
    a = acq(lambda url: pytest.fail(url))
    block, row, t = _row(m_copy)
    monkeypatch.setattr(http, "get_pdf", lambda url: data)
    with pytest.raises(http.Unusable):
        a._fetch_pdf(t, block, row, "P4", "Q", row.links["Q"])
    assert not list((tmp_path / "raw").rglob("*.pdf")) and not list((tmp_path / "raw").rglob("*.tmp"))
