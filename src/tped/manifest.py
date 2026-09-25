"""manifest.json（spec §4.6）：只記錄觀測到什麼、存在哪裡；不存任何判定結果。"""

import gzip
import hashlib
from pathlib import Path

from . import jsonio
from .config import KINDS, MANIFEST_PATH, ROOT

SCHEMA_VERSION = 1


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rev_of(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def empty() -> dict:
    return {"schema_version": SCHEMA_VERSION, "pages": [], "discovery": {"year_list_revs": {}, "subject_list_revs": {}}, "tuples": []}


def load(path: Path = MANIFEST_PATH) -> dict:
    if not path.exists():
        return empty()
    m = jsonio.load(path)
    if m.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"manifest schema_version {m.get('schema_version')} 不支援")
    return m


def save(m: dict, path: Path = MANIFEST_PATH) -> None:
    normalize(m)
    jsonio.dump(m, path)


def normalize(m: dict) -> None:
    """固定排序（決定性輸出）；不變量檢查前必須先呼叫。"""
    m["pages"].sort(key=lambda p: p["rev"])
    m["tuples"].sort(key=lambda t: (t["exam_code"], t["subject"]))
    for t in m["tuples"]:
        t["revisions"].sort(key=lambda r: (r["fetched_at"], r["rev"]))
    m["discovery"]["year_list_revs"] = dict(sorted(m["discovery"]["year_list_revs"].items()))
    m["discovery"]["subject_list_revs"] = dict(sorted(m["discovery"]["subject_list_revs"].items()))


# ---------- raw 存取（內容定址、不可變） ----------

def write_immutable(path: Path, data: bytes) -> None:
    """同路徑已存在時內容必須相同；禁止覆寫。"""
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"raw 檔已存在且內容不同（禁止覆寫）：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def page_blob(html_bytes: bytes) -> bytes:
    """HTML 以 gzip（mtime=0）存放以節省空間；rev 仍為原始位元組之 SHA256。"""
    return gzip.compress(html_bytes, compresslevel=9, mtime=0)


def read_page(m: dict, rev: str) -> bytes:
    page = page_by_rev(m, rev)
    data = gzip.decompress((ROOT / page["raw_path"]).read_bytes())
    if rev_of(data) != rev:
        raise ValueError(f"頁面 {page['raw_path']} 解壓後 SHA256 與 rev 不符")
    return data


def read_pdf(t: dict, rev: str) -> bytes:
    r = revision(t, rev)
    data = (ROOT / r["raw_path"]).read_bytes()
    if rev_of(data) != rev:
        raise ValueError(f"{r['raw_path']} SHA256 與 rev 不符")
    return data


# ---------- 查詢 ----------

def page_by_rev(m: dict, rev: str) -> dict:
    hits = [p for p in m["pages"] if p["rev"] == rev]
    if len(hits) != 1:
        raise KeyError(f"pages 中 {rev} 出現 {len(hits)} 次")
    return hits[0]


def tuple_of(m: dict, exam_code: str, subject: str) -> dict | None:
    hits = [t for t in m["tuples"] if (t["exam_code"], t["subject"]) == (exam_code, subject)]
    if len(hits) > 1:
        raise ValueError(f"tuple {exam_code}/{subject} 重複")
    return hits[0] if hits else None


def revision(t: dict, rev: str) -> dict:
    hits = [r for r in t["revisions"] if r["rev"] == rev]
    if len(hits) != 1:
        raise KeyError(f"{t['exam_code']}/{t['subject']} revisions 中 {rev} 出現 {len(hits)} 次")
    return hits[0]


# ---------- 不變量（AC-9） ----------

def invariant_errors(m: dict, check_files: bool = True) -> list[str]:
    errs: list[str] = []
    all_revs: list[str] = [p["rev"] for p in m["pages"]]
    keys = set()
    for t in m["tuples"]:
        key = (t["exam_code"], t["subject"])
        if key in keys:
            errs.append(f"tuple 重複：{key}")
        keys.add(key)
        all_revs += [r["rev"] for r in t["revisions"]]
        cur = t["current"]
        if set(cur) != set(KINDS):
            errs.append(f"{key} current 鍵集合錯誤：{sorted(cur)}")
            continue
        if cur["Q"] is None:
            errs.append(f"{key} current.Q 為 null")
        for kind in KINDS:
            if cur[kind] is None:
                continue
            hits = [r for r in t["revisions"] if r["rev"] == cur[kind]]
            if len(hits) != 1:
                errs.append(f"{key} current.{kind} 指向 {len(hits)} 筆 revision")
            elif hits[0]["kind"] != kind:
                errs.append(f"{key} current.{kind} 指向 kind={hits[0]['kind']} 之 revision")
        order = [(r["fetched_at"], r["rev"]) for r in t["revisions"]]
        if order != sorted(order):
            errs.append(f"{key} revisions 未依 (fetched_at, rev) 排序")
        if t.get("mod_page_rev") and t["mod_page_rev"] not in {p["rev"] for p in m["pages"]}:
            errs.append(f"{key} mod_page_rev 不存在於 pages")
    dup = {r for r in all_revs if all_revs.count(r) > 1}
    if dup:
        errs.append(f"rev 重複：{sorted(dup)[:3]}")
    page_revs = {p["rev"] for p in m["pages"]}
    for ref in list(m["discovery"]["year_list_revs"].values()) + list(m["discovery"]["subject_list_revs"].values()):
        if ref not in page_revs:
            errs.append(f"discovery 引用不存在之頁面 {ref}")
    if check_files:
        for p in m["pages"]:
            f = ROOT / p["raw_path"]
            if not f.exists():
                errs.append(f"頁面檔不存在：{p['raw_path']}")
            elif rev_of(gzip.decompress(f.read_bytes())) != p["rev"]:
                errs.append(f"頁面檔 SHA256 不符：{p['raw_path']}")
        for t in m["tuples"]:
            for r in t["revisions"]:
                f = ROOT / r["raw_path"]
                if not f.exists():
                    errs.append(f"PDF 不存在：{r['raw_path']}")
                elif rev_of(f.read_bytes()) != r["rev"]:
                    errs.append(f"PDF SHA256 不符：{r['raw_path']}")
    return errs
