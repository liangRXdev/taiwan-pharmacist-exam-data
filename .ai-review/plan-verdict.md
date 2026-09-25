# plan-verdict — spec.md v0.2（8abbf34）

覆核日期：2026-09-25　覆核者：Claude（主持人）　來源：`.ai-review/plan-review.md`

編號：R{區塊}-{序}；區塊 3 的 AC 逐條分析記為 R3-AC{n}，共通問題記為 R3-C{n}。

## 1. 需求與邊界缺漏

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|---|---|---|---|
| R1-1 | 缺完整性基準（universe） | High | 接受 | 目前的 AC 都只驗「已經產出的東西」，只產出一科、甚至空集合都能全綠。這是把 G1/G6 寫成驗收條件，不算新增需求 |
| R1-2 | `parked` 無狀態模型 | High | 接受 | 粒度定為科目。科目 parked 時，同場其他科目仍可發布，但 release 必須明列缺漏的科目（不可靜默缺科） |
| R1-3 | 「確認無 MOD」無定義 | High | 接受 | 這是 `unverified` 升為 `original` 的唯一依據，必須是可證偽的正向觀測 |
| R1-4 | 端點失敗分類 | Medium | 接受 | 結果只能歸為三類：成功、可重試、不可解析。404 或解析不到連結不得視為「無 MOD」 |
| R1-5 | raw 版本／覆寫語意 | High | 接受 | 改用內容定址（檔名帶 SHA256），raw 不可變；同一來源出現新 hash 就產生新 revision 並開 PR 審查 |
| R1-6 | 重入與併發 | Medium | 部分接受 | 問題確實存在，但不需要設計批次快照機制。修法：GitHub Actions 設 `concurrency` group 讓執行序列化；PR 的 base 若不是最新 main 就判為衝突，不自動 rebase |
| R1-7 | 時間邊界 | Medium | 接受 | 時區定為 Asia/Taipei，閉區間語意寫清楚；release 參考日期必須由參數顯式傳入 |
| R1-8 | 來源欄位 nullability | Medium | 接受 | 定義 ANS-only、MOD-only、ANS+MOD 三種狀態的 schema，不存在的欄位一律 `null` |
| R1-9 | `script_char_offsets` 座標系 | Medium | 接受 | 以 canonical 正規化後文字的 Unicode code point 計數；stem 與 options 都涵蓋 |
| R1-10 | 110–112 與 G6 邊界 | Medium | 接受 | 110–112 只做相容性探索，產物不進 `data/`，只留 parked 或探索報告 |

## 2. 架構風險

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|---|---|---|---|
| R2-1 | G4 byte-identical 不可成立 | Blocker | 部分接受（嚴重度改 High） | 問題屬實，但修法只是界定責任邊界：拆成 acquire（非決定性）和 compile（決定性）兩段，不必整段重寫，所以不到 Blocker。這項仍會改動架構，修訂後需要重審 |
| R2-2 | MOD 不存在壓縮成時間戳 | High | 接受（併入 R1-3） | 定義 `mod_observations[]` 為一級 provenance 資料 |
| R2-3 | 逐題 `verified` 混層 | High | 接受 | 刪除逐題的 `verified`，release 資格改為 compile 時計算 |
| R2-4 | manifest 無 schema | High | 接受 | 在 M1 開始前寫成規範性 schema |
| R2-5 | 「獨立 oracle」表述過強 | High | 部分接受（嚴重度改 Low） | 表述確實過強，但只要修正文字：把保證拆成來源身分、結構、答案 revision、文字忠實度四類。資料模型不受影響 |
| R2-6 | 圖片判定未涵蓋向量圖 | High | 接受（嚴重度改 Medium） | **實測確認**：排除頁框後，有 2 題題幹只有向量圖、沒有 image 物件（113090 P3 第 66 題 49 個向量物件、114090 P3 第 8 題 4 個）。另外每一頁都有一條貫穿整頁的框線，會造成全面誤判。修法是判定規則納入 curve/line/rect 並排除頁框，schema 不變 |
| R2-7 | 正規化與 AC-10 層次矛盾 | Medium | 接受 | 定義 L0（PDF 字元）、L1（去重後）、L2（canonical）三層 |
| R2-8 | `accepted_answers` 無 canonical order | Medium | 接受 | 集合內依字母排序；集合之間依（長度，字典序）排序；禁止重複 |
| R2-9 | `textContent` 超出邊界 | Low | 接受 | 移到 README 的下游建議 |

