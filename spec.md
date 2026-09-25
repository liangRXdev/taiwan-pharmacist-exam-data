# spec.md — `taiwan-pharmacist-exam-data`

**考選部藥師國考題庫結構化管線**

| 項目 | 內容 |
|---|---|
| 版本 | v0.2（M0 探針完成，需求確認定案） |
| 日期 | 2026-09-25 |
| Owner | liangRXdev |
| Tool tier | **L1**（有臨床/教學使用者，非劑量輸出）→ 需 `README.md` + `CLAUDE.md` + `CHANGELOG.md` |
| 授權 | 程式碼 MIT；題目資料 Public Domain（著作權法 §9 I ⑤）；自加標註 CC BY 4.0 |
| 狀態 | M0 通過 → 技術路線定案為純規則式；待 `/codex-checkplan` 覆審後啟動 M1/M2 |

---

## 1. 問題陳述

社群現行做法為「PDF → LLM → 生成式網站」，其失效模式為**靜默錯誤**：輸出流暢但無法稽核。具體風險：

| 失效模式 | 後果 | 使用者可察覺 |
|---|---|---|
| LLM 抽取幻覺 | 題幹被改寫、選項遺漏、上下標/數值失真 | ✗ |
| 答案來源錯位 | 標準答案在獨立 PDF，單丟試題 PDF 時答案為 LLM 推理產物 | ✗ |
| 更正答案未套用 | 初版答案 ≠ 最終答案（一律給分／多重答案） | ✗ |
| 圖片題失真 | 結構式、層析圖、計算圖表整題無效 | 部分 |
| 無 provenance | 無法追溯年度/科目/題號，無版本、無 diff | ✗ |

錯誤答案在練習型應用中會被**反覆增強**，其危害高於「沒有題庫」。本專案的核心價值不是省時間（一年兩次，手工約 1 小時），而是 **可重現性（reproducibility）與可稽核性（auditability）**。

M0 實測佐證「更正答案未套用」為常態而非邊緣：5 場考試 30 科中有 19 科存在更正答案（MOD）。

---

## 2. 目標與非目標

### 2.1 目標（v1）

| ID | 目標 |
|---|---|
| G1 | 從考選部考畢試題平台自動擷取藥師國考測驗式試題、初版答案（ANS）與更正答案（MOD） |
| G2 | 產出 canonical JSON 題庫，每題具備完整 provenance（來源 URL、SHA256、擷取時間） |
| G3 | 提供衍生格式：Markdown、CSV、Anki `.apkg`（衍生自 JSON，非獨立來源） |
| G4 | 任何人 fork 後執行同一指令，可得到 **byte-identical** 的輸出（冪等） |
| G5 | 所有未經規則式驗證的題目均明確標記，且預設排除於 release build |
| G6 | v1 release 範圍：**113 年起至最新一場**（D7） |

### 2.2 非目標（v1 明確排除）

| ID | 非目標 | 理由 |
|---|---|---|
| N1 | 生成題目詳解／解析 | 屬 LLM 生成內容，與「可稽核事實」混合會污染資料品質；留待 v2 獨立欄位 |
| N2 | 遊戲／測驗前端 | 本專案僅為資料層。前端為下游消費者 |
| N3 | 申論式試題 | 藥師國考六科均為測驗式 |
| N4 | 其他職類（醫師、護理師…） | 架構須可擴充，但 v1 只驗證藥師 |
| N5 | 圖片題的圖形內容抽取 | v1 僅標記 `has_figure` 並保留整題裁切影像，不做 OCR/VLM 解讀 |
| N6 | 上下標還原 | 屬改寫題幹；v1 只標記證據，還原延至 v2 annotation 層（D3） |
| N7 | 科目次分類（ATC、章節） | 自建標註，若做須置於獨立 `annotations.json` |
| N8 | LLM fallback | M0 顯示規則式命中率 100%；解析失敗的年度標 `parked`，不以 LLM 補救 |

---

## 3. 資料來源契約

### 3.1 端點

