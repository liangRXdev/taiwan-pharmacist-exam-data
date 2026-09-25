"""MG-1 人工閘門：依 compile 產出之 intermediate/mg1/{code}.json 建立 review/{code}.json 範本。

審查者逐題比對 PDF 視覺原文與 data/questions.json 之 L2（預期差異僅限 T），
將 result 填為 pass／fail、reviewer 填姓名縮寫，並核對 inputs/exams.json 之考試日期來源。
範本不會覆蓋既有 review 檔。
"""

import sys

from .. import jsonio
from ..config import INPUTS_EXAMS_PATH, ROOT


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: tped review-init EXAM_CODE", file=sys.stderr)
        return 2
    code = argv[0]
    src = ROOT / "intermediate" / "mg1" / f"{code}.json"
    dst = ROOT / "review" / f"{code}.json"
    if not src.exists():
        print(f"找不到 {src.relative_to(ROOT)}，請先執行 tped compile", file=sys.stderr)
        return 1
    if dst.exists():
        print(f"{dst.relative_to(ROOT)} 已存在，不覆蓋", file=sys.stderr)
        return 1
    mg1 = jsonio.load(src)
    exams = {e["exam_code"]: e for e in jsonio.load(INPUTS_EXAMS_PATH)} if INPUTS_EXAMS_PATH.exists() else {}
    jsonio.dump({
        "exam_code": code,
        "revs": mg1["revs"],
        "exam_date": exams.get(code, {}).get("exam_date"),
        "exam_date_source_url": exams.get(code, {}).get("exam_date_source_url"),
        "exam_date_source_quote": "",
        "not_applicable": mg1["not_applicable"],
        "items": [{"id": i, "labels": mg1["labels"][i], "result": None, "reviewer": "", "note": ""} for i in mg1["sample"]],
    }, dst)
    print(f"已建立 {dst.relative_to(ROOT)}（{len(mg1['sample'])} 題）")
    return 0