## 3. 驗證策略缺口

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|---|---|---|---|
| R3-C1 | AC-10 非 pytest | High | 接受 | 拆成 automated AC 與 manual gate；人工證據檔要綁定來源 SHA256，CI 只驗證證據檔存在且 hash 相符 |
| R3-C2 | 無完整性斷言 | High | 接受（併入 R1-1） | 新增 AC-0 |
| R3-C3 | oracle SHA 相符不證身分 | Medium | 接受 | crawler 產物和 oracle 都要各自通過表頭身分驗證 |
| R3-AC1 | 題數可同為 0／同漏 | High | 接受 | 題數必須大於 0，題號集合必須恰為 `1..N` |
| R3-AC2 | 硬塞 ABCD、依題級 figure 放寬 | High | 接受 | 空選項豁免必須以「該選項自身範圍內有圖形物件」逐選項判定 |
| R3-AC3 | 跨欄位無真值表 | High | 接受 | 建立 `score_policy` × `accepted_answers` 的真值表 |
| R3-AC4 | ID 唯一但不一致 | Medium | 接受 | ID 反向解析後必須與各欄位一致 |
| R3-AC5 | 只測 parse+validate | Blocker | 部分接受（嚴重度改 High，併入 R2-1） | 範圍擴大到整個 compile 產物（含 figures、dist），但同步產物不納入 |
| R3-AC6 | 驗標籤不驗性質 | High | 接受（併入 R2-3） | release 必須等於重新計算出的 eligible 集合 |
| R3-AC7 | 清空文字可通過 | High | 接受 | 可證偽的斷言是：L2 == T(L1)，T 冪等，且非豁免文字不得為空 |
| R3-AC8 | 不輸出即通過；`exam_date` 可偽造 | High | 部分接受 | 接受「release == eligible」與 negative observation 連結。`exam_date` 的「官方 provenance」改為：人工填入並附考選部考試日程來源 URL，經 PR 審查。站方沒有結構化日期端點，要求自動擷取會變成新增需求 |
| R3-AC9 | hash 相符但來源錯 | High | 接受（併入 AC-12 強化） | hash 對應的 raw 表頭必須與 source type 和 tuple 一致 |
| R3-AC10 | 人工挑軟柿子 | High | 接受 | 改成決定性分層抽樣（seed＝來源 SHA256） |
| R3-AC11 | MOD-only 真空通過 | High | 接受 | **有效且重要**：19 科有 MOD，其中 16 科只有 MOD，現行寫法對它們根本沒有約束 |
| R3-AC12 | 六份指向同一場 | High | 接受 | tuple 必須一一對應，Q、ANS、MOD 三份各自驗表頭 |
| R3-AC13 | 硬編第 54 題、只驗計數 | High | 部分接受 | 接受兩點：加入反例「合法相鄰重複字元不得被刪」（例如 `C-11` 這類不同位置的重複字），以及記錄被刪字元清單。拒絕「斷言被刪字元有相同 glyph／位置證據」：這是 `dedupe_chars()` 本身的定義，測它等於在測第三方函式庫 |

## 4. 更簡單的替代方案

| # | 項目 | 嚴重度 | 判定 | 理由 |
|---|---|---|---|---|
| R4-1 | acquire／compile 兩階段 | High | 接受（併入 R2-1） | — |
| R4-2 | 刪除 `verified` | Medium | 接受（併入 R2-3） | — |
| R4-3 | inventory 契約當母集合 | Medium | 接受（併入 R1-1、R2-4） | — |
| R4-4 | M3 round-trip 改投影追溯 | Medium | 接受 | Markdown 和 CSV 無法無損還原 canonical，改成「每筆衍生記錄可追溯到 canonical ID，且投影欄位與 canonical 相等」 |
| R4-5 | M1/M2 前先凍結四項核心契約 | Low | 接受 | 只調整順序，沒有額外成本 |
| R4-6 | AC-10 分層抽樣 | Medium | 接受（併入 R3-AC10） | — |

## 統計

- 共 41 項：接受 35（其中 8 項併入他項）／部分接受 6／拒絕 0（範圍蔓延 0）
- Codex 沒有標注任何 `[新增需求]`。R3-AC8 自動擷取 `exam_date` 屬於隱性擴張，已在該項內改為人工填入並附來源
- 嚴重度下修：R2-1（Blocker → High）、R3-AC5（Blocker → High）、R2-5（High → Low）、R2-6（High → Medium）

## 結論

沒有 Blocker。但 High 項目會改動架構（acquire／compile 分段、manifest 與 observation schema、刪除 `verified`、parked 模型），依規則 **修訂後需要重跑 `/codex-checkplan`**。