| 用途 | URL 樣式 | 狀態 |
|---|---|---|
| 年度考試清單 | `GET /exam/wFrmExamQandASearch.aspx?y={西元年}` | 已實測 |
| 科目清單 | `GET /exam/wFrmExamQandASearch.aspx?y={西元年}&e={exam_code}` | 已實測 |
| 試題 PDF | `GET /exam/wHandExamQandA_File.ashx?t=Q&code={exam_code}&c={類科}&s={科目}&q=1` | 已實測 |
| 單科答案 PDF | `GET /exam/wHandExamQandA_File.ashx?t=S&code={exam_code}&c={類科}&s={科目}&q=1` | 已實測；ANS 或 MOD 未確認 |
| 全考試標準答案 | `GET /exam/wHandExamQandA_File.ashx?t=A&code={exam_code}` | 已實測 |
| 更正答案（MOD） | **未知**（H1） | M1 以 oracle SHA256 比對找出 |

Base：`https://wwwq.moex.gov.tw`

實測 `exam_code`：`113020`、`113090`、`114020`、`114090`、`115020`（第一次 `xxx020`、第二次 `xxx090`；僅為觀察，**不得據以枚舉**）。

### 3.2 已知約束（實測）

| 約束 | 說明 | 因應 |
|---|---|---|
| `exam_code` 不可枚舉 | 無效 code 會 redirect 回上一個有效 code，不回 404 | 必須解析 `<select>` 的 `option value`；**禁止**猜測式枚舉 |
| 存在 session 狀態 | 跨請求沿用前次選擇（手動下載亦曾因此取得重複檔） | `requests.Session()`，每次請求後驗證回應 `code` 與請求一致；下載後比對 PDF 表頭考試名稱 |
| 打包功能限 8 科目 | 站方明示網路資源限制 | 逐檔下載，請求間 `sleep(1.5s)`，加 `User-Agent` 與聯絡資訊 |
| 引用聲明 | 站方要求註明來源、確保完整、不得增刪 | README 與每份輸出檔頭嵌入來源聲明；**禁止任何形式的題幹改寫** |
| 官方代碼不穩定 | 檔名科目碼跨年變動且同場重複（113090 有兩個 `11`）；試題代號 113-1→113-2 變動（調劑 4306→1306） | 自訂 `P1`–`P6`（D2），官方代碼僅存 `source` |
| 下載檔名截斷 | 如 `藥物分析與生藥學(含.pdf` | 科目身分以 PDF 表頭為準，不以檔名為準 |

### 3.3 假設狀態

| ID | 假設 | 狀態 | 依據 / 驗證方法 |
|---|---|---|---|
| A1 | 更正後最終答案之來源 | ✅ **已解** | 114090 三科同時有 ANS 與 MOD：MOD 表頭「測驗題標準答案更正」，僅 `＃` 題與 ANS 不同，其餘逐題一致 |
| A2 | 試題 PDF 具文字層 | ✅ 成立 | 每科 6.6k–13.7k 字元；`(cid:)` 0；PUA 0 |
| A3 | 題號／選項格式跨年度一致 | ✅ 成立（113–115） | 題號 `1.`、選項 `A.`；30 科題數與 ABCD 結構 100% 命中 |
| H1 | MOD 可經某 `t=` 參數或頁面連結取得 | 待驗 | M1：crawler 產物與 oracle SHA256 相符 |
| H2 | 更正答案均於考後 90 天內公告 | 待驗（推論） | M1：蒐集歷年更正公告日期 |
| H3 | MOD 備註僅有「答X或Y(或XY)者均給分」「一律給分」兩類句型 | 22/22 句成立 | 出現新句型 → AC-11 FAIL，不靜默通過 |

---

## 4. 資料模型

### 4.1 Canonical question object

