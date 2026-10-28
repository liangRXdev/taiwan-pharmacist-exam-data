"""決定性 JSON 讀寫：UTF-8、ensure_ascii=False、縮排 2、LF、結尾換行。"""

import json
import os
from pathlib import Path
from typing import Any


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps(obj).encode("utf-8"))


def dump_atomic(obj: Any, path: Path) -> None:
    """先寫同目錄暫存檔再 os.replace：寫入中途失敗不得留下截斷檔（人工證據檔用）。"""
    tmp = path.with_name(path.name + ".tmp")
    try:
        dump(obj, tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))
