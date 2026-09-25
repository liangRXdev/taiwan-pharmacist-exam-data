"""compile：snapshot（raw/ + manifest.json + inputs/）+ release_date → data/、release/、intermediate/。

決定性：不讀網路、不讀系統時間、不讀前次產物（輸出目錄先清空）、只讀 current revisions。
"""

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import pdfplumber

from .. import jsonio, manifest
from ..config import INPUTS_EXAMS_PATH, ROOT
from . import assemble, derive, eligible, validate

FIGURE_DPI = 150
OUTPUT_DIRS = ("data", "release", "intermediate")


class CompileError(RuntimeError):
    pass


def _load_exam_inputs() -> dict[str, dict]:
    if not INPUTS_EXAMS_PATH.exists():
        return {}
    out = {}
    for e in jsonio.load(INPUTS_EXAMS_PATH):
        if e["exam_code"] in out:
            raise CompileError(f"inputs/exams.json 重複 {e['exam_code']}")
        date.fromisoformat(e["exam_date"])
        out[e["exam_code"]] = e
    return out


def _load_review(code: str) -> dict | None:
    f = ROOT / "review" / f"{code}.json"
    return jsonio.load(f) if f.exists() else None


def _review_verdict(review: dict | None, sample: list[str]) -> dict | None:
    """回傳供 eligible 判定之 {revs, result}；樣本不符或任一題非 pass → fail。"""
    if review is None:
        return None
    items = {it["id"]: it for it in review.get("items", [])}
    ok = (sorted(items) == sample and all(it.get("result") == "pass" and it.get("reviewer") for it in items.values())
          and bool(review.get("exam_date_source_quote")))
    return {"revs": review.get("revs"), "result": "pass" if ok else "fail"}


def _render_figures(res: assemble.TupleResult, q_path: Path, out: Path) -> None:
    if not res.figures:
        return
    with pdfplumber.open(q_path) as pdf:
        for rel, page, bbox in res.figures:
            pg = pdf.pages[page]
            x0, top, x1, bottom = bbox
            bottom = min(bottom, pg.height)
            img = pg.crop((x0, top, min(x1, pg.width), bottom)).to_image(resolution=FIGURE_DPI).original
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            img.save(dst, format="PNG", optimize=False)