```jsonc
{
  "id": "114-1-PHARM-P2-067",          // {民國年}-{場次}-PHARM-{P1..P6}-{題號3碼}
  "exam_code": "114020",
  "year_roc": 114,
  "session": 1,                        // 該年度第幾次
  "profession": "pharmacist",
  "subject": "P2",                     // 自訂穩定代碼，見 subjects.json
  "stage": 1,                          // 由 subject 推導：P1–P3 → 1，P4–P6 → 2
  "question_no": 67,
  "stem": "…",                         // 原文，禁止改寫
  "options": { "A": "…", "B": "…", "C": "…", "D": "…" },  // 圖片選項可為 ""（限 AC-2 條件）
  "accepted_answers": [["B"], ["C"], ["B", "C"]],          // 答案集合之陣列；all_credit → []
  "answer_status": "corrected",        // original | corrected | unverified
  "score_policy": "multi_answer",      // normal | multi_answer | all_credit
  "answer_raw_note": "第67題答B或C或BC者均給分",  // MOD 備註逐字；無更正為 null
  "has_figure": false,
  "figure_refs": [],                   // 整題裁切 PNG 相對路徑
  "flags": [],                         // 例："script_chars"
  "script_char_offsets": [],           // flags 含 script_chars 時，stem 中小字型字元之 offset
  "extraction": "rule",
  "verified": true,                    // 是否通過全部 AC
  "notes": null,
  "source": {
    "subject_file_code": "0402",       // 官方檔名科目碼（不穩定，僅追溯）
    "paper_code": "2305",              // 試題代號
    "category_name": "藥師(一)",        // 類科名稱
    "subject_name_raw": "藥學(二)(包括藥物分析與生藥學(含中藥學))",
    "question_url": "…", "answer_url": "…", "correction_url": "…",
    "question_sha256": "…", "answer_sha256": "…", "correction_sha256": "…",
    "fetched_at": "2026-09-25T00:00:00+08:00",
    "mod_checked_at": "2026-09-25T00:00:00+08:00"
  }
}
```

### 4.2 考試層級物件（`exams.json`）

```jsonc
{
  "exam_code": "114020", "year_roc": 114, "session": 1,
  "exam_date": "…",                    // 用於 90 天 release 閘門
  "text_fidelity": { "scripts": "flattened" }   // flattened（113–114）| size_encoded（115–）
}
```

### 4.3 `subjects.json`（跨年度科目對照）

| 代碼 | 114 年起名稱 | 113 年舊名 | stage |
|---|---|---|---|
| P1 | 藥學(一)(包括藥理學與藥物化學) | 藥理學與藥物化學 | 1 |
| P2 | 藥學(二)(包括藥物分析與生藥學(含中藥學)) | 藥物分析與生藥學(含中藥學) | 1 |
| P3 | 藥學(三)(包括藥劑學與生物藥劑學) | 藥劑學與生物藥劑學 | 1 |
| P4 | 藥學(四)(包括調劑學與臨床藥學) | 調劑學與臨床藥學 | 2 |
| P5 | 藥學(五)(包括藥物治療學) | 藥物治療學 | 2 |
| P6 | 藥學(六)(包括藥事行政與法規) | 藥事行政與法規 | 2 |

對應以 PDF 表頭「科目名稱」（經 `dedupe_chars()`、§4.5 相容漢字正規化、去除 `(試題代號：…)` 後）精確比對；比對不到 → FAIL（不做模糊比對）。

### 4.4 答案判定規則（決定性）

| 來源狀態 | `answer_status` | `accepted_answers` |
|---|---|---|
| 有 MOD，題目非 `＃` | `corrected` | `[[MOD 答案]]` |
| 有 MOD，`＃` + 「答X或Y或XY者均給分」 | `corrected` | `[[X],[Y],[X,Y]]`，`score_policy: multi_answer` |
| 有 MOD，`＃` + 「答X或Y者均給分」 | `corrected` | `[[X],[Y]]`，`score_policy: multi_answer` |
| 有 MOD，`＃` + 「一律給分」 | `corrected` | `[]`，`score_policy: all_credit` |
| 僅 ANS，且 crawler 於 `mod_checked_at` 確認站方無 MOD | `original` | `[[ANS 答案]]` |
| 其他（含手動 oracle、未確認 MOD 存在與否） | `unverified` | `[[ANS 答案]]` |

`answer_status` 為整科一致（同科所有題目同值）。

### 4.5 正規化規則（決定性，不可由 LLM 執行）

