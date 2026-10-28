"""命令列入口：`tped acquire` / `tped compile --release-date YYYY-MM-DD` / `tped oracle-check`。"""

import sys
import traceback

USAGE = "usage: tped {acquire|compile --release-date YYYY-MM-DD|oracle-check|review-init EXAM_CODE|review-backfill-digest EXAM_CODE|--all|review-serve}"
HELP = {"-h", "--help"}


def main() -> None:
    import logging
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    argv = sys.argv[1:]
    if argv[:1] and argv[0] in HELP:
        print(USAGE)
        sys.exit(0)
    if not argv or argv[0] not in {"acquire", "compile", "oracle-check", "review-init", "review-backfill-digest", "review-serve"}:
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    cmd, rest = argv[0], argv[1:]
    # acquire／oracle-check 不收參數、review-init 只收 EXAM_CODE：旗標（含 --help）不得被忽略後直接執行
    if (cmd in {"acquire", "oracle-check"} and rest) or (cmd == "review-init" and any(a.startswith("-") for a in rest)):
        is_help = len(rest) == 1 and rest[0] in HELP
        print(USAGE, file=sys.stdout if is_help else sys.stderr)
        sys.exit(0 if is_help else 2)
    try:
        if cmd == "acquire":
            from .acquire.run import main as run
        elif cmd == "compile":
            from .build.run import main as run
        elif cmd == "review-init":
            from .build.review import main as run
        elif cmd == "review-backfill-digest":
            from .build.review_backfill import main as run
        elif cmd == "review-serve":
            from .build.review_serve import main as run
        else:
            from .acquire.oracle import main as run
        code = run(rest)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    sys.exit(code)
