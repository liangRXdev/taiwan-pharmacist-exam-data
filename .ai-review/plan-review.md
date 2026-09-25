<!--
審查日期：2026-09-25
Codex 版本：codex-cli 0.153.4（mcp__codex__codex，sandbox read-only，approval never）
thread：01a0d74b-7c59-7d63-937b-e3d735222380
規劃文件：spec.md v0.2（commit 8abbf34）
備註：prompt 內含專案前提 (a)(b) 與規格摘要，並指示 Codex 直接讀取 cwd 下 spec.md 全文（repo 非空，檔案與 commit 一致）
以下為 Codex 原始輸出，未修飾、未刪改。
-->

# 規格覆審報告

結論：v0.2 的技術方向符合威脅模型，純規則式、失敗即 `parked`、raw PDF 保留、MOD 優先及人工閘門均合理。主要問題不是選型，而是數個關鍵性質目前「可以用弱化實作通過」：

- G4 的 byte-identical 定義與時間欄位、線上同步互相矛盾。
- 「確認不存在 MOD」沒有可稽核的證據模型，卻直接決定答案能否發布。
- 驗收條件沒有證明資料集完整；只處理一科甚至空集合，也可能大部分全綠。
- `parked`、發布資格與驗證證據沒有正式資料模型。
- AC-11 只涵蓋 ANS/MOD 並存，對目前多數「只有 MOD」的科目會真空通過。

本次僅唯讀檢視，未修改任何檔案。

---

## 1. 需求與邊界缺漏