| 項目 | 規則 |
|---|---|
| 疊印去重 | 抽取一律先 `page.dedupe_chars()`。113020 P1 以同位置重複繪字做假粗體（題幹強調字、表頭），不去重會產生 `C-1144`（原文 `C-14`）、`lliiootthhyyrroonniinnee` 等**靜默數值錯誤**；題數與選項數仍正確，結構性 AC 抓不到 |
| CJK 相容漢字 | **僅** U+F900–FAFF、U+2F00–2FDF 逐字做 NFKC（實測約 65 處，如 列 U+F99C、度 U+FA01）；禁止全量 NFKC（會改動全形標點、①②） |
| 全形/半形 | 標點統一全形；英數字統一半形；答案 PDF 之 `ＡＢＣＤ` → `ABCD` |
| 題號 / 選項標記 | 實測格式：題號 `^{n}.`（依序遞增比對，防止題幹內數字誤判）；選項 `^[A-D].` |
| 空白 | 中文間空白移除；英文詞間保留單一空白 |
| 換行 | 題幹內軟換行合併為單一空白；表格式題幹保留 `\n` |
| 上下標 | **不還原**（D3）。113–114 已扁平化（`Ca2+`、`Na+`），無法決定性偵測，不逐題標記；115 起以字型大小 < 本文 0.8 倍判定，標 `script_chars` 並記錄 offset |

---

## 5. 管線架構

```
[1] discover   → 解析年度頁 option value，產出 exam_code × 類科 × 科目 清單（含 MOD 連結是否存在）
       ↓ manifest.json
[2] fetch      → 下載 Q / ANS / MOD 至 raw/，計算 SHA256，寫入 manifest（含 mod_checked_at）
       ↓ raw/{year_roc}/{exam_code}/*.pdf（進版控）
[3] parse      → pdfplumber 文字層抽取 + 規則式 parser；依題目版面範圍判定 has_figure 並裁切 PNG
       ↓ intermediate/*.json
[4] validate   → 試題 × ANS × MOD 交叉驗證（獨立來源），跑全部 AC
       ↓ data/questions.json、data/exams.json（canonical）
[5] render     → Markdown / CSV / Anki
       ↓ dist/
```

**設計原則**

1. **純規則式，無 LLM。** 解析失敗 → 該科/該年度 `parked`，不補救。
2. **獨立來源交叉驗證。** 試題、ANS、MOD 三份 PDF 互為 oracle：題數不等、題號集合不等、ANS/MOD 非更正題不一致 → 直接失敗。
3. **raw PDF 進版控。** 僅 crawler 產物進 `raw/`；手動下載檔置於 `oracle/manual/`（gitignore），僅作 M1 驗證基準（D5）。
4. **`sys.exit(1)`** 於所有 `except` 區塊，確保 GitHub Actions 失敗可見。
5. **冪等。** 裁切 PNG 固定 DPI；JSON 輸出固定 key 順序、`ensure_ascii=False`、固定縮排。
6. 前端渲染一律 `textContent`，無 `innerHTML`。

### 5.1 圖片題判定（D4）

- 題目版面範圍：題號行 top ～ 下一題題號行 top（跨頁則分段）。
- 範圍內存在任一 image 物件 → `has_figure: true`。
- `figure_refs`：依範圍裁切整題頁面為 PNG（固定 DPI），不抽取個別 image 物件（113020 P1 單檔 5,425 個碎片物件）。

---

## 6. 驗收條件（CI-bound）

每項對應一個 pytest 測試，CI 未全綠不得 merge。

