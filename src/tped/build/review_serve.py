"""MG-1 本機審查頁：`tped review-serve [--port 8765]`。

只監聽 127.0.0.1；只讀 data/、intermediate/、raw/，只寫 review/{code}.json 之
items[].result/reviewer/note 與 exam_date_source_quote（revs、題目集合不可改）。
需先執行 `tped compile` 與 `tped review-init`。
"""

import argparse
import io
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pdfplumber

from .. import jsonio, manifest
from ..config import ROOT

QUESTION_DPI = 200
ANSWER_DPI = 110
_CODE = re.compile(r"^\d{6}$")
_QID = re.compile(r"^(\d{3})-(\d)-PHARM-(P[1-6])-(\d{3})$")
PAGE = Path(__file__).with_name("review_page.html")


class Store:
    def __init__(self):
        self.m = manifest.load()
        self.questions = {r["id"]: r for r in jsonio.load(ROOT / "data" / "questions.json")}
        self.lock = threading.Lock()
        self.cache: dict[tuple, bytes] = {}

    def review_path(self, code: str) -> Path:
        return ROOT / "review" / f"{code}.json"

    def exams(self) -> list[dict]:
        out = []
        for f in sorted((ROOT / "review").glob("*.json")):
            r = jsonio.load(f)
            done = sum(1 for it in r["items"] if it.get("result") in ("pass", "fail"))
            fails = sum(1 for it in r["items"] if it.get("result") == "fail")
            out.append({"exam_code": r["exam_code"], "total": len(r["items"]), "done": done, "fails": fails,
                        "quote": bool(r.get("exam_date_source_quote"))})
        return out

    def exam(self, code: str) -> dict:
        r = jsonio.load(self.review_path(code))
        items = []
        for it in r["items"]:
            q = self.questions[it["id"]]
            inter = jsonio.load(ROOT / "intermediate" / f"{q['exam_code']}_{q['subject']}.json")
            qi = next(x for x in inter["questions"] if x["id"] == it["id"])
            items.append({**it, "question": q, "regions": len(qi["region"])})
        return {**r, "items": items}

    def _tuple(self, code: str, subject: str) -> dict:
        t = manifest.tuple_of(self.m, code, subject)
        if t is None:
            raise KeyError(f"{code}/{subject}")
        return t

    def question_png(self, qid: str, j: int) -> bytes:
        key = ("q", qid, j)
        if key not in self.cache:
            q = self.questions[qid]
            inter = jsonio.load(ROOT / "intermediate" / f"{q['exam_code']}_{q['subject']}.json")
            page, top, bottom = next(x for x in inter["questions"] if x["id"] == qid)["region"][j]
            t = self._tuple(q["exam_code"], q["subject"])
            with pdfplumber.open(ROOT / manifest.revision(t, t["current"]["Q"])["raw_path"]) as pdf:
                pg = pdf.pages[page]
                img = pg.crop((0, top, pg.width, min(bottom, pg.height))).to_image(resolution=QUESTION_DPI).original
            self.cache[key] = _png(img)
        return self.cache[key]

    def answer_png(self, code: str, subject: str, kind: str) -> bytes:
        key = ("a", code, subject, kind)
        if key not in self.cache:
            t = self._tuple(code, subject)
            rev = t["current"][kind]
            if rev is None:
                raise KeyError(kind)
            with pdfplumber.open(ROOT / manifest.revision(t, rev)["raw_path"]) as pdf:
                img = pdf.pages[0].to_image(resolution=ANSWER_DPI).original
            self.cache[key] = _png(img)
        return self.cache[key]

    def save(self, code: str, body: dict) -> dict:
        with self.lock:
            path = self.review_path(code)
            r = jsonio.load(path)
            incoming = {it["id"]: it for it in body.get("items", [])}
            if set(incoming) - {it["id"] for it in r["items"]}:
                raise ValueError("含範本以外之題目 id")
            for it in r["items"]:
                new = incoming.get(it["id"])
                if new is None:
                    continue
                if new.get("result") not in (None, "pass", "fail"):
                    raise ValueError(f"result 不合法：{new.get('result')!r}")
                it["result"] = new.get("result")
                it["reviewer"] = str(new.get("reviewer") or "")[:40]
                it["note"] = str(new.get("note") or "")[:2000]
            if "exam_date_source_quote" in body:
                r["exam_date_source_quote"] = str(body["exam_date_source_quote"] or "")[:500]
            jsonio.dump(r, path)
            return {"ok": True}


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_handler(store: Store, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _guard(self) -> bool:
            if self.headers.get("Host") not in allowed_hosts:
                self._send(403, b"forbidden", "text/plain")
                return False
            return True

        def do_GET(self):
            if not self._guard():
                return
            p = self.path.split("?", 1)[0].strip("/").split("/")
            try:
                if p == [""]:
                    self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
                elif p == ["api", "exams"]:
                    self._json(store.exams())
                elif len(p) == 3 and p[:2] == ["api", "exam"] and _CODE.match(p[2]):
                    self._json(store.exam(p[2]))
                elif len(p) == 4 and p[:2] == ["img", "q"] and _QID.match(p[2]) and p[3].isdigit():
                    self._send(200, store.question_png(p[2], int(p[3])), "image/png")
                elif len(p) == 5 and p[:2] == ["img", "a"] and _CODE.match(p[2]) and re.fullmatch(r"P[1-6]", p[3]) and p[4] in ("ANS", "MOD"):
                    self._send(200, store.answer_png(p[2], p[3], p[4]), "image/png")
                else:
                    self._send(404, b"not found", "text/plain")
            except (KeyError, FileNotFoundError, StopIteration, IndexError) as e:
                self._json({"error": f"找不到資料：{e}"}, 404)

        def do_POST(self):
            if not self._guard():
                return
            p = self.path.strip("/").split("/")
            if not (len(p) == 3 and p[:2] == ["api", "exam"] and _CODE.match(p[2])):
                self._send(404, b"not found", "text/plain")
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self._json({"error": "Content-Type 必須為 application/json"}, 415)
                return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n > 1_000_000:
                    raise ValueError("內容過大")
                self._json(store.save(p[2], json.loads(self.rfile.read(n).decode("utf-8"))))
            except (ValueError, KeyError, FileNotFoundError) as e:
                self._json({"error": str(e)}, 400)
            except OSError as e:
                self._json({"error": f"寫檔失敗：{e}"}, 500)

    return H


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="tped review-serve")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    if not (ROOT / "data" / "questions.json").exists() or not list((ROOT / "review").glob("*.json")):
        print("請先執行 tped compile 與 tped review-init", file=sys.stderr)
        return 1
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(Store(), a.port))
    print(f"[review] http://127.0.0.1:{a.port}/  （Ctrl+C 結束）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
