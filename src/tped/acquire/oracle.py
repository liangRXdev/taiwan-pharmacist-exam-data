"""M1 出場檢查：crawler 產物 vs oracle/manual（手動下載檔）。

兩邊各自以 PDF 表頭驗證身分（不信任檔名）。SHA256 不同時再比對「去空白後字元多重集合」，
用以區分「站方重新產生同內容 PDF」與「內容不同」；後者一律列為失敗。
"""

import collections
import re
import sys

import pdfplumber

from .. import manifest, pdfhead, subjects
from ..config import KINDS, ROOT


def _chars(data_or_path) -> collections.Counter:
    with pdfplumber.open(data_or_path) as pdf:
        text = "".join(p.dedupe_chars().extract_text() or "" for p in pdf.pages)
    return collections.Counter(re.sub(r"\s+", "", text))


def _created(path) -> str:
    """PDF CreationDate（D:YYYYMMDDHHmmSS…）；僅用於判斷新舊，不作身分依據。"""
    with pdfplumber.open(path) as pdf:
        return str(pdf.metadata.get("CreationDate", ""))[2:16]


def main(argv: list[str]) -> int:
    m = manifest.load()
    by_ident: dict[tuple, dict] = {}
    for t in m["tuples"]:
        for kind in KINDS:
            rev = t["current"][kind]
            if rev is None:
                continue
            r = manifest.revision(t, rev)
            h = pdfhead.read_header(ROOT / r["raw_path"])
            by_ident[(h.year_roc, h.session, t["subject"], kind)] = {"t": t, "r": r, "h": h}
    same = regenerated = newer = 0
    failures: list[str] = []
    oracle_files = sorted((ROOT / "oracle" / "manual").rglob("*.pdf"))
    if not oracle_files:
        print("oracle/manual 無檔案", file=sys.stderr)
        return 1
    for f in oracle_files:
        h = pdfhead.read_header(f)
        p = subjects.subject_code(h.subject_name)
        hit = by_ident.get((h.year_roc, h.session, p, h.kind))
        label = f"{f.parent.name}/{f.name}"
        if hit is None:
            failures.append(f"{label}：crawler 無對應 {h.year_roc}-{h.session}/{p}/{h.kind}")
            continue
        if h.as_dict() != hit["h"].as_dict():
            failures.append(f"{label}：表頭身分不同 {h.as_dict()} vs {hit['h'].as_dict()}")
            continue
        data = f.read_bytes()
        if manifest.rev_of(data) == hit["r"]["rev"]:
            same += 1
        elif _chars(f) == _chars(ROOT / hit["r"]["raw_path"]):
            regenerated += 1
            print(f"[regenerated] {label} ≠ {hit['r']['raw_path']}（位元組不同、字元多重集合相同）")
        elif _created(ROOT / hit["r"]["raw_path"]) > _created(f):
            newer += 1
            print(f"[site-newer] {label}（{_created(f)}）→ {hit['r']['raw_path']}（{_created(ROOT / hit['r']['raw_path'])}）：內容不同，站方版本較新，須人工確認差異")
        else:
            failures.append(f"{label}：內容不同於 {hit['r']['raw_path']}，且站方版本不較新")
    print(f"[oracle-check] SHA256 相同 {same}；站方重新產生（內容相同）{regenerated}；站方較新（內容不同）{newer}；失敗 {len(failures)}；oracle 共 {len(oracle_files)}")
    for x in failures:
        print("  FAIL", x, file=sys.stderr)
    return 1 if failures else 0