| ID | 驗收條件 | 失敗處置 |
|---|---|---|
| AC-1 | 每科解析題數 == 答案 PDF 表頭「題數」== 答案表題號數 | FAIL |
| AC-2 | 每題選項鍵集合 == `{A,B,C,D}`；選項文字為空僅允許於 `has_figure: true` 且該選項範圍內有 image 物件 | FAIL |
| AC-3 | `accepted_answers` 每個集合元素 ∈ `{A,B,C,D}`；`[]` 僅允許於 `score_policy == "all_credit"` | FAIL |
| AC-4 | `id` 全域唯一 | FAIL |
| AC-5 | 連續執行兩次 `parse+validate`，輸出（含 PNG）SHA256 相同 | FAIL |
| AC-6 | release build 中 `verified == false` 的題目數 == 0 | FAIL |
| AC-7 | `stem` 與 `options` 通過正規化檢查（無殘留全形英數、無雙空白、無 U+F900–FAFF / U+2F00–2FDF）；空選項依 AC-2 條件豁免 | FAIL |
| AC-8 | release build 中 `answer_status == "unverified"` 為 0，且不含考後未滿 90 天之考試 | FAIL |
| AC-9 | 每題 `source.*_sha256` 對應之 raw 檔存在且雜湊相符 | FAIL |
| AC-10 | 抽樣 20 題（其中 ≥5 題 `has_figure`）人工比對 PDF 原文，字元級一致 | 手動閘門，每次新增考試執行 |
| AC-11 | ANS 與 MOD 並存時：非 `＃` 題答案逐題相同；`＃` 題號集合 == MOD 備註中題號集合；備註每句均可被 §4.4 句型解析 | FAIL |
| AC-12 | 每科 PDF 表頭科目名稱可精確對應 `subjects.json`；試題 PDF 與答案 PDF 表頭考試名稱一致 | FAIL |
| AC-13 | 疊印回歸：113020 P1 第 54 題 stem 含 `C-14` 且不含 `C-1144`；parse 必經 `dedupe_chars()`（每科記錄去重字元數於 intermediate，供 diff 追蹤） | FAIL |

---

## 7. 目錄結構

```
taiwan-pharmacist-exam-data/
├── README.md                 # 含來源聲明與授權
├── CLAUDE.md                 # ≤40 行，僅寫無法從程式碼推斷者
├── CHANGELOG.md
├── spec.md                   # 本文件
├── pyproject.toml            # uv 管理
├── subjects.json             # 科目對照（D2）
├── src/
│   ├── discover.py           # 端點契約集中於此
│   ├── fetch.py
│   ├── parse.py
│   ├── normalize.py          # 正規化規則，純函式
│   ├── validate.py
│   └── render/{markdown,csv,anki}.py
├── tests/                    # AC-1 ~ AC-9、AC-11 ~ AC-13
├── raw/{year_roc}/{exam_code}/   # crawler 產物（進版控）
├── oracle/manual/            # 手動下載檔（gitignore，M1 驗證後可刪）
├── data/
│   ├── questions.json        # canonical
│   ├── exams.json
│   └── figures/              # 整題裁切 PNG
├── dist/                     # 衍生格式（gitignore，由 CI 產出）
└── .github/workflows/sync.yml
```

`progress.md` / `plan.md` **不進版控**。

---

## 8. 自動化

| 項目 | 設定 |
|---|---|
| 觸發 | GitHub Actions cron，每月 1 日 + `workflow_dispatch` |
| 行為 | (1) `discover` 比對 `manifest.json`，發現新 `exam_code` → 全管線；(2) **重新檢查 180 天內之考試是否新增 MOD** → 有則更新答案（D6）；兩者皆開 PR，**不自動 merge** |
| Release 閘門 | 考後未滿 90 天之考試不進 release build |
| 人工閘門 | PR 需通過 AC-10 抽樣比對後方可 merge |
| 失敗 | `sys.exit(1)`；Actions 紅燈即為通知 |

---

## 9. 里程碑

| M | 內容 | 出場條件 | 狀態 |
|---|---|---|---|
| **M0** | Parser 可行性探針 | 文字層、題號/選項命中率、圖片題佔比 | ✅ 完成（見 §9.1） |
| M1 | `discover` + `fetch` + manifest | 5 場（113-1 ~ 115-1）全部 Q/ANS/MOD 下載；**SHA256 與 `oracle/manual/` 全數相符**；H1 解決 | — |
| M2 | `parse` + `normalize` + `validate` | AC-1~AC-9、AC-11~AC-13 全綠（5 場）；可先以 oracle 為夾具與 M1 平行 | — |
| M3 | `render` 三格式 | Markdown/CSV/Anki 均由 canonical JSON 產出且可 round-trip 驗證 | M2 |
| M4 | 回填 + GitHub Actions | 110–112 逐年嘗試，未達 100% 者標 `parked`（不設數量下限）；cron 正常；CHANGELOG 建立 | M3 |

