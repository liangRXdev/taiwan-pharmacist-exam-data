# Changelog

## [Unreleased]

### Added
- M1 acquire：6 場 36 科 Q/ANS/MOD 與頁面證據（raw/、manifest.json）；H1 解決（`t=M`）
- M2 compile：canonical 2,620 題（data/）、coverage 與 release（release/）、203 張整題裁切圖
- AC-0 ~ AC-16 測試與反例 fixture；AC-16 文字層交叉驗證（pdfium）
- `inputs/exams.json`：6 場考試日期與考選部來源
- `tped review-init`：MG-1 人工抽樣範本

### Fixed（實作中發現之靜默錯誤）
- Word 版 PDF 清單標記後之重疊假空白（`a spirin` → `aspirin`）
- 115 年下標被切成獨立行而移至行尾（`β receptor … 2` → `β2 receptor`）
- 題幹以數字開頭之題目（`14.25℃`）被誤判非題號
- 控制字元 U+0081 殘留

### Changed
- `spec.md` v0.4：依第二輪覆審（22 項：接受 21／部分接受 1／拒絕 0）修訂，acquire 只存 HTML/PDF 證據、universe 與 MOD 判定由 compile 重算、`inputs/` 分離、字元歸屬契約、AC-14 答案值、AC-15 M0 回歸下限、MG-1 決定性演算法
- `spec.md` v0.3：依 `/codex-checkplan` 第一輪覆審（41 項：接受 35／部分接受 6／拒絕 0）修訂，acquire／compile 分離、manifest 與 MOD observation schema、刪除逐題 `verified`、AC-0 完整性與反例 fixture

### Added
- `spec.md` v0.2：M0 探針結果、決策 D1–D7、AC-11/AC-12
- `subjects.json`：P1–P6 跨年度科目對照
- 專案初始化：README、CLAUDE.md、.gitignore
