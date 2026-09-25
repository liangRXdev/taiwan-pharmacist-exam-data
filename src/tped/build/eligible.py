"""Release 資格（spec §5.4）與 MG-1 抽樣（spec §6.2）。純函式。"""

import hashlib
from dataclasses import dataclass
from datetime import date

from ..config import RELEASE_MIN_AGE_DAYS

LABEL_ORDER = ("figure", "dedupe", "compat", "script", "table", "crosspage", "corrected", "edge")
SAMPLE_SIZE = 20


@dataclass
class TupleState:
    exam_code: str
    subject: str
    parked_reason: str | None          # E1 / E2
    answer_status: str | None          # E3
    revs: dict                         # 本次 compile 實際使用之 Q/ANS/MOD/mod_page


def withheld_reasons(st: TupleState, exam_date: date | None, release_date: date, review: dict | None, exam_revs: dict) -> list[str]:
    """回傳排序之 withheld 原因；空 = 可發布（前提：未 parked）。"""
    out = []
    if st.answer_status not in ("corrected", "original"):
        out.append("unverified")
    if exam_date is None:
        out.append("exam_date_missing")
    elif (release_date - exam_date).days < RELEASE_MIN_AGE_DAYS:
        out.append("too_recent")
    if review is None:
        out.append("mg1_missing")
    elif review.get("revs") != exam_revs:
        out.append("mg1_stale")
    elif review.get("result") != "pass":
        out.append("mg1_failed")
    return sorted(out)


def coverage_record(st: TupleState, withheld: list[str]) -> dict:
    if st.parked_reason:
        status, reasons = "parked", [st.parked_reason]
    elif withheld:
        status, reasons = "withheld", withheld
    else:
        status, reasons = "released", []
    return {"exam_code": st.exam_code, "subject": st.subject, "status": status, "reasons": reasons, "revs": st.revs}


def seed_of(q_revs_by_subject: dict[str, str]) -> str:
    return "".join(q_revs_by_subject[p] for p in sorted(q_revs_by_subject))


def _h(seed: str, qid: str) -> str:
    return hashlib.sha256((seed + qid).encode("utf-8")).hexdigest()


def mg1_sample(labels: dict[str, list[str]], seed: str) -> list[str]:
    """貪婪覆蓋：每個風險標籤至少一題（依標籤順序、同標籤取 hash 最小），再以 hash 補足至 20。"""
    ids = sorted(labels)
    chosen: list[str] = []
    for lab in LABEL_ORDER:
        members = [i for i in ids if lab in labels[i]]
        if not members or any(lab in labels[c] for c in chosen):
            continue
        chosen.append(min(members, key=lambda i: _h(seed, i)))
    chosen = chosen[:SAMPLE_SIZE]
    rest = sorted((i for i in ids if i not in chosen), key=lambda i: _h(seed, i))
    chosen += rest[:SAMPLE_SIZE - len(chosen)]
    return sorted(chosen)


def mg1_not_applicable(labels: dict[str, list[str]]) -> list[str]:
    present = {lab for labs in labels.values() for lab in labs}
    return [lab for lab in LABEL_ORDER if lab not in present]