| 嚴重度 | 問題 | 為什麼現在不修之後會更貴 | 建議修法 |
|---|---|---|---|
| **High** | **沒有定義完整性基準。** G6 要求 113 年起至最新一場，但沒有規定每場應恰有 P1–P6、各 tuple 只能出現一次，也沒有區分「站方確實沒有資料」與「discover 漏抓」。現有 AC 都以「已產出的科目」為量詞。 | 管線若只抓到一科、漏掉一場或回傳空 manifest，仍可能全綠；直到下游發現缺題才需回頭改 discover、manifest、驗證與 release。 | 規定每次成功 discovery 必須形成封閉的考試清冊：目標期間內的考試集合、每場 P1–P6 完整集合、每個來源 tuple 唯一。任何清冊不完整、頁面無法判定或 unexpected empty，整場不得視為成功。 |
| **High** | **`parked` 只有政策文字，沒有狀態模型。** 未定義 parked 的粒度是 PDF、科目、考試還是年度，也沒有 reason、來源、發生階段、最後檢查時間、是否允許部分考試發布。 | M2/M4 開始後，會被迫把 parked 塞進 manifest、questions 或外部文件；這會改動資料模型、release 篩選及所有驗收條件。 | 在規格中定義 parked record，至少包含唯一 scope、reason code、pipeline stage、來源識別、observed_at，以及 release 對「同場部分 parked」的處置。依「寧缺勿錯」原則，建議明定科目失敗時該科不發布；是否連帶阻擋整場須現在定案。 |
| **High** | **「crawler 確認無 MOD」未定義何謂確認。** `mod_checked_at` 只能證明某時間被填入，無法區分完整頁面明確無連結、HTTP 錯誤、redirect、登入/session 錯位或 selector 失效。 | 這個判斷會把 `unverified` 升為 `original`，直接越過最重要的 release 閘門；日後補證據模型需遷移既有答案狀態與 provenance。 | 將「無 MOD」定義成可證偽的成功觀測：檢查目標、官方考試 tuple、回應身分、結果類型、觀測時間及來源快照均有效，才能成為 negative evidence。任何不確定、空頁或解析失敗都不得更新 `mod_checked_at`，並維持 `unverified`。 |
| **Medium** | **外部端點的失敗分類未定義。** 未涵蓋非 200、redirect chain、HTML 錯誤頁偽裝成 PDF、空檔、截斷 PDF、逾時、429/5xx、Content-Type 不符及頁面結構改版。 | 若只寫成一般 exception，可能把暫時性失敗當成「沒有 MOD」或把 HTML 存成 raw；之後要清理錯誤 provenance 與 release。 | 定義每種結果只能落入三類：成功且身分已驗證、可重試但不得改變既有狀態、不可解析而 parked/FAIL。尤其禁止以空集合、404 或解析不到連結代表「無 MOD」。 |
| **High** | **raw 檔的版本／覆寫語意不明。** 官方 URL 可能維持不變但內容被替換；規格未說同一 URL 新 SHA256 是合法 revision、衝突或覆寫。 | 一旦 MOD 或官方 PDF 被原址更新，若 raw 檔被覆寫，舊 canonical 的 SHA256 可能失去可重建來源，破壞 G2。 | 規定官方內容變更為新的 immutable revision；舊 SHA256 與其 canonical 版本仍可追溯。相同來源識別但不同 hash 必須造成可見差異與人工審查，不可靜默覆蓋。 |
| **Medium** | **重入與併發沒有行為契約。** cron 與 `workflow_dispatch` 可同時執行，兩次執行也可能基於不同站方狀態開 PR。 | 可能出現 manifest、raw、canonical 分屬不同觀測批次，形成雜湊都正確但資料集合不一致的 release。之後才補會牽涉整個管線狀態。 | 規定一次 run 的資料必須屬於同一批次快照；失敗不得產生「部分批次可發布」狀態。並行結果若基線或來源 revision 不同，必須顯式衝突，不能後完成者靜默取代前者。 |
| **Medium** | **時間邊界未定義。** `exam_date` 的官方來源、時區、90/180 天的起訖包含關係均未規定。 | 邊界日可能在本機與 CI 得到不同 release 結果，直接違反 G4，也可能提早一天發布。 | 規定 `exam_date` 的權威來源、Asia/Taipei 時區，以及「滿 90 天」「180 天內」的精確比較語意。release 的參考時間亦須是顯式輸入，而不是執行當下的隱含時間。 |
| **Medium** | **來源欄位的 nullability 不明。** 沒有 MOD 時，`correction_url`／`correction_sha256` 是 `null`、省略或空字串？ANS 缺失但有 MOD 時亦不清楚。 | 不同階段會產出不同 JSON 形狀，破壞 byte-identical、驗證與下游相容性。 | 將 question、exam、manifest 的 required/nullable、enum、陣列順序及空值語意列為 normative schema；特別定義 ANS-only、MOD-only、ANS+MOD、尚未完成 MOD 檢查四種狀態。 |
| **Medium** | **`script_char_offsets` 座標系未定義。** 不清楚是原始抽取字串、正規化後 `stem`、Unicode code point、UTF-16 offset 或 byte offset；選項中的小字亦未涵蓋。 | 一旦資料發布，下游會依某種索引方式解讀；之後更改即是破壞性 schema 變更。 | 明定 offset 所指的是 canonical 正規化後文字及其計數單位；同時決定小字型證據是否只適用 stem，若只適用 stem，需明確寫成限制。 |
| **Medium** | **M4 的 110–112 與 G6/D7 邊界含糊。** G6 說 release 自 113 起，M4 又回填 110–112。 | 實作時會不清楚舊年度是 canonical 的一部分、僅實驗資料，還是可進 release；不同解讀會改變驗收母集合。 | 明定 110–112 僅是相容性探索／parked 記錄，或明定可產生非 release canonical；不得讓它們隱式擴張 v1 release 範圍。 |

---

## 2. 架構風險

