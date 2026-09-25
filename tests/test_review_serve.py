"""MG-1 審查頁寫回：只允許改 result/reviewer/note 與日期原文；revs 與題目集合不可改。"""

import pytest

from tped import jsonio
from tped.build import review_serve


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = review_serve.Store.__new__(review_serve.Store)
    import threading
    s.lock = threading.Lock()
    path = tmp_path / "114020.json"
    jsonio.dump({"exam_code": "114020", "revs": {"P1": {"Q": "sha256:x"}}, "exam_date_source_quote": "",
                 "items": [{"id": "114-1-PHARM-P1-001", "result": None, "reviewer": "", "note": ""}]}, path)
    monkeypatch.setattr(s, "review_path", lambda code: path, raising=False)
    return s, path


def test_save_roundtrip(store):
    s, path = store
    s.save("114020", {"exam_date_source_quote": "考試日期： 114/1/17~1/19", "revs": {"P1": {"Q": "forged"}},
                      "items": [{"id": "114-1-PHARM-P1-001", "result": "pass", "reviewer": "LG", "note": ""}]})
    r = jsonio.load(path)
    assert r["items"][0]["result"] == "pass" and r["items"][0]["reviewer"] == "LG"
    assert r["revs"] == {"P1": {"Q": "sha256:x"}}, "revs 不可被請求改寫"
    assert r["exam_date_source_quote"].startswith("考試日期")


@pytest.mark.parametrize("body", [
    {"items": [{"id": "114-1-PHARM-P1-002", "result": "pass"}]},
    {"items": [{"id": "114-1-PHARM-P1-001", "result": "ok"}]},
])
def test_save_rejects(store, body):
    s, path = store
    before = path.read_bytes()
    with pytest.raises(ValueError):
        s.save("114020", body)
    assert path.read_bytes() == before
