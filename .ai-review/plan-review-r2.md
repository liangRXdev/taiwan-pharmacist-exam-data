<!--
審查日期：2026-09-25（第二輪）
Codex 版本：codex-cli 0.153.4（mcp__codex__codex，sandbox read-only，approval never）
thread：01a0d755-7408-7962-8f43-e65007b769e2
規劃文件：spec.md v0.3（工作區未 commit 版本，base commit 8abbf34；修訂時間 2026-09-25）
備註：Codex 自行讀取 cwd 下 spec.md 與第一輪 .ai-review/ 紀錄
以下為 Codex 原始輸出，未修飾、未刪改。
-->

# 第二輪規格覆審報告

覆審對象：`spec.md` v0.3 工作區版本。  
覆審範圍：聚焦 v0.3 新增架構，並檢查第一輪接受項目是否真正封堵弱化實作。  
本次為唯讀審查，未修改任何檔案。

## 1. 需求與邊界缺漏

### 1.1 High — universe 仍是由結果反推，未成為可稽核的 discovery 輸入

- **嚴重度：High**
- **問題：** manifest schema 只有 `tuples`，沒有獨立的 discovery 結果、目標考試清冊或 discovery 頁面 revision。AC-0 的「每個已 discover 之 exam_code」因此只能從同一份 `tuples` 推導。刪掉整個考試的六科後，剩餘考試仍各有 P1–P6、manifest 仍非空，AC-0 可以通過。這是第一輪 R1-1/R3-C2 的弱化修正，而非真正建立 inventory 母集合。[spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:211) [spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:352)
- **為什麼現在不修之後會更貴：** M1 一旦以 `tuples` 同時代表「發現結果」與「抓取結果」，日後補 discovery provenance 會改 manifest schema、AC-0、coverage 及歷史資料。
- **建議修法：** 將「站方 discovery 得到的 exam_code 集合」規格化為獨立、可重建且有來源證據的 inventory；`tuples` 必須對該 inventory 做完整映射。反例至少增加「刪除某場全部六科」，而不只是刪除一科。這是 G6 的驗收化，不是新增需求。

### 1.2 High — `exams.json` 同時被描述為 compile 輸入與 compile 輸出

- **嚴重度：High**
- **問題：** G4 把 `exams.json` 列為 snapshot 輸入；§4.2 又稱 `data/exams.json` 為「人工維護 + compile 補欄」；目錄結構只列出 `data/exams.json`，而 `data/` 又是 compile 產物。AC-5 第二次會刪除全部產物，可能連人工輸入一起刪掉。[spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:43) [spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:164) [spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:390)
- **為什麼現在不修之後會更貴：** 這會直接影響 clean build、90 天資格、acquire 的 180 天選取及 repository layout；實作後再拆會搬移資料及修改所有命令與測試。
- **建議修法：** 明確分離人工維護的考試 metadata 輸入與 compile 生成的公開投影；規定哪一份屬 snapshot、哪一份可刪除重建，以及兩者欄位投影關係。

### 1.3 High — `parked` 沒有生命週期，第一輪要求的唯一 scope 未落實

- **嚴重度：High**
- **問題：** `parked` 只規定排序與 reason code，未定義同一 scope 能否有多筆、哪筆是 active、成功重跑後是刪除、取代還是標記 resolved。release 條件只寫「未 parked」，因此歷史失敗可能永久阻擋，或實作者直接刪除紀錄而失去稽核軌跡。[spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:244) [spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:325)
- **為什麼現在不修之後會更貴：** 第一次格式漂移後就必須臨時決定狀態遷移；會同時改 manifest、coverage 與 release eligibility。
- **建議修法：** 二選一並寫成契約：只保存每個 scope 的當前 parked 狀態、歷史交由 Git；或保留事件歷史但明定 active/resolved 與唯一當前狀態。不得讓「陣列中曾出現過」等同永久 parked。

### 1.4 Medium — negative observation 沒有時序／取代規則

- **嚴重度：Medium**
- **問題：** 目前只要求存在「一筆」有效 `absent`。若較早為 `absent`、較晚為 `inconclusive`，舊觀測仍可讓答案維持 `original`；規格也未要求 qualifying observation 位於 90 天發布閘門附近。[spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:250) [spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:327)
- **為什麼現在不修之後會更貴：** 發布後才定義「最新、最晚成功或特定期間內」會改變既有 release 結果與重建語意。
- **建議修法：** 定義每個 tuple 的 authoritative observation 選擇規則、較晚 `present`／`inconclusive` 對舊 `absent` 的影響，以及 release 所需的觀測時間窗口。這是既有「未確認即 unverified」政策的精確化。

