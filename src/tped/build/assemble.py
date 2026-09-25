"""單一 tuple（exam_code × subject）之 canonical 題目組裝與驗證。"""

from dataclasses import dataclass, field

from .. import manifest, subjects, textnorm
from ..config import ROOT
from . import apdf, crosscheck, pdftext, qparse, validate
from .derive import ModJudgement, original_allowed

HLINE_MAX_H = 1.5
HLINE_MIN_W = 20.0


@dataclass
class TupleResult:
    exam_code: str
    subject: str
    records: list[dict] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)      # (reason, message)
    labels: dict[str, list[str]] = field(default_factory=dict)       # id → MG-1 風險標籤
    figures: list[tuple[str, int, tuple]] = field(default_factory=list)   # (png 路徑, page, bbox)
    intermediate: dict = field(default_factory=dict)
    has_small: bool = False

    @property
    def parked_reason(self) -> str | None:
        return self.errors[0][0] if self.errors else None


def _labels(q: qparse.ParsedQuestion, doc: pdftext.DocText, parsed: qparse.ParsedDoc, corrected: set[int], n: int) -> list[str]:
    """MG-1 風險標籤：由 L0／版面證據決定，不依賴 L2 內容。"""
    out = []
    if q.graphics:
        out.append("figure")
    if any(any(r.page == rm["page"] and r.top <= rm["top"] < r.bottom for r in q.region) for rm in parsed.removed):
        out.append("dedupe")
    own = [key for key, lab in parsed.attribution.items() if lab.startswith(f"q:{q.no}:")]
    if any(textnorm.is_compat(k[3]) for k in own):
        out.append("compat")
    if any(q.stem_l1.small) or any(any(s.small) for s in q.options_l1.values()):
        out.append("script")
    hlines = [g for g in q.graphics if g.kind in ("lines", "rects") and (g.bottom - g.top) <= HLINE_MAX_H and (g.x1 - g.x0) >= HLINE_MIN_W]
    if len(hlines) >= 2:
        out.append("table")
    if len({r.page for r in q.region}) > 1:
        out.append("crosspage")
    if q.no in corrected:
        out.append("corrected")
    if q.no in (1, n):
        out.append("edge")
    return out


