# Changelog

## [Unreleased]

### Added
- release 2026-10-28：新增 115 年第二次（115090）六科 450 題（corrected 320／original 130），MG-1 20 題人工抽樣通過；合計 6 場 35 科 2,620 題

### Fixed
- 選項標記誤切：`K.` + 空白 + 小寫（屬名縮寫 `B. subtilis`）不再視為選項標記；續行以 `[A-D].` 開頭改判 `parse_fail`（spec v0.10 §4.5.1）
- MG-1 審查綁定 L2：review-init 逐題寫入 `l2_digest`，compile 重算不符 → `mg1_stale`；review 之 `exam_date`／`exam_date_source_url` 與 `inputs/exams.json` 不符 → `mg1_stale`；items id 重複 → `mg1_stale`；審查者僅空白 → `mg1_pending`（spec v0.10 §5.4、§6.2）
- acquire 年度頁非 200 中止；年度頁 `ddlExamCode` 選單與表格區塊 code 集合交叉驗證（acquire 與 compile 共用）（spec v0.10 §4.6）
- acquire 科目頁非 200 不再中止整次 run：存證、更新 `mod_page_rev`、記 problems（spec v0.10 §5.2）
- acquire 期 parked 一律重抓；`requests.RequestException` 歸 retryable；PDF 開檔例外歸 unusable；review-serve 原子存檔；review-init 驗證 EXAM_CODE
- acquire 科目頁 digest 只涵蓋該場藥師科目列：年度考試下拉選單新增他場考試、同場他類科更正不再換 rev（避免 MG-1 全數 `mg1_stale`）；比對加入 `final_url`；舊頁 digest 由 raw 重算（spec v0.7）
- `tped acquire --help` 等未知參數不再被忽略後直接連線執行；`tped --help` 印出用法
- acquire 科目頁去重比對 `content_digest` 前綴不一致，同內容重抓（僅 VIEWSTATE 不同）仍新增 revision，致全部 MG-1 審查判 `mg1_stale`

### Changed
- `spec.md` v0.8：GitHub Actions 排程暫緩（D14），§8 改為手動執行方式（考後 90 天發布、180 天複查）
- 115090、115020 之 MG-1 審查紀錄 `revs.mod_page` 更新為 2026-10-28 科目頁；Q/ANS/MOD、抽樣集合與標籤皆不變，人工判定沿用（115020 頁面變動僅為年度下拉選單新增非藥師考試）

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
