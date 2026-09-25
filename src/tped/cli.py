"""命令列入口：`tped acquire` / `tped compile --release-date YYYY-MM-DD` / `tped oracle-check`。"""

import sys
import traceback


def main() -> None:
    import logging
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    argv = sys.argv[1:]
    if not argv or argv[0] not in {"acquire", "compile", "oracle-check"}:
        print("usage: tped {acquire|compile --release-date YYYY-MM-DD|oracle-check}", file=sys.stderr)
        sys.exit(2)
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "acquire":
            from .acquire.run import main as run
        elif cmd == "compile":
            from .build.run import main as run
        else:
            from .acquire.oracle import main as run
        code = run(rest)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    sys.exit(code)