### 1.5 Medium — `coverage.json` 只有字串範例，沒有完整 schema 與理由優先序

- **嚴重度：Medium**
- **問題：** 同一科可能同時是 `too_recent`、`unverified`、缺 MG-1 或 AC 失敗；規格只允許單一 `withheld:{reason}`，未定義優先序、是否可多原因、所依 release date/revision。[spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:266)
- **為什麼現在不修之後會更貴：** coverage 一旦被下游使用，再從字串改成結構或改變 reason 選擇會成為 schema 破壞。
- **建議修法：** 在動工前固定 coverage record 的欄位、reason 集合、優先序或多原因語意，並綁定本次 compile 的 `release_date` 與來源 revision。

## 2. 架構風險

### 2.1 High — negative MOD evidence 實際上不可重驗

- **嚴重度：High**
- **問題：** observation 只保存 `page_sha256` 與可任意填入的 `positive_control: true`，卻沒有保存對應 HTML snapshot、URL、解析規則版本或可重算的結構證據。頁面日後改變後，無法證明當時確實沒有 MOD 連結。Q 連結存在也只能證明頁面部分可解析，不能證明 MOD selector 正常。[spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:231)
- **為什麼現在不修之後會更貴：** 這些 observation 一旦將題目升為 `original` 並發布，事後無法補回當時的負向證據；這正是新 schema 原本要解決的 provenance 問題。
- **建議修法：** qualifying negative evidence 必須指向不可變、可重新套用 H1 判定規則的頁面證據，或保存足以完整重算判定的結構化證據；單獨的 hash 與布林值不得構成有效 observation。

### 2.2 High — compile 允許使用非 `current` revision，revision 更新可能未進入輸出

- **嚴重度：High**
- **問題：** AC-9 只要求 `*_rev` 能在 manifest 找到且身分相符，沒有要求 canonical source 等於該 tuple 的 `current`。官方出現新 Q、ANS 或 MOD revision 後，compile 仍可輸出舊 revision；若 MG-1 另行綁到 current，兩者甚至可彼此不一致。
- **為什麼現在不修之後會更貴：** revision 歷史累積後，無法判斷「刻意重建舊版本」或「漏用最新來源」；release 可能在 provenance 全合法的外觀下發布過時答案。
- **建議修法：** 定義正常 compile 必須以每個 tuple 的 `current` Q/ANS/MOD 為唯一來源；若需要歷史重建，應由明確的歷史 snapshot 決定，而不是任意挑 manifest 中任一 revision。MG-1 應綁定實際進入 canonical 的 revision 集合。

### 2.3 Medium — `current` 本身缺少完整性不變量

- **嚴重度：Medium**
- **問題：** 未規定每個非 null current 值必須在同 tuple 的 revisions 中恰找到一個同 kind revision，也未規定 Q 必填、revision 重複及 fetched_at 同時的排序方式。
- **為什麼現在不修之後會更貴：** manifest 累積後才補限制，可能需要清理既有重複、懸空或跨 kind pointer。
- **建議修法：** 把 current-to-revision 的參照完整性、唯一性、必填性及穩定排序列入 manifest schema 與驗收。

### 2.4 Medium — G4 未封閉 build environment

- **嚴重度：Medium**
- **問題：** 「相同 commit」不等於相同 PDF renderer、字型、平台與壓縮器環境。AC-5 在同一 runner 連跑兩次可以通過，但另一乾淨 runner 產出的 PNG 或 `.apkg` bytes 仍可能不同。[spec.md](C:/Users/liang/projects/taiwan-pharmacist-exam-data/spec.md:357)
- **為什麼現在不修之後會更貴：** M3 才發現跨環境不一致時，會被迫重新界定 G4 或重做既有 release hash。
- **建議修法：** 規格需明定 byte-identical 的環境邊界：是同一鎖定工具鏈，還是跨支援平台。AC-5 必須驗證所宣稱的那個範圍。

## 3. 驗證策略缺口：仍可通過但功能壞掉的弱化實作