def compile_all(release_date: date, out: Path = ROOT, render: bool = True) -> dict:
    m = manifest.load()
    manifest.normalize(m)
    errs = manifest.invariant_errors(m)
    if errs:
        raise CompileError("manifest 不變量失敗：" + "；".join(errs[:5]))
    for d in OUTPUT_DIRS:
        shutil.rmtree(out / d, ignore_errors=True)

    blocks = derive.universe(m, release_date)
    universe = derive.universe_keys(blocks)
    tuple_keys = {(t["exam_code"], t["subject"]) for t in m["tuples"]}
    exams_in = _load_exam_inputs()
    q_revs = [t["current"]["Q"] for t in m["tuples"]]
    dup_q = {r for r in q_revs if q_revs.count(r) > 1}

    states: dict[tuple, eligible.TupleState] = {}
    results: dict[tuple, assemble.TupleResult] = {}
    for key in sorted(universe):
        code, p = key
        t = manifest.tuple_of(m, code, p)
        if t is None:
            states[key] = eligible.TupleState(code, p, "fetch_fail", None, {})
            continue
        jd = derive.mod_judgement(m, t)
        revs = {"Q": t["current"]["Q"], "ANS": t["current"]["ANS"], "MOD": t["current"]["MOD"], "mod_page": jd.page_rev}
        id_errs = derive.identity_errors(t, derive.headers(m, t), blocks[code])
        if t["current"]["Q"] in dup_q:
            id_errs.append("current.Q 與他科相同")
        if id_errs:
            states[key] = eligible.TupleState(code, p, "identity_mismatch", None, revs)
            results[key] = assemble.TupleResult(code, p, errors=[("identity_mismatch", e) for e in id_errs])
            continue
        exam_date = date.fromisoformat(exams_in[code]["exam_date"]) if code in exams_in else None
        res = assemble.build(m, t, jd, exam_date, blocks[code].session)
        results[key] = res
        status = res.records[0]["answer_status"] if res.records else None
        states[key] = eligible.TupleState(code, p, res.parked_reason, status, revs)

    good = [r for k, res in results.items() if not res.errors for r in res.records]
    id_errs = validate.ac4_ids(good) + validate.ac9_current(good, m)
    if id_errs:
        raise CompileError("AC-4/AC-9：" + "；".join(id_errs[:5]))

    # ---- MG-1 與資格 ----
    coverage, release, mg1 = [], [], {}
    for code in sorted(blocks):
        keys = [k for k in sorted(universe) if k[0] == code]
        exam_revs = {k[1]: states[k].revs for k in keys}
        labels = {rid: labs for k in keys if k in results and not results[k].errors for rid, labs in results[k].labels.items()}
        seed = eligible.seed_of({k[1]: states[k].revs.get("Q") or "" for k in keys})
        sample = eligible.mg1_sample(labels, seed) if labels else []
        mg1[code] = {"exam_code": code, "seed": seed, "revs": exam_revs, "sample": sample,
                     "labels": {i: labels[i] for i in sample}, "not_applicable": eligible.mg1_not_applicable(labels)}
        verdict = _review_verdict(_load_review(code), sample)
        exam_date = date.fromisoformat(exams_in[code]["exam_date"]) if code in exams_in else None
        for k in keys:
            st = states[k]
            wh = [] if st.parked_reason else eligible.withheld_reasons(st, exam_date, release_date, verdict, exam_revs)
            rec = eligible.coverage_record(st, wh)
            coverage.append(rec)
            if rec["status"] == "released":
                release += results[k].records
    errs0 = validate.ac0_universe(universe, tuple_keys, [(c["exam_code"], c["subject"]) for c in coverage])

    # ---- 輸出 ----
    good.sort(key=lambda r: r["id"])
    release.sort(key=lambda r: r["id"])
    jsonio.dump(good, out / "data" / "questions.json")
    jsonio.dump([_exam_record(code, blocks[code], exams_in.get(code), results) for code in sorted(blocks)], out / "data" / "exams.json")
    jsonio.dump(release, out / "release" / "questions.json")
    jsonio.dump({"release_date": release_date.isoformat(), "tuples": coverage}, out / "release" / "coverage.json")
    for code, v in mg1.items():
        jsonio.dump(v, out / "intermediate" / "mg1" / f"{code}.json")
    for (code, p), res in sorted(results.items()):
        jsonio.dump(res.intermediate or {"errors": res.errors}, out / "intermediate" / f"{code}_{p}.json")
        if render and not res.errors:
            t = manifest.tuple_of(m, code, p)
            _render_figures(res, ROOT / manifest.revision(t, t["current"]["Q"])["raw_path"], out)
    return {"coverage": coverage, "ac0": errs0, "results": results, "release": release, "questions": good}


def _exam_record(code: str, blk, inp: dict | None, results: dict) -> dict:
    small = any(res.has_small for (c, _), res in results.items() if c == code)
    rec = {"exam_code": code, "exam_date": None, "exam_date_source_url": None, "exam_date_source_quote": None}
    if inp:
        rec.update({k: inp.get(k) for k in rec if k != "exam_code"})
    rec.update({"year_roc": blk.year_roc, "session": blk.session, "text_fidelity": {"scripts": "size_encoded" if small else "flattened"}})
    return rec


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="tped compile")
    ap.add_argument("--release-date", required=True, type=date.fromisoformat)
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = compile_all(a.release_date, render=not a.no_figures)
    except (CompileError, derive.DeriveError) as e:
        print(f"[compile] 失敗：{e}", file=sys.stderr)
        return 1
    by = {}
    for c in r["coverage"]:
        by.setdefault(c["status"], []).append(f"{c['exam_code']}/{c['subject']}:{','.join(c['reasons'])}")
    print(f"[compile] canonical {len(r['questions'])} 題；release {len(r['release'])} 題")
    for s, xs in sorted(by.items()):
        print(f"  {s} {len(xs)}：{' '.join(xs) if s != 'withheld' else ''}")
    if r["ac0"]:
        print("[compile] AC-0 失敗：" + "；".join(r["ac0"]), file=sys.stderr)
        return 1
    return 0
