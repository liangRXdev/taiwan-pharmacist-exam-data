"""文字層交叉驗證（AC-16）：以 pdfium 為第二個獨立抽取器，偵測 pdfminer 靜默丟棄之字元。

實測：113020 P1 第 4 頁之圈號①–⑥（符號字型，PUA U+F00D–F012）pdfminer 完全不產生字元物件，
字元歸屬檢查因此無從發現。比對規則：逐頁、非空白、經相容漢字正規化、排除控制字元與連字號變體後，
任一方有而另一方完全沒有之字元 → 失敗。疊印使兩者計數不同，故只比「是否出現」。
"""

import collections
import unicodedata

import pypdfium2

from .. import textnorm

_IGNORE = {"￾", "-", "­"}   # pdfium 將軟連字號抽成 U+FFFE；pdfminer 為 '-'


def _norm_counter(chars) -> collections.Counter:
    out: collections.Counter = collections.Counter()
    for ch in chars:
        if ch.isspace() or ch in _IGNORE or unicodedata.category(ch) == "Cc":
            continue
        out[textnorm.compat_char(ch)] += 1
    return out


def page_mismatches(path, l1_by_page: dict[int, list[str]]) -> list[str]:
    doc = pypdfium2.PdfDocument(str(path))
    try:
        errs = []
        if len(doc) != len(l1_by_page):
            return [f"頁數不同：pdfium {len(doc)} vs pdfminer {len(l1_by_page)}"]
        for i in range(len(doc)):
            page = doc[i]
            tp = page.get_textpage()
            a = _norm_counter(tp.get_text_range())
            tp.close()
            page.close()
            b = _norm_counter(l1_by_page[i])
            only_a = sorted(ch for ch in a if b[ch] == 0)
            only_b = sorted(ch for ch in b if a[ch] == 0)
            if only_a or only_b:
                fmt = lambda xs: ",".join(f"U+{ord(c):04X}×{(a if xs is only_a else b)[c]}" for c in xs[:8])
                errs.append(f"第 {i + 1} 頁：pdfium 獨有 [{fmt(only_a)}]；pdfminer 獨有 [{fmt(only_b)}]")
        return errs
    finally:
        doc.close()