以下只列 v0.3 後仍答得出來者。

### 3.1 AC-0

- **嚴重度：High**
- **問題：** 完全漏掉某一場考試的六個 tuple；剩餘 manifest 非空且每場仍有 P1–P6，AC-0 通過。
- **為什麼現在不修之後會更貴：** 需回頭新增 discovery inventory 及遷移 manifest，並重算所有 coverage。
- **建議修法：** AC-0 的母集合必須來自獨立 discovery evidence；新增「刪除整場」及「漏掉最新一場」反例。

### 3.2 AC-3／AC-11

- **嚴重度：Medium**
- **問題：** 對所有 ANS-only 題把 canonical 答案固定成 `A`，仍可符合 AC-3 的形狀；AC-11 也未明文要求每題 canonical `accepted_answers` 等於 ANS/MOD 表中的實際答案。對 MOD-only 的非 `＃` 題同樣可能完整解析來源表，卻把錯值寫入 canonical。
- **為什麼現在不修之後會更貴：** 這會直接發布錯誤答案；但修正主要是驗證邏輯，不需改架構。
- **建議修法：** 增加逐題來源到 canonical 的值相等斷言：ANS-only 取 ANS；MOD 存在時取 MOD；`＃` 題依完全解析的備註展開。反例應改一題答案值但保留所有形狀、題數與 provenance。

### 3.3 AC-5

- **嚴重度：Medium**
- **問題：** 在同一 runner 連跑兩次穩定，但 renderer 或環境改變即產生不同 PNG／Anki bytes，仍可通過現有 AC-5。
- **為什麼現在不修之後會更貴：** 發布後才縮小 G4 承諾會使既有 hash 與 reproducibility 宣稱失真。
- **建議修法：** 讓 AC-5 的執行範圍與 G4 明定的工具鏈／平台範圍完全一致。

### 3.4 AC-6

- **嚴重度：Medium**
- **問題：** 產生 release 與測試都呼叫同一個錯誤 eligibility 判定，例如共同忽略 MG-1；集合仍完全相等。現有反例只證明手動增刪輸出會被抓到，沒有證明資格 predicate 正確。
- **為什麼現在不修之後會更貴：** eligibility 成為單一錯誤來源，所有 release 都會一致地錯。
- **建議修法：** 反例應逐項翻轉 §5.4 的每個必要條件，並以明確預期集合驗證，不得只比較同一判定器的兩次結果。

### 3.5 AC-7

- **嚴重度：High**
- **問題：** 在形成 L1 時就截掉一段文字，再令 L2=`T(L1)`；T 冪等、無殘留、stem 非空全部成立。現有「L2 被截斷」fixture 若只改 L2，抓不到發生在 L0→L1 或題目分段階段的截斷。
- **為什麼現在不修之後會更貴：** L1 一旦被視為可信基準，所有後續 AC 都只能一致地驗證錯誤文字；若要補可追溯性會改 intermediate 契約。
- **建議修法：** 為 L0→L1→題目分段加入字元歸屬／排除的可核對契約；反例須同時截斷 L1 與 L2，而原始 page chars 不變。這不是重新測試 `dedupe_chars()` 的內部幾何，而是驗證管線沒有遺失未被規則允許排除的文字。

### 3.6 AC-8

- **嚴重度：Medium**
- **問題：** 填入錯誤 `exam_date`，再附一個格式合法但未支持該日期的考選部 URL，仍可通過自動 AC，導致提前發布。
- **為什麼現在不修之後會更貴：** release date 計算結果會進入歷史版本，事後更正日期將大幅改變 coverage。
- **建議修法：** 不要求自動擷取日期；將「人工核對 URL 內容確實支持該日期」列為明確的 PR manual gate 與證據欄位，而不只是 URL 非 null。這與 N10 相容。

### 3.7 AC-9

- **嚴重度：Medium**
- **問題：** canonical 指向同 tuple、同 kind、hash 正確但已非 current 的舊 revision，AC-9 仍通過。
- **為什麼現在不修之後會更貴：** revision 數量增加後才補會使既有輸出大量改版。
- **建議修法：** 加入 canonical source 必須等於 snapshot current 的斷言，並提供「新增 current、canonical 仍指舊 revision」反例。

### 3.8 MG-1

