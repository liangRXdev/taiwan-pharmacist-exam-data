"""P1–P6 科目對照（spec §4.3）。精確比對，不做模糊比對。"""

import re
from functools import lru_cache

from . import jsonio
from .config import SUBJECTS_PATH
from .textnorm import compat


def _key(name: str) -> str:
    return re.sub(r"\s+", "", compat(name))


@lru_cache(maxsize=1)
def _table() -> tuple[dict[str, str], dict[str, int]]:
    raw = jsonio.load(SUBJECTS_PATH)
    by_name: dict[str, str] = {}
    stage: dict[str, int] = {}
    for code, v in raw.items():
        stage[code] = v["stage"]
        for n in v["names"]:
            if _key(n) in by_name:
                raise ValueError(f"subjects.json 名稱重複：{n}")
            by_name[_key(n)] = code
    return by_name, stage


def subject_code(name: str) -> str | None:
    return _table()[0].get(_key(name))


def stage_of(code: str) -> int:
    return _table()[1][code]


CATEGORY_STAGE = {"藥師(一)": 1, "藥師(二)": 2}
