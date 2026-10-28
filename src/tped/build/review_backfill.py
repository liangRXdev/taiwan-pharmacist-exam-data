"""`tped review-backfill-digest EXAM_CODE | --all`：v0.9 以前建立之 MG-1 審查檔一次性回填 l2_digest（spec §6.2）。

以目前 compile 產出之 intermediate/mg1/{code}.json 逐題寫入 l2_digest；只寫此欄位，判定、reviewer、
日期摘錄等一律不動。前置檢查——revs、樣本 id（含重複）、exam_date／exam_date_source_url 與目前一致，
且全部題目 pass、審查者與日期摘錄非空（即除缺 digest 外與 mg1_pass 等同）——不成立即拒絕。
部分題目已有 l2_digest 之檔拒絕處理；全部已有者略過。--all 先全部檢查，任一不符則一檔都不寫。
"""

import copy
import re
import sys
from pathlib import Path

from .. import jsonio
from ..config import INPUTS_EXAMS_PATH, ROOT

USAGE = "usage: tped review-backfill-digest EXAM_CODE | --all"


def precondition_errors(review: dict, mg1: dict, exam: dict | None, require_missing: bool = True) -> list[str]:
    from .run import _review_verdict
    items = review.get("items", [])
    errs = []
    has = sum(1 for it in items if "l2_digest" in it)
    if require_missing and has:
        errs.append(f"已有 l2_digest 之題 {has}/{len(items)}（只處理整檔皆缺者）")
    if review.get("revs") != mg1["revs"]:
        errs.append("revs 與目前 compile 不符")
    # 假設已回填之候選檔：若判定不是 pass，表示 digest 以外之條件（樣本、日期來源、人工判定）不成立
    cand = copy.deepcopy(review)
    for it in cand["items"]:
        it["l2_digest"] = mg1["l2_digest"].get(it.get("id"))
    verdict = _review_verdict(cand, mg1["sample"], digests=mg1["l2_digest"], exam=exam)["result"]
    if verdict != "pass":
        errs.append(f"除 l2_digest 外之判定為 {verdict}（樣本 id、日期來源或人工判定與目前不符）")
    return errs


def _with_digest(review: dict, digests: dict[str, str]) -> dict:
    out = copy.deepcopy(review)
    items = []
    for it in out["items"]:
        new = {}
        for k, v in it.items():
            new[k] = v
            if k == "labels":
                new["l2_digest"] = digests[it["id"]]
        new.setdefault("l2_digest", digests[it["id"]])
        items.append(new)
    out["items"] = items
    return out


def main(argv: list[str]) -> int:
    if argv == ["--all"]:
        codes = sorted(p.stem for p in (ROOT / "review").glob("*.json"))
    elif len(argv) == 1 and re.fullmatch(r"[0-9]{6}", argv[0]):
        codes = argv
    else:
        print(USAGE, file=sys.stderr)
        return 2
    exams = {e["exam_code"]: e for e in jsonio.load(INPUTS_EXAMS_PATH)} if INPUTS_EXAMS_PATH.exists() else {}
    plan: list[tuple[str, Path, dict]] = []
    failed = False
    for code in codes:
        dst = ROOT / "review" / f"{code}.json"
        src = ROOT / "intermediate" / "mg1" / f"{code}.json"
        if not dst.exists() or not src.exists():
            print(f"{code}：拒絕：缺 {dst.relative_to(ROOT) if not dst.exists() else src.relative_to(ROOT)}（先執行 tped compile）", file=sys.stderr)
            failed = True
            continue
        review, mg1 = jsonio.load(dst), jsonio.load(src)
        items = review.get("items", [])
        if items and all("l2_digest" in it for it in items):
            print(f"{code}：已有 l2_digest，略過")
            continue
        errs = precondition_errors(review, mg1, exams.get(code))
        if errs:
            print(f"{code}：拒絕：" + "；".join(errs), file=sys.stderr)
            failed = True
            continue
        plan.append((code, dst, _with_digest(review, mg1["l2_digest"])))
    if failed:
        return 1
    for code, dst, new in plan:
        jsonio.dump_atomic(new, dst)
        print(f"{code}：回填 {len(new['items'])} 題")
    return 0
