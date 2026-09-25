# CLAUDE.md

規格：`spec.md`（決策紀錄在 §11，改動前先讀）。

## 硬性規則

- 禁止 LLM 參與抽取或補救；解析失敗 → 標 `parked`
- 禁止改寫題幹/選項；正規化只做 spec §4.5 列出的規則
- 禁止猜測式枚舉 `exam_code`（無效 code 會 redirect 回上一個有效 code，不回 404）
- 所有 `except` 區塊 `sys.exit(1)`
- Python 一律 `uv run` / `uv add`

## 不可從程式碼推斷的事實

- ANS = 初版答案、MOD = 更正版；兩者可並存，MOD 僅 `＃` 題不同。更正內容在 MOD「備註」自由文字
- 官方檔名科目碼與試題代號跨年變動（113-2 同場有兩個 `11`；調劑試題代號 4306→1306），科目身分以 PDF 表頭名稱對應 `subjects.json`
- 部分 PDF 以同位置疊印做假粗體（113020 P1 題幹內也有），抽取必須先 `page.dedupe_chars()`，否則 `C-14` 變 `C-1144` 且結構性檢查全過
- PDF 文字層含 CJK 相容漢字（U+F900–FAFF），只對該區段做 NFKC，不可全量 NFKC
- 站方有 session 狀態：曾因此下載到重複考試，下載後必須比對 PDF 表頭考試名稱
- 下載檔名會被截斷（`藥物分析與生藥學(含.pdf`），不可依檔名判斷科目
- 站方會原址替換 PDF（含 MOD 二次更正），oracle/manual 可能是舊版
- PDF 空白 glyph 不可信：Word 版在清單標記後放重疊假空白；斜體學名之真空白視覺間距 ≈ 0（規則見 spec §4.5.1，改動前先跑 test_space_rule_real）
- pdfminer 會靜默丟棄某些符號字型字元，只有 AC-16（pdfium 交叉比對）抓得到
- 不要用 `extract_text_lines` 切行：115 年下標會被拆成獨立行

## 架構邊界

- acquire（線上）與 compile（離線）分離；compile 禁止讀網路、系統時間、前次產物，`release_date` 必須顯式傳入
- `raw/` 不可變、內容定址；禁止覆寫，新 hash 一律 append revision
- acquire 只存證據（HTML/PDF）；universe、MOD 有無、表頭身分一律由 compile 重算，manifest 不存判定結果
- `inputs/` 是人工輸入，compile 不得寫入
- 每條 AC 必須附反例 fixture；只驗正例的測試不算數

## 目錄

- `raw/`：crawler 產物，進版控
- `oracle/manual/`：手動下載檔，gitignore，只作 M1 SHA256 比對基準
- `.ai-review/`：規格覆審紀錄（plan-review 原文、plan-verdict 判定）
