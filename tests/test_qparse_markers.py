"""選項標記切分（spec §4.5.1）：屬名縮寫（`B. subtilis`、`A. niger`）不得被當成選項標記。

合成 DocText：逐字等寬排版，空白為真實空白 glyph（不觸發 Word 假空白規則）。
反例皆為「切錯但 unattributed 0、AC-2/AC-7 全過」之靜默錯誤，修正前 parse 會產生錯誤分段。
"""

import pytest

from tped.build import pdftext, qparse

ADV = 10.0          # 每字寬度
BODY = 10.0
QNO_X = 50.0        # 題號行左邊界
OPT_X = 70.0        # 懸掛縮排


def _line(page: int, top: float, x0: float, text: str) -> pdftext.Line:
    chars = [pdftext.Ch(c, x0 + i * ADV, x0 + (i + 1) * ADV, top, top + BODY, BODY, page, False) for i, c in enumerate(text)]
    return pdftext.Line(page, chars).finalize()


def _doc(rows: list[tuple[float, str]]) -> pdftext.DocText:
    lines = [_line(0, 100 + i * 20, x0, text) for i, (x0, text) in enumerate(rows)]
    l1 = [c for ln in lines for c in ln.chars if c.text.strip()]
    return pdftext.DocText([pdftext.PageData(0, 600, 1000, lines, l1, [], [])], BODY)


def _texts(parsed: qparse.ParsedDoc) -> dict[str, str]:
    return {k: s.text for k, s in parsed.questions[0].options_l1.items()}


def test_clean_fixture_parses():
    parsed = qparse.parse(_doc([(QNO_X, "1.何者正確？"), (OPT_X, "A.甲"), (OPT_X, "B.乙"), (OPT_X, "C.丙"), (OPT_X, "D.丁")]))
    assert _texts(parsed) == {"A": "甲", "B": "乙", "C": "丙", "D": "丁"}
    assert parsed.unattributed == []


def test_inline_genus_abbrev_not_split():
    """反例 (c)：選項 A 內文「以 B. subtilis 為指標」。修正前 A='以'、B='subtilis 為指標\\nB.乙'，AC-2 全過。"""
    parsed = qparse.parse(_doc([
        (QNO_X, "1.滅菌確效何者正確？"),
        (OPT_X, "A.以 B. subtilis 為指標"),
        (OPT_X, "B.乙"), (OPT_X, "C.丙"), (OPT_X, "D.丁"),
    ]))
    assert _texts(parsed) == {"A": "以 B. subtilis 為指標", "B": "乙", "C": "丙", "D": "丁"}
    assert parsed.unattributed == []


def test_inline_real_markers_still_split():
    """同行多選項（無空白緊接小寫為真實標記之常態：語料 3,749/3,749）仍須切分。"""
    parsed = qparse.parse(_doc([(QNO_X, "1.何者為 NSAID？"), (OPT_X, "A.aspirin B.ibuprofen"), (OPT_X, "C.丙 D.丁")]))
    assert _texts(parsed) == {"A": "aspirin", "B": "ibuprofen", "C": "丙", "D": "丁"}


@pytest.mark.parametrize("rows", [
    # 反例 (a)：選項 A 換行後續行以「B. subtilis」開頭（K.＋空白＋小寫不是標記）→ 真 B 行成為以 B. 開頭之續行
    [(QNO_X, "1.滅菌確效指標菌為何？"), (OPT_X, "A.以下列何者為指標：嗜熱菌"), (OPT_X, "B. subtilis"),
     (OPT_X, "B.乙"), (OPT_X, "C.丙"), (OPT_X, "D.丁")],
    # 反例 (a)：題幹續行以「A.niger」開頭（排版無空白，形同真實標記）→ 被當成選項 A，真 A 行成為以 A. 開頭之續行
    [(QNO_X, "1.下列何種黴菌常用於檸檬酸發酵？即"), (OPT_X, "A.niger 之菌株"),
     (OPT_X, "A.甲"), (OPT_X, "B.乙"), (OPT_X, "C.丙"), (OPT_X, "D.丁")],
])
def test_continuation_starting_with_option_marker_is_parse_fail(rows):
    with pytest.raises(qparse.ParseError, match="續行"):
        qparse.parse(_doc(rows))
