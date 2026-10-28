"""acquire 頁面存證去重（_store_page）。

科目頁只比對該場考試區塊：ASP.NET 隱藏欄位、年度考試下拉選單新增他場考試皆不得新增 revision；
區塊內容（連結、科目、類科）、狀態碼、final_url 改變，或跨更正窗口，才新增。

離線：http.get 以真實已存證頁面改寫後回放，寫檔導向 tmp。
"""

import re
from datetime import date

import pytest

from tped import manifest, moexhtml
from tped.acquire import http, run

URL_115090 = "https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx?y=2026&e=115090"
BEFORE_WINDOW = date(2026, 10, 16)   # 115090 exam_date 2026-07-19 + 90 = 2026-10-17
AFTER_WINDOW = date(2026, 10, 28)

PREV_REV = "sha256:069363346f20a06f9b485759550d744995b10b42f375a08cfaf7d88a67f10b76"  # 115090 科目頁，2026-09-25（窗口前）抓取
# 2026-10-28 實抓：與 09-25 版只差年度下拉選單多了 115111、115150（非藥師）
DROPDOWN_ONLY = {
    "115090": (PREV_REV, "sha256:917ef44ca100258a3c4f85639e1fa3c7fd7cc81adcf6d1835941be7ada74d27a"),
    "115020": ("sha256:66c6b95e80c36a0962e5a2f7094c81cc7723441dd5c99621fcf8982a0db508d2",
               "sha256:f860dff8c80bcd7223ecefad2c38543f7e29f18da125c40a7ed0cc9ebd6e168d"),
}
MOD_HREF_P1 = 'href="wHandExamQandA_File.ashx?t=M&amp;code=115090&amp;c=305&amp;s=0401&amp;q=1"'  # 藥師(一) P1
MOD_HREF_OTHER = 'href="wHandExamQandA_File.ashx?t=M&amp;code=115090&amp;c=301&amp;s=0101&amp;q=1"'  # 同場他類科


def _prev(m):
    return PREV_REV, manifest.read_page(m, PREV_REV).decode("utf-8")


def _revisit(html: str) -> str:
    """模擬同內容重抓：VIEWSTATE／EVENTVALIDATION 每次請求都不同。"""
    html, n = re.subn(r'(id="__(?:VIEWSTATE|EVENTVALIDATION)" value=")[^"]*', r"\1REFETCHED", html)
    assert n == 2
    return html


@pytest.fixture
def acq(m_copy, tmp_path, monkeypatch):
    monkeypatch.setattr(run, "PAGES_DIR", tmp_path)
    monkeypatch.setattr(run, "ROOT", tmp_path.parent)

    def make(today: date, html: str, status: int = 200, final_url: str | None = None):
        monkeypatch.setattr(http, "get", lambda url: http.Response(url, status, final_url or url, "text/html", html.encode("utf-8")))
        return run.Acquirer(m_copy, today)
    return make


def _store(a):
    rev, _ = a._store_page("subject_list", URL_115090, PREV_REV, "115090")
    return rev


# ---------- 不得新增 revision ----------

def test_same_content_new_viewstate_keeps_rev(acq, m_copy):
    _, html = _prev(m_copy)
    a = acq(BEFORE_WINDOW, _revisit(html))
    n_pages = len(a.m["pages"])
    assert _store(a) == PREV_REV
    assert len(a.m["pages"]) == n_pages and a.changes == []


def test_dropdown_only_change_keeps_rev(acq, m_copy):
    """真實回歸：09-25→10-28 只多了他場考試選項，不可換 rev（否則 MG-1 全數 stale）。"""
    new_html = manifest.read_page(m_copy, DROPDOWN_ONLY["115090"][1]).decode("utf-8")
    a = acq(BEFORE_WINDOW, _revisit(new_html))
    assert _store(a) == PREV_REV


@pytest.mark.parametrize("code", sorted(DROPDOWN_ONLY))
def test_real_dropdown_pairs_same_digest(m, code):
    old, new = (manifest.read_page(m, r) for r in DROPDOWN_ONLY[code])
    assert old != new
    assert run._digest(old, code) == run._digest(new, code)
    assert run._digest(old, None) != run._digest(new, None), "整頁比對確實不同：證明區塊範圍才是讓它相同的原因"


# ---------- 必須新增 revision ----------

def test_block_link_change_appends_rev(acq, m_copy):
    _, html = _prev(m_copy)
    assert MOD_HREF_P1 in html
    changed = _revisit(html).replace(MOD_HREF_P1, 'href=""')
    a = acq(BEFORE_WINDOW, changed)
    rev = _store(a)
    assert rev != PREV_REV
    assert manifest.page_by_rev(a.m, rev)["content_digest"] == run._digest(changed.encode("utf-8"), "115090")


def test_other_category_change_keeps_rev(acq, m_copy):
    """同場他類科（c=301）更正連結變動，不影響藥師科目之 MOD 判定。"""
    _, html = _prev(m_copy)
    assert MOD_HREF_OTHER in html
    assert _store(acq(BEFORE_WINDOW, _revisit(html).replace(MOD_HREF_OTHER, 'href=""'))) == PREV_REV


def test_block_subject_name_change_appends_rev(acq, m_copy):
    _, html = _prev(m_copy)
    name = moexhtml.subject_page_block(html, "115090").pharm_rows()[0].subject_name
    assert html.count(f">{name}<") >= 1
    a = acq(BEFORE_WINDOW, _revisit(html).replace(f">{name}<", f">{name}（更正）<"))
    assert _store(a) != PREV_REV


def test_unparseable_page_appends_rev(acq, m_copy):
    """區塊解析失敗（如站方回整份年度頁）退回整頁比對，必定另存新證據。"""
    _, html = _prev(m_copy)
    broken = _revisit(html).replace("chk_115090_", "chk_115091_")
    with pytest.raises(moexhtml.PageStructureError):
        moexhtml.subject_page_block(broken, "115090")
    a = acq(BEFORE_WINDOW, broken)
    assert _store(a) != PREV_REV


def test_status_change_appends_rev(acq, m_copy):
    _, html = _prev(m_copy)
    assert _store(acq(BEFORE_WINDOW, _revisit(html), status=203)) != PREV_REV


def test_final_url_change_appends_rev(acq, m_copy):
    _, html = _prev(m_copy)
    assert _store(acq(BEFORE_WINDOW, _revisit(html), final_url=URL_115090 + "&x=1")) != PREV_REV


def test_crossing_correction_window_appends_rev(acq, m_copy):
    _, html = _prev(m_copy)
    a = acq(AFTER_WINDOW, _revisit(html))
    rev = _store(a)
    assert rev != PREV_REV
    assert manifest.page_by_rev(a.m, rev)["content_digest"] == run._digest(manifest.read_page(m_copy, PREV_REV), "115090")