| 嚴重度 | 問題 | 為什麼現在不修之後會更貴 | 建議修法 |
|---|---|---|---|
| **Blocker** | **G4 的 byte-identical 目前不可成立。** 同一指令若重新連線，站方內容可能改變；`fetched_at`、`mod_checked_at` 也會隨時間改變。AC-5 又只驗 `parse+validate`，實際弱化了 G4。 | 若照字面實作，必須在同步時間、線上狀態與 deterministic build 之間做不可能的折衷；最後勢必要重定義命令、輸入邊界與產物。 | 將 G4 拆成兩個規格性概念：同步是帶觀測時間的新 revision；從同一份 immutable raw＋manifest snapshot 建置，才必須 byte-identical。明確列出哪些產物屬於 deterministic build。 |
| **High** | **最難回頭的決策是把「MOD 不存在」壓縮成時間戳。** `answer_status` 的可信度實際依賴負向觀測，但 schema 沒有觀測證據。 | 已發布的 `original` 無法證明當時為何被視為安全；補欄位後舊資料無法可靠回填。 | 將 MOD observation 視為 provenance 的一級資料，而不是單一 `mod_checked_at`。`original` 必須可追到一筆成功且 scope 完整的「未發現 MOD」觀測。 |
| **High** | **`verified: true` 把不同層級的驗證混成每題布林值。** AC-5 是整體建置性質、AC-10 是每場抽樣、AC-12 是科目層級；它們不能誠實地表示成「此題通過全部 AC」。 | 下游容易把它解讀為逐題人工驗證；未來增加 AC 時，歷史布林值語意也會漂移。 | 移除「通過全部 AC」的逐題語意，改把 release eligibility 定義為建置時計算的結果；若保留欄位，必須精確限定它只代表哪些逐題性質。 |
| **High** | **`manifest.json` 是核心狀態卻沒有 schema，也未列入目錄結構。** discover、fetch、MOD observation、revision 與完整性都依賴它。 | M1 若先自由形成 manifest，M2 之後才補契約，會造成資料遷移與 provenance 斷裂。 | M1 前先定義 manifest 的規範性資料模型、唯一鍵、來源 revision、觀測狀態與失敗狀態；不可只把它視為內部暫存檔。 |
| **High** | **「試題、ANS、MOD 三份 PDF 互為獨立 oracle」表述過強。** 它們來自同一官方系統；Q 不含標準答案，而且多數科目並非三份並存。結構一致只能抓錯位，不能證明題幹未被靜默改字。 | 若把結構交叉驗證誤當內容正確性證明，會留下與威脅模型正面衝突的盲點。 | 將保證拆開陳述：來源身分一致性、題號／題數一致性、答案 revision 一致性、文字忠實度抽樣。不得宣稱結構檢查能證明題幹字元忠實。 |
| **High** | **圖片題模型只以 image object 判定，沒有涵蓋向量圖形或整頁背景 image 的反例。** PDF 圖表可能由 line/curve/rect 組成，也可能整頁皆有背景圖。 | 若實際存在，會出現圖片題 false negative，或整科 false positive；D4 與 AC-2 都依賴這個欄位，日後更換判定會改動大量 canonical 資料。 | 先把支援性質寫清楚：M0 corpus 中所有人工識別之題圖是否皆包含題目範圍內 image object。若不能證明，圖片判定契約須涵蓋 PDF 圖形物件類別及頁面背景排除規則。 |
| **Medium** | **正規化與「字元級一致」的參考層次矛盾。** §4.5 明確會轉換相容漢字、全半形、空白與換行，但 AC-10 要與 PDF 原文字元級一致。 | 驗收者可能依兩種不同基準判定，造成同一輸出有人判 PASS、有人判 FAIL。 | 定義三層：PDF visual/source text、deduped extraction、canonical normalized text。AC-10 應比較「canonical 是否恰等於對原文套用列舉轉換後的結果」，並另確認沒有未列舉變更。 |
| **Medium** | **`accepted_answers` 名為集合但資料型別是陣列，canonical order 未定義。** `["B","C"]` 與 `["C","B"]`、重複集合、重複元素目前都可能合法。 | 會破壞 byte-identical，也使下游將等價答案解讀成不同資料。 | 定義元素順序、集合順序、禁止重複及各 `score_policy` 的唯一 canonical 形狀。 |
| **Low** | **「前端一律 `textContent`」超出資料層邊界。** 專案明確沒有前端，且無法約束下游。 | 形成無法由本 repo 驗收的假性要求，稀釋真正的資料層契約。 | 移至 README 的下游安全建議，或刪除；不要列為本管線設計原則。 |