def build(m: dict, t: dict, jd: ModJudgement, exam_date, session: int) -> TupleResult:
    res = TupleResult(t["exam_code"], t["subject"])
    code, p = t["exam_code"], t["subject"]
    year = int(code[:3])
    fail = lambda reason, msg: res.errors.append((reason, msg))
    if t.get("parked"):
        fail(t["parked"]["reason"], f"acquire parked：{t['parked']['detail']}")
        return res
    cur = t["current"]
    path = lambda k: ROOT / manifest.revision(t, cur[k])["raw_path"]

    # ---- 答案 ----
    ans = mod = None
    try:
        if cur["ANS"]:
            ans = apdf.parse(path("ANS"))
        if cur["MOD"]:
            mod = apdf.parse(path("MOD"))
    except apdf.AnswerParseError as e:
        fail(e.reason, str(e))
        return res
    if ans is None and mod is None:
        fail("answer_missing", "無 ANS 亦無 MOD")
        return res
    if jd.result == "present" and mod is None:
        fail("fetch_fail", "頁面有更正答案連結但 current.MOD 為 null")
        return res
    for e in validate.ac11_mod(ans, mod):
        fail("note_unparsed", e)

    # ---- 試題 ----
    doc = pdftext.load(path("Q"))
    res.has_small = any(c.small for pg in doc.pages for c in pg.l1_chars)
    l1_by_page = {pg.index: [c.text for c in pg.l1_chars] for pg in doc.pages}
    for e in crosscheck.page_mismatches(path("Q"), l1_by_page):
        fail("text_layer_loss", e)
    try:
        parsed = qparse.parse(doc)
    except qparse.ParseError as e:
        fail("parse_fail", str(e))
        return res
    for e in validate.ac7_attribution(parsed.unattributed):
        fail("parse_fail", e)
    for e in validate.ac1_numbers([q.no for q in parsed.questions], {k: d for k, d in (("ANS", ans), ("MOD", mod)) if d}):
        fail("parse_fail", e)
    if res.errors:
        res.intermediate = {"errors": res.errors}
        return res

    if mod is not None:
        status = "corrected"
    elif original_allowed(jd, exam_date):
        status = "original"
    else:
        status = "unverified"
    corrected = set(mod.corrections) if mod else set()
    n = len(parsed.questions)
    inter_q = []
    for q in parsed.questions:
        rid = f"{year}-{session}-PHARM-{p}-{q.no:03d}"
        acc, pol = validate.expected_answer(q.no, ans, mod)
        stem, stem_off = textnorm.apply_t(q.stem_l1.text, q.stem_l1.small)
        options, offsets = {}, {"stem": stem_off}
        for k in validate.KEYS:
            seg = q.options_l1.get(k, qparse.Segment("", []))
            options[k], offsets[k] = textnorm.apply_t(seg.text, seg.small)
        empty_keys = [k for k in validate.KEYS if not options[k] and q.option_graphics.get(k)]
        figs = []
        if q.graphics:
            for j, r in enumerate(q.region):
                fp = f"data/figures/{rid}_{j + 1}.png"
                figs.append(fp)
                res.figures.append((fp, r.page, (r.x0, r.top, r.x1, r.bottom)))
        rec = {
            "id": rid, "exam_code": code, "year_roc": year, "session": session,
            "profession": "pharmacist", "subject": p, "stage": subjects.stage_of(p),
            "question_no": q.no, "stem": stem, "options": options,
            "accepted_answers": acc, "answer_status": status, "score_policy": pol,
            "answer_raw_note": mod.corrections[q.no].clause if mod and q.no in mod.corrections else None,
            "has_figure": bool(q.graphics), "figure_refs": figs, "empty_option_keys": empty_keys,
            "flags": ["script_chars"] if any(offsets.values()) else [],
            "script_char_offsets": offsets,
            "source": {
                "subject_file_code": t["subject_file_code"], "category_code": t["category_code"],
                "question_rev": cur["Q"], "ans_rev": cur["ANS"], "mod_rev": cur["MOD"],
                "mod_page_rev": jd.page_rev if status == "original" else None,
            },
        }
        l1 = {"stem": (q.stem_l1.text, q.stem_l1.small), **{k: (q.options_l1.get(k, qparse.Segment("", [])).text, q.options_l1.get(k, qparse.Segment("", [])).small) for k in validate.KEYS}}
        opt_g = {k: len(v) for k, v in q.option_graphics.items()}
        errs = (validate.ac2_options(rec, list(q.options_l1), opt_g) + validate.ac3_shape(rec)
                + validate.ac7_text(rec, l1) + validate.ac14_values(rec, ans, mod))
        for e in errs:
            fail("parse_fail", e)
        res.records.append(rec)
        res.labels[rid] = _labels(q, doc, parsed, corrected, n)
        inter_q.append({"id": rid, "l1": {k: v[0] for k, v in l1.items()}, "labels": res.labels[rid],
                        "region": [[r.page, round(r.top, 2), round(r.bottom, 2)] for r in q.region],
                        "graphics": len(q.graphics)})
    res.intermediate = {
        "exam_code": code, "subject": p, "mod_judgement": {"result": jd.result, "reason": jd.reason},
        "answer_status": status, "removed_chars": parsed.removed,
        "removed_count": sum(r["count"] for r in parsed.removed),
        "attribution_counts": _count_labels(parsed.attribution),
        "questions": inter_q, "errors": res.errors,
    }
    return res


def _count_labels(attr: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for lab in attr.values():
        k = lab if not lab.startswith("q:") else "q:" + lab.split(":", 2)[2].split(":")[0]
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))
