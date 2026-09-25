"""正規化規則 T（spec §4.5）。純函式，逐字元 1→1 映射，保留位置以便追蹤 offset。"""

import unicodedata

_COMPAT_RANGES = ((0xF900, 0xFAFF), (0x2F00, 0x2FDF))


def is_compat(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _COMPAT_RANGES)


def compat_char(ch: str) -> str:
    if not is_compat(ch):
        return ch
    out = unicodedata.normalize("NFKC", ch)
    if len(out) != 1:
        raise ValueError(f"相容漢字 NFKC 非單一字元：U+{ord(ch):04X} → {out!r}")
    return out


def fullwidth_alnum_char(ch: str) -> str:
    cp = ord(ch)
    if 0xFF10 <= cp <= 0xFF19 or 0xFF21 <= cp <= 0xFF3A or 0xFF41 <= cp <= 0xFF5A:
        return chr(cp - 0xFEE0)
    return ch


def map_char(ch: str) -> str:
    """T 的逐字元部分（相容漢字 → 全形英數）。空白處理見 join_lines。"""
    return fullwidth_alnum_char(compat_char(ch))


def compat(s: str) -> str:
    return "".join(compat_char(c) for c in s)


def is_ascii_alnum(ch: str) -> bool:
    return ch.isascii() and ch.isalnum()


_SPACES = {" ", "　", "\t", " "}


def _keep_space(prev: str | None, nxt: str | None) -> bool:
    """中文間空白移除；英文詞間保留單一空白（兩側皆為非空白 ASCII 才保留）。"""
    return prev is not None and nxt is not None and prev.isascii() and nxt.isascii() and prev not in _SPACES | {"\n"} and nxt not in _SPACES | {"\n"}


def apply_t(text: str, flags: list[bool] | None = None) -> tuple[str, list[int]]:
    """T(L1) → L2。flags 為逐字 small 旗標；回傳 L2 與 small 字元之 L2 code point offset（升冪）。"""
    if flags is None:
        flags = [False] * len(text)
    if len(flags) != len(text):
        raise ValueError("flags 長度與文字不符")
    # 不可見控制字元（Cc，\n 除外）移除：實測 Word 殘留 U+0081 夾於題幹與①之間
    mapped = [(map_char(c) if c not in _SPACES else " ", f) for c, f in zip(text, flags) if c == "\n" or unicodedata.category(c) != "Cc"]
    out: list[tuple[str, bool]] = []
    i = 0
    while i < len(mapped):
        c, f = mapped[i]
        if c == " ":
            j = i
            while j < len(mapped) and mapped[j][0] == " ":
                j += 1
            prev = out[-1][0] if out else None
            nxt = mapped[j][0] if j < len(mapped) else None
            if _keep_space(prev, nxt):
                out.append((" ", False))
            i = j
            continue
        out.append((c, f))
        i += 1
    l2 = "".join(c for c, _ in out)
    return l2, [k for k, (_, f) in enumerate(out) if f]


def residue(s: str) -> list[str]:
    """回傳 L2 中 T 應已消除之殘留（AC-7）。"""
    bad = []
    for i, ch in enumerate(s):
        if is_compat(ch):
            bad.append(f"compat U+{ord(ch):04X} @{i}")
        elif fullwidth_alnum_char(ch) != ch:
            bad.append(f"fullwidth {ch!r} @{i}")
        elif ch in "　\t\r ":
            bad.append(f"whitespace U+{ord(ch):04X} @{i}")
        elif ch != "\n" and unicodedata.category(ch) == "Cc":
            bad.append(f"control U+{ord(ch):04X} @{i}")
    if "  " in s:
        bad.append("double space")
    if s != s.strip():
        bad.append("leading/trailing whitespace")
    return bad