---

## 3. 驗證策略缺口

### 跨 AC 的共通問題

| 嚴重度 | 問題 | 為什麼現在不修之後會更貴 | 建議修法 |
|---|---|---|---|
| **High** | §6 宣稱「每項對應一個 pytest」，但 AC-10 是人工閘門，無法由 CI 自動判定。 | 會出現假測試或以永遠 PASS 的標記代替人工證據。 | 明確拆分 automated AC 與 manual acceptance evidence；AC-10 的完成紀錄必須綁定考試 revision／來源 SHA256。 |
| **High** | 沒有任何 AC 驗證 release 母集合完整。所有條件都可以對空集合真空通過。 | 這是最典型的「沒有錯資料，但也沒有資料」弱化實作。 | 增加既有 G6/G1 的 completeness assertion：目標考試集合、每場 P1–P6、每科題號集合均需封閉且完整；這是既有目標的驗收化，不是新增需求。 |
| **Medium** | M1 的「crawler SHA256 與 manual oracle 相符」只能證明下載到同一 bytes，不能證明 manual oracle 當初下載正確。 | 已知曾因 session 取得重複考試，因此「兩次取得同一錯檔」仍可能通過。 | SHA 比對之外，oracle 與 crawler 都必須分別通過 PDF 表頭 tuple 身分驗證；不能以檔名或相互相等代替官方身分。 |

### AC-1 ～ AC-13 弱化實作分析與改寫方向