### 9.1 M0 結果（2026-09-25，oracle/manual 5 場 30 科）

| 指標 | 結果 |
|---|---|
| 文字層字元 | 每科 6.6k–13.7k；`(cid:)` 0；PUA 0 |
| 題數命中 | 30/30 科 == 答案 PDF（P1–P5 80 題、P6 50 題；合計 2,300 題） |
| 選項 ABCD 結構 | 2,300/2,300 |
| 圖片選項（空選項文字） | 約 45 題，集中於 P1、P2 |
| CJK 相容漢字 | 約 65 處 |
| 上下標 | 113–114 扁平化；115 有小字型字元約 200 個 |
| 疊印假粗體 | 全部試題 PDF 首頁表頭；題幹內僅 113020 P1（216 字元）→ 須 `dedupe_chars()` |
| 科目對應 | 經去重 + 相容漢字正規化後 63/63 PDF 表頭精確對應 `subjects.json`（未正規化時 11 份失配，如 行 U+FA08、理 U+F9E4） |
| 更正答案 | 19/30 科有 MOD；114090 三科 ANS+MOD 並存供 A1 驗證 |

→ 判定：**純規則式路線**。

---

## 10. 風險登錄

| 風險 | 影響 | 機率 | 緩解 |
|---|---|---|---|
| MOD 端點不明（H1） | 無法自動取得更正答案 | 中 | M1 以 oracle SHA256 反推；未解則 `answer_status` 全為 `unverified`，AC-8 阻擋 release |
| 更正晚於 90 天公告（H2） | 已發布之初版答案錯誤 | 低 | 180 天 MOD 複查 + PR；H2 以歷年公告日期驗證 |
| MOD 備註新句型（H3） | 答案語意解析錯誤 | 低 | AC-11 FAIL，不靜默 |
| 站方改版／端點變更 | 管線中斷 | 中 | 端點契約集中於 `discover.py`；CI 紅燈 |
| Session 狀態導致取得錯誤考試 | 資料錯置（手動下載已發生一次） | 中 | 回應 code 驗證 + AC-12 表頭比對 |
| 爬取被視為濫用 | 存取受限 | 低 | 1.5s 節流、辨識性 User-Agent、月頻、raw 進版控 |
| 跨年度格式漂移（110–112） | 舊年度解析失敗 | 高 | 逐年加入；失敗標 `parked`，不以 LLM 補救 |
| 扁平化上下標歧義（如 `10-15`） | 下游誤讀數值 | 中 | 不改寫；`exams.json` 標 `text_fidelity`，README 明示 |
| 下游應用改寫題幹 | 違反站方引用聲明 | 中 | README 明列使用條款；JSON 內嵌 `source` 使改寫可被偵測 |

---

## 11. 決策紀錄（2026-09-25 需求確認）

| # | 決策 | 理由 |
|---|---|---|
| D1 | `accepted_answers` 為答案集合陣列；`answer_raw_note` 逐字保留 | 「答A或B」與「答A或B或AB」語意不同，單一陣列無法區分 |
| D2 | 自訂 `P1`–`P6`；官方代碼僅存 `source` | 檔名科目碼、試題代號皆跨年變動 |
| D3 | 上下標不還原，僅標記證據 | 還原即改寫；`10-15` 等歧義無法決定性判斷 |
| D4 | 圖片題納入 release，整題裁切 | 排除會使 P1 系統性缺題；裁切為忠實呈現 |
| D5 | 手動下載檔僅作 M1 oracle，不進版控 | 無 URL/擷取時間，無法滿足 G2 |
| D6 | `original` 須 crawler 確認無 MOD；180 天複查；90 天 release 閘門 | 寧可延遲發布，不發布將被更正之答案 |
| D7 | v1 release 限 113 年起 | 以實測格式範圍為準，不為湊年數放寬驗證 |

---

## 12. 下一步

1. `/codex-checkplan` 覆審本規格。
2. M1（crawler，解 H1）與 M2（parser，以 `oracle/manual/` 為夾具）平行啟動。

---

> 資料來源：考選部考畢試題查詢平臺（https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx）。
> 引用時請註明資料來源並確保資料之完整，不得任意增刪。
