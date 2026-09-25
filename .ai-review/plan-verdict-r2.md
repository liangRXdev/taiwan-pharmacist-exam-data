# plan-verdict（第二輪）— spec.md v0.3

覆核日期：2026-09-25　覆核者：Claude（主持人）　來源：`.ai-review/plan-review-r2.md`

編號：S{區塊}-{序}，對應 Codex 報告的小節編號。

| # | 項目 | 嚴重度 | 判定 | 理由／修法 |
|---|---|---|---|---|
| S1-1 | universe 由 tuples 自證 | High | 接受 | 屬實，第一輪 R1-1 的修正確實被弱化了。修法：manifest 新增 `discovery`，保存年度頁與科目頁的 HTML snapshot（內容定址）；universe 由 compile 從 snapshot 重新解析，不信任儲存下來的清單 |
| S1-2 | `exams.json` 輸入／輸出混淆 | High | 接受 | 人工維護的輸入移到 `inputs/exams.json`（屬 snapshot，不可刪），compile 產出 `data/exams.json` 投影 |
| S1-3 | parked 無生命週期 | High | 接受 | 採用 S4-3 的做法：每個 tuple 最多一筆「當前」parked，恢復後就移除，歷史交給 Git |
| S1-4 | observation 無時序規則 | Medium | 接受 | 以該 tuple 最新一次觀測為準。最新結果不是 `absent` 就不能標 `original`。另外 `absent` 的觀測時間必須在考後 90 天以後，確保更正窗口已經過了 |
| S1-5 | coverage 無 schema | Medium | 接受 | 改為結構化紀錄，原因用排序陣列（可多原因），並綁定 `release_date` 與來源 revision |
| S2-1 | negative evidence 不可重驗 | High | 接受 | 頁面 HTML 以內容定址存入 `raw/pages/`；`absent`、`present`、positive control 全部由 **compile 從 HTML 重新計算**，manifest 不存判定結果。這樣也順帶解決「`positive_control` 布林值可以任意填」的問題 |
| S2-2 | 可使用非 current revision | High | 接受 | compile 只能讀 `current`；AC-9 加入「canonical rev == current」 |
| S2-3 | current 缺不變量 | Medium | 接受 | 寫入 manifest 不變量，由 AC-9 驗證 |
| S2-4 | G4 環境邊界 | Medium | 接受 | G4 限定在「鎖定工具鏈 + CI runner 映像」，AC-5 在 CI 上以兩個全新 job 執行 |
| S3-1 | AC-0 可整場漏掉 | High | 接受（併入 S1-1） | 新增反例：刪除整場、漏掉最新一場 |
| S3-2 | 答案值未驗 | Medium | 接受 | **有效且嚴重**：現行 AC 只驗形狀，答案錯了也不會被抓到。新增 AC-14：逐題答案值必須等於來源表或備註展開的結果 |
| S3-3 | AC-5 環境 | Medium | 接受（併入 S2-4） | — |
| S3-4 | AC-6 共用錯誤判定器 | Medium | 接受 | 反例 fixture 對 §5.4 每個條件逐項翻轉，並用手寫的預期集合比對 |
| S3-5 | L1 被截斷後後續全綠 | High | 接受 | 新增字元歸屬契約：頁面 L1 的每個字元必須恰好歸到一個題目段落，或屬於明列的排除類別（表頭、頁碼、注意事項）。未歸屬的字元 → FAIL |
| S3-6 | `exam_date` URL 未核對 | Medium | 接受 | 併入 MG-1 證據：審查者逐字摘錄來源頁上的日期文字 |
| S3-7 | AC-9 可指向舊 revision | Medium | 接受（併入 S2-2） | — |
| S3-8 | MG-1 演算法未定、旗標可能漏標 | Medium | 部分接受 | 接受：用單一 coverage-set 演算法（S4-5）。部分接受「風險層成員由人工 oracle 固定」：v1 範圍內的 5 場，改為**把 M0 實測值設為回歸下限**（例如 113020 P1 疊印 216 字元、純向量圖 2 題、相容漢字約 65 處）。風險標籤本身由 L0 層的偵測器產生，不依賴 parser 的題目分段；不另外建立人工標註集，避免增加單人維護負擔 |
| S4-1 | 保留兩階段 | Low | 接受（不改動） | — |
| S4-2 | observations 不必 append | Medium | 接受 | 每個 tuple 只保存當前 observation（指向 HTML snapshot），歷史交給 Git。只有結果改變，或出現第一筆符合 90 天條件的 `absent` 時才開 PR |
| S4-3 | parked 當前狀態 | Medium | 接受（併入 S1-3） | — |
| S4-4 | 保留 coverage 與 eligibility | Low | 接受（不改動） | — |
| S4-5 | MG-1 單一演算法 | Medium | 接受（併入 S3-8） | — |

## 統計

- 共 22 項：接受 21（其中 7 項併入他項、2 項不改動）／部分接受 1／拒絕 0（範圍蔓延 0）

## 結論

所有 High 都是 manifest／intermediate schema 的補強，**架構本身（acquire／compile 兩段、manifest 為中心、compile 時計算 release 資格）沒有變**，不構成「架構整段更動」。修訂成 v0.4 後，判定為 **可以動工**，不需要第三輪。