| AC | 嚴重度／問題：可通過但實際壞掉的弱化版本 | 為什麼現在不修之後會更貴 | 建議修法：堵死弱化版本的可證偽斷言 |
|---|---|---|---|
| **AC-1** | **High**／只產生一科；或把題數表頭、答案表及解析題目都錯讀成 0，三者仍相等；亦可同時漏掉同一題。 | 無法證明完整性，漏題直到下游才被發現。 | 對每個已確認的 P1–P6 tuple，要求表頭題數解析成功且大於 0；試題、答案的題號集合均恰為 `1..N`，無缺號、重號、越界；並要求每場六科完整。 |
| **AC-2** | **High**／每題硬塞 A–D 鍵即可；選項文字可放錯題、截斷或只含空白。把 `has_figure` 全設 true，也可能放寬空選項。 | 選項錯位仍是靜默內容錯誤，且結構檢查全過。 | 除鍵集合外，非圖片選項須為正規化後非空；A→B→C→D 標記必須各在該題邊界內且各一次。空選項豁免必須逐選項對應其自身版面範圍內的圖形證據，不得只依題級 `has_figure`。 |
| **AC-3** | **High**／`[[]]`、重複答案、`normal` 配多答案、`multi_answer` 配單答案、`all_credit` 同時保留答案都可能通過。 | 下游計分會產生語意分歧；事後收緊屬 schema 相容性變更。 | 建立跨欄位真值表：`normal` 僅一個 singleton；`multi_answer` 至少兩個互異、非空集合且符合 MOD 句型；`all_credit` 必須恰為 `[]`；集合內與集合間均禁止重複並規定 canonical order。 |
| **AC-4** | **Medium**／所有 ID 都用隨機 UUID，仍全域唯一；ID 與 year/session/subject/question_no 可不一致。 | provenance、排序及下游 join 都會錯，但唯一性測不到。 | 每題 ID 必須恰等於 schema 指定欄位的決定性組合；反向解析後須與欄位逐項一致；完整資料集中 ID 與 `(exam_code, subject, question_no)` 為一對一。 |
| **AC-5** | **Blocker**／穩定地輸出錯誤內容即可通過；只測 parse+validate，render、來源聲明及時間欄位不在範圍內。亦可能第二次直接沿用第一次輸出。 | G4 會在 M3/M4 才暴露為不可達成。 | 明定相同 immutable input snapshot、相同規格版本及相同顯式 build time 下，從乾淨狀態產出的 canonical、figures 與所有 dist bytes 全數相同；建置不得依賴前次產物。同步結果不納入此斷言。 |
| **AC-6** | **High**／產生器把所有 `verified` 硬寫為 true；或把失敗題直接刪除，計數仍為 0。 | 這個 AC 目前驗證標籤，不驗證性質，正是「驗證某物」而非「某性質」。 | release 必須重新依來源完整性、schema、答案狀態、考試年齡及 validation evidence 計算資格；不得信任輸入的 `verified`。並與完整性母集合比對，防止刪題規避。 |
| **AC-7** | **High**／把 stem/options 清空或刪除大量字元，即可沒有全形英數、雙空白或相容漢字；未列舉字元也可被任意改寫。 | 直接違反最高風險的「題幹不可靜默改寫」。 | 對每段文字斷言：canonical 恰等於對 deduped source 套用 §4.5 指定轉換一次的結果；轉換集合以外的字元序列保持不變；正規化具冪等性；stem 與非豁免 option 不得為空。 |
| **AC-8** | **High**／不輸出任何最近考試或 unverified 題目即可通過；也可偽造 `exam_date`、`answer_status` 或 `mod_checked_at`。 | 可能既違反 G6，又繞過 90 天與 MOD 閘門。 | 先對目標 universe 做完整性比對，再斷言 release 恰等於 eligible 集合；`exam_date` 必須有官方 provenance；`original` 必須連結有效的 negative MOD observation；90 天邊界使用明定時區與顯式 release date。 |
| **AC-9** | **High**／任意 raw 檔只要自行計算相符 SHA256 即可；錯考試、錯科目、ANS/MOD 類型顛倒仍會通過。`*_sha256` 對缺失 MOD 的語意也不明。 | provenance 看似完整但指向錯來源，屬最危險的可稽核性假象。 | 每個 hash 除存在且相符外，其 raw PDF 表頭必須與 question/exam/subject/source type 的 tuple 一致；URL、revision 與 hash 需一對一。不存在的來源必須使用唯一明定的 null 狀態，而非空字串或任意檔。 |
| **AC-10** | **High**／人工挑最容易的 20 題，避開 dedupe、相容漢字、表格、跨頁、小字、MOD 與長題幹；每次挑不同題也無稽核紀錄。 | 抽樣是唯一直接檢查內容忠實度的閘門；弱抽樣會使 silent corruption 穿透。 | 抽樣必須決定性且分層，至少覆蓋 figure、dedupe affected、CJK compatibility、script chars、表格／跨頁、corrected answer、首末題等已知風險類別；記錄題目 ID、來源 SHA256、比較層次及審查結果。若當次無某類，明確記錄不適用。 |
| **AC-11** | **High**／只在 ANS 與 MOD 並存時執行；目前多數 MOD-only 科目會真空通過。也可忽略未被 parser 消耗的備註片段，或只比較集合不檢查重複題號。 | 這會直接讓錯誤答案進 release，且答案模型完成後再改會影響所有 corrected 資料。 | AC 應對「任何有 MOD 的科目」生效：MOD 答案表完整覆蓋 `1..N`；每個 `＃` 題恰對應一則完整解析且無剩餘文字的備註；備註不得有額外／重複／越界題號；非 `＃` 題不得被備註更正。若 ANS 同時存在，再額外要求非 `＃` 題逐題相同。 |
| **AC-12** | **High**／六份 Q 可全部指向同一場考試，只要科目名各自合法；Q 與答案只比考試名稱，未必比較同一科目、類科、場次或請求 tuple。 | 已發生過 session 重複下載，此 AC 尚不足以阻擋同類錯置。 | 對每個 discovered tuple，Q、ANS、MOD 各自的表頭考試名稱、類科、科目、試題代號／題數等可用識別均須與 manifest 一致；每個 P1–P6 tuple 恰出現一次。不得以檔名或 URL query 單獨作為身分證明。 |
| **AC-13** | **High**／針對第 54 題硬編 `C-14`，或虛構「去重字元數」，即可通過；只測單一重複模式也不能證明沒有誤刪合法重複字元。 | dedupe 是整個文字忠實度最關鍵且不可逆的轉換；錯誤規則可能在未抽樣題目靜默刪字。 | 保留已知第 54 題 regression，但另斷言：所有被去除字元均有相同 glyph、位置與幾何證據；合法相鄰重複字元不得被刪；去重前後差異可逐字追溯；同一輸入重複去重結果不再改變。不得只驗計數。 |