- **嚴重度：Medium**
- **問題：** seed 已定義，但分層配額、跨層重疊、候選排序、超過 20 題時如何取捨均未定義，無法唯一重算樣本。另一弱化方式是把 `has_figure`、`script_chars` 等風險旗標全部漏標，再把該層記為「不適用」，只審各科首末題。
- **為什麼現在不修之後會更貴：** review 證據產生後若抽樣演算法再定案，既有 MG-1 全部可能失效；單人需重審多場。
- **建議修法：** 固定候選集合、各層最低覆蓋、跨層重疊規則、排序及補足至 20 題的方式。對 M0 五場，風險層成員應由既有人工 oracle 固定；「不適用」不可只依被審 parser 自己產生的空旗標。

## 4. 更簡單的替代方案

### 4.1 Low — acquire／compile 分離不是 over-engineering，不應刪

- **嚴重度：Low**
- **問題：** 無；這是解決 G4 矛盾的必要責任邊界。
- **為什麼現在不修之後會更貴：** 若重新合併，時間觀測與 deterministic build 的矛盾會復發。
- **建議修法：** 保留兩階段，只需修正 `exams`、review evidence 與工具鏈哪些屬 compile 輸入。

### 4.2 Medium — `mod_observations[]` 不必保存所有重複狀態

- **嚴重度：Medium**
- **問題：** 每月相同 `absent` 都 append，且「有新 observation 就開 PR」，在 180 天內會產生多筆幾乎相同資料與多次人工 PR。
- **為什麼現在不修之後會更貴：** 歷史累積後才壓縮會牽涉 observation ID 與 canonical 引用。
- **建議修法：** 可只保存每 tuple 的當前 authoritative negative evidence；歷史由 Git commit 保留。`present` 已由 MOD revision 證明，不需再保存一份平行 observation；`inconclusive` 可作當前 operational 狀態而非永久 append log。前提是保留可重驗的頁面證據。

### 4.3 Medium — parked 可改成「當前狀態」，不需要自建事件史

- **嚴重度：Medium**
- **問題：** 現行陣列看似要保留歷史，卻沒有 lifecycle，複雜度大於實際需求。
- **為什麼現在不修之後會更貴：** 一旦形成多筆同 scope 資料，所有 consumer 都要自行推斷 active record。
- **建議修法：** 每個 tuple 最多一個當前 parked record；成功後移除，歷史交由 Git。這不降低「目前缺漏必須可見」的保護。

### 4.4 Low — coverage 與 compile 時計算 release 資格應保留

- **嚴重度：Low**
- **問題：** 無；兩者分別防止靜默缺科與漂移布林值。
- **為什麼現在不修之後會更貴：** 刪除 coverage 會重現「空 release 也看似成功」；恢復 `verified` 則重現狀態漂移。
- **建議修法：** 不刪機制，只將 coverage schema 與單一 eligibility 契約固定，避免不同輸出各自實作理由判定。

### 4.5 Medium — MG-1 分層概念保留，但抽樣模型可縮成單一 coverage-set 演算法

- **嚴重度：Medium**
- **問題：** 現行文字像多個獨立 strata，但總上限 20，容易產生配額與重疊歧義。
- **為什麼現在不修之後會更貴：** 不同維護者會產生不同樣本，CI 無法真正重算。
- **建議修法：** 使用一個決定性的 20 題集合，先以最少題數覆蓋所有可用風險標籤與各科首末題，再以 seed 補足。無須為每層建立獨立抽樣資料結構。

## 結論

- **Blocker：0**
- **High：仍有，會阻擋核心 M1/M2 動工。**

必須先修的 High 項目：

1. 建立獨立且可稽核的 discovery universe，不能再由 manifest tuples 自證完整。
2. 分離人工 `exam` metadata 輸入與 compile 輸出。
3. 定義 parked 的當前狀態／解除生命週期。
4. 讓 negative MOD observation 具有可重驗證據，而非孤立 hash 與布林值。
5. 規定 canonical 必須使用 snapshot 的 current revisions。
6. 封堵 L1 先被截斷、其後所有正規化檢查仍全綠的路徑。

因此：**v0.3 方向正確，沒有需要整段推翻的 Blocker；但上述 High 尚未處理前，不宜凍結 §4.6–§5.4，也不宜正式啟動會產生持久 manifest／observation 資料的 M1/M2。**
