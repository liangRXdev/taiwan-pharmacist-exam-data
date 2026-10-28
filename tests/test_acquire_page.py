"""acquire 頁面存證去重（_store_page）：只差 ASP.NET 隱藏欄位不得新增 revision；內容、狀態碼或跨更正窗口才新增。

離線：http.get 以真實已存證頁面改寫後回放，寫檔導向 tmp。
"""

import re
from datetime import date

import pytest

from tped import manifest
from tped.acquire import http, run

URL_115090 = "https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx?y=2026&e=115090"
BEFORE_WINDOW = date(2026, 10, 16)   # 115090 exam_date 2026-07-19 + 90 = 2026-10-17
AFTER_WINDOW = date(2026, 10, 28)


PREV_REV = "sha256:069363346f20a06f9b485759550d744995b10b42f375a08cfaf7d88a67f10b76"  # 115090 科目頁，2026-09-25（窗口前）抓取


def _prev(m):
    rev = PREV_REV
    return rev, manifest.read_page(m, rev).decode("utf-8")


def _revisit(html: str) -> str:
    """模擬同內容重抓：VIEWSTATE／EVENTVALIDATION 每次請求都不同。"""
    html, n = re.subn(r'(id="__(?:VIEWSTATE|EVENTVALIDATION)" value=")[^"]*', r"\1REFETCHED", html)
    assert n == 2
    return html


@pytest.fixture
def acq(m_copy, tmp_path, monkeypatch):
    monkeypatch.setattr(run, "PAGES_DIR", tmp_path)
    monkeypatch.setattr(run, "ROOT", tmp_path.parent)

    def make(today: date, html: str, status: int = 200):
        monkeypatch.setattr(http, "get", lambda url: http.Response(url, status, url, "text/html", html.encode("utf-8")))
        return run.Acquirer(m_copy, today)
    return make


def test_same_content_new_viewstate_keeps_rev(acq, m_copy):
    prev_rev, html = _prev(m_copy)
    a = acq(BEFORE_WINDOW, _revisit(html))
    n_pages = len(a.m["pages"])
    rev, _ = a._store_page("subject_list", URL_115090, prev_rev, "115090")
    assert rev == prev_rev
    assert len(a.m["pages"]) == n_pages and a.changes == []


def test_content_change_appends_rev(acq, m_copy):
    prev_rev, html = _prev(m_copy)
    assert "藥師" in html
    a = acq(BEFORE_WINDOW, _revisit(html).replace("藥師", "藥師（更正）", 1))
    rev, _ = a._store_page("subject_list", URL_115090, prev_rev, "115090")
    assert rev != prev_rev
    new = manifest.page_by_rev(a.m, rev)
    assert new["content_digest"].startswith("sha256:") and new["content_digest"] != manifest.page_by_rev(a.m, prev_rev)["content_digest"]


def test_status_change_appends_rev(acq, m_copy):
    prev_rev, html = _prev(m_copy)
    a = acq(BEFORE_WINDOW, _revisit(html), status=203)
    rev, _ = a._store_page("subject_list", URL_115090, prev_rev, "115090")
    assert rev != prev_rev


def test_crossing_correction_window_appends_rev(acq, m_copy):
    prev_rev, html = _prev(m_copy)
    a = acq(AFTER_WINDOW, _revisit(html))
    rev, _ = a._store_page("subject_list", URL_115090, prev_rev, "115090")
    assert rev != prev_rev
    assert manifest.page_by_rev(a.m, rev)["content_digest"] == manifest.page_by_rev(a.m, prev_rev)["content_digest"]