---

## 4. 更簡單的替代方案

| 嚴重度 | 問題 | 為什麼現在不修之後會更貴 | 建議修法 |
|---|---|---|---|
| **High** | 同一規格把「會隨官方站方改變的同步」與「必須 byte-identical 的建置」視為同一條管線。 | 導致 G4、時間欄位與 cron 天生衝突，後續每層都需特殊處理。 | 最簡單的規格分界是兩階段：① acquisition 產生不可變來源 snapshot；② compile 僅以 snapshot 為輸入。只有第二階段承諾 byte-identical。元件不必增加，僅需把責任邊界寫清楚。 |
| **Medium** | `verified` 同時重複表達 AC 結果、答案可信度及 release 資格。 | 三種狀態會隨不同事件改變，單一布林值容易矛盾。 | 刪除逐題 `verified`，由 `answer_status`、parked 狀態、來源完整性及 build validation 決定 release；若下游確實需要，再由 release 產物隱含「已通過」，不在 canonical 儲存易漂移布林值。 |
| **Medium** | 目前每個 AC 各自補結構條件，但缺少一個明確的 dataset inventory 契約。 | 會持續增加局部 AC，仍無法回答「應有多少場、多少科、哪些題」。 | 以一份規範性的 inventory/manifest 契約作為所有 AC 的量詞母集合：先證明 universe，再驗每個成員。這比在 AC-1、AC-8、AC-12 各自猜完整性更簡單。 |
| **Medium** | 三種衍生格式都要求 round-trip，但 Markdown、CSV、Anki 並非天然可無損承載 canonical 全欄位與 figure/provenance。 | M3 可能為了滿足含糊的 round-trip 而引入額外欄位或私有編碼，增加不必要複雜度。 | 將 M3 改成「每個衍生記錄可唯一追溯至 canonical ID，且規格指定的投影欄位與 canonical 相等」。只有 JSON 是 canonical；不要求衍生格式重建全部資料。 |
| **Low** | cron、前端安全句、Anki round-trip 等次要事項與核心 silent-error 契約並列，使規格焦點分散。 | 實作者可能先完成周邊元件，核心 MOD negative evidence 與完整性模型反而延後。 | M1/M2 前只凍結四項核心契約：manifest universe、source revision、MOD observation、canonical/release eligibility。cron 與衍生格式維持後續里程碑，不影響核心模型。 |
| **Medium** | AC-10 每次固定「20 題且 ≥5 圖片題」簡單，但沒有利用已知高風險題型。 | 同樣投入人工時間，卻可能反覆驗證低風險普通題。 | 保留 20 題上限與單人維護取捨，但改成 deterministic risk-stratified sample；這不增加人工數量，只提高現有閘門的偵錯能力。 |

整體建議的規格修訂優先序為：先修正 G4 的輸入邊界，再補 manifest／MOD negative evidence／parked 模型，接著加入資料集完整性斷言，最後逐條收緊 AC。這四項若在 M1/M2 後才處理，會同時牽動資料模型、歷史 provenance、release 邏輯與測試基準。
