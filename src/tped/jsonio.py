"""決定性 JSON 讀寫：UTF-8、ensure_ascii=False、縮排 2、LF、結尾換行。"""

import json
from pathlib import Path
from typing import Any


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps(obj).encode("utf-8"))


def load(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))
