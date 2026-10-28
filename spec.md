# spec.md — `taiwan-pharmacist-exam-data`

**考選部藥師國考題庫結構化管線**

| 項目 | 內容 |
|---|---|
| 版本 | v0.7（頁面 revision 新增條件：subject_list digest 限藥師科目列） |
| 日期 | 2026-09-25 |
| Owner | liangRXdev |
| Tool tier | **L1**（有臨床/教學使用者，非劑量輸出）→ 需 `README.md` + `CLAUDE.md` + `CHANGELOG.md` |
| 授權 | 程式碼 MIT；題目資料 Public Domain（著作權法 §9 I ⑤）；自加標註 CC BY 4.0 |
| 狀態 | M0 通過 → 純規則式路線；核心契約（§4.6–§4.8、§5.3）凍結後啟動 M1/M2 |

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

錯誤答案在練習型應用中會被**反覆增強**，其危害高於「沒有題庫」。本專案的核心價值是 **可重現性（reproducibility）與可稽核性（auditability）**。

M0 實測佐證：5 場考試 30 科中 19 科有更正答案（MOD）；且已實際發生兩起靜默錯誤（session 狀態致重複考試、疊印假粗體致 `C-14` → `C-1144`），兩者皆可通過純結構檢查。

---

## 2. 目標與非目標

### 2.1 目標（v1）

| ID | 目標 |
|---|---|
| G1 | 從考選部考畢試題平台自動擷取藥師國考測驗式試題、初版答案（ANS）與更正答案（MOD） |
| G2 | 產出 canonical JSON 題庫，每題可追溯至不可變之來源 revision（URL、SHA256、擷取時間） |
| G3 | 提供衍生格式：Markdown、CSV、Anki `.apkg`（投影自 canonical，非獨立來源） |
| G4 | **compile 決定性**：相同 snapshot（`raw/` + `manifest.json` + `inputs/`）+ 相同 `release_date` + 相同 commit（含 `uv.lock`、鎖定之 Python 版本）+ 相同 CI runner 映像 → canonical、figures、dist 全部 byte-identical。**不承諾跨作業系統**。acquire（線上同步）不承諾決定性，其產物為帶觀測時間之新 revision |
| G5 | release 資格於 compile 時計算（§5.4），不信任任何儲存之布林值 |
| G6 | v1 release 範圍：**113 年起至最新一場**；範圍內每場應完整含 P1–P6（缺者須明列於 parked） |

### 2.2 非目標（v1 明確排除）

| ID | 非目標 | 理由 |
|---|---|---|
| N1 | 生成題目詳解／解析 | 屬 LLM 生成內容；留待 v2 獨立欄位 |
| N2 | 遊戲／測驗前端 | 本專案僅為資料層 |
| N3 | 申論式試題 | 藥師國考六科均為測驗式 |
| N4 | 其他職類 | 架構可擴充，v1 只驗證藥師 |
| N5 | 圖片題的圖形內容抽取 | 僅標記 `has_figure` 並保留整題裁切影像 |
| N6 | 上下標還原 | 屬改寫題幹；v1 只標記證據（D3） |
| N7 | 科目次分類（ATC、章節） | 自建標註，若做須置於獨立 `annotations.json` |
| N8 | LLM fallback | 解析失敗 → `parked`，不補救 |
| N9 | 110–112 年進入 `data/` 或 release | 僅相容性探索（M4），產物為探索報告與 parked 記錄 |
| N10 | 自動擷取 `exam_date` | 站方無結構化日期端點；人工填入附來源 URL（§4.2） |

---

## 3. 資料來源契約

### 3.1 端點

| 用途 | URL 樣式 | 狀態 |
|---|---|---|
| 年度考試清單 | `GET /exam/wFrmExamQandASearch.aspx?y={西元年}` | 已實測 |
| 科目清單 | `GET /exam/wFrmExamQandASearch.aspx?y={西元年}&e={exam_code}` | 已實測 |
| 試題 PDF | `GET /exam/wHandExamQandA_File.ashx?t=Q&code={exam_code}&c={類科}&s={科目}&q=1` | 已實測 |
| 單科答案 PDF（ANS，初版） | `GET /exam/wHandExamQandA_File.ashx?t=S&code={exam_code}&c={類科}&s={科目}&q=1` | 已實測 |
| 更正答案 PDF（MOD） | `GET /exam/wHandExamQandA_File.ashx?t=M&code={exam_code}&c={類科}&s={科目}&q=1` | ✅ 已實測（H1 解決）；無更正時回 302 |
| 全考試標準答案 | `GET /exam/wHandExamQandA_File.ashx?t=A&code={exam_code}` | 已實測（未使用） |
| 考試期日 | `GET https://wwwc.moex.gov.tw/main/exam/wFrmExamDetail.aspx?c={exam_code}` | 人工核對 `exam_date` 之來源（N10） |

Base：`https://wwwq.moex.gov.tw`

**頁面結構（2026-09 實測）**：年度頁含全年所有考試之完整三層結構（`td.level1` 考試 → `td.level2` 類科 → 科目列）；科目列以 `input#…chk_{code}_{c}_{s}` 標識，含 3 個 `td.exam-question-ans`（依序 Q／S／M），**無更正答案時 M 格存在但 `<a>` 無 href**（positive control 依據）。每列另有手機版重複連結，只讀桌機版。科目頁（`e=`）只含該場；**無效 code 回傳整份年度頁（HTTP 200）**，故以「頁面只含請求之 code」判定有效。每次回應之 `__VIEWSTATE`／`__EVENTVALIDATION` 皆不同。

實測 universe（2026-09-25）：`113020`、`113090`、`114020`、`114090`、`115020`、`115090`（6 場 36 科；115090 不在手動 oracle 內，僅為觀察，**不得據以枚舉**）。

### 3.2 已知約束（實測）

| 約束 | 說明 | 因應 |
|---|---|---|
| `exam_code` 不可枚舉 | 無效 code 會 redirect 回上一個有效 code，不回 404 | 必須解析 `<select>` 的 `option value`；**禁止**猜測式枚舉 |
| 存在 session 狀態 | 跨請求沿用前次選擇（手動下載已因此取得重複檔） | 每次請求獨立、不帶 cookie；不跟隨 redirect；下載後以 PDF 表頭驗證身分（AC-12） |
| 站方原址替換 PDF | 實測 9 份試題 PDF 被重新產生（Chrome/Skia → Word，內容相同）；114020 P3 MOD 於 2025-03-13 發布後，**2025-04-02 再追加第 73 題一律給分** | raw 不可變 + append revision；M1 oracle 比對分三類（§9） |
| 網路資源限制 | 站方明示 | 逐檔下載，請求間 `sleep(1.5s)`，辨識性 `User-Agent` 含聯絡資訊 |
| 引用聲明 | 註明來源、確保完整、不得增刪 | README 與每份輸出檔頭嵌入來源聲明；禁止任何題幹改寫 |
| 官方代碼不穩定 | 檔名科目碼跨年變動且同場重複（113090 有兩個 `11`）；試題代號 113-1→113-2 變動（調劑 4306→1306） | 自訂 `P1`–`P6`（D2），官方代碼僅存 `source` |
| 下載檔名截斷 | 如 `藥物分析與生藥學(含.pdf` | 科目身分以 PDF 表頭為準 |

### 3.3 假設狀態

| ID | 假設 | 狀態 | 依據 / 驗證方法 |
|---|---|---|---|
| A1 | 更正後最終答案之來源 | ✅ 已解 | 114090 三科 ANS+MOD 並存：MOD 表頭「測驗題標準答案更正」，僅 `＃` 題與 ANS 不同 |
| A2 | 試題 PDF 具文字層 | ✅ 成立，**但有例外** | pdfminer 對 113020 P1 之符號字型圈號（PUA U+F00D–F012，18 字）**完全不產生字元物件** → AC-16 |
| A3 | 題號／選項格式跨年度一致 | ✅ 成立（113–115） | 題號 `1.`、選項 `A.`；36 科 100% 命中 |
| H1 | MOD 取得方式 | ✅ 已解 | `t=M`；crawler 產物對 oracle：53 SHA256 相同、9 站方重新產生（內容相同）、1 站方較新 |
| H2 | 更正答案均於考後 90 天內公告 | 部分佐證 | 114020 P3：考後 53 天首次更正、73 天再次更正（皆 < 90）。其餘待累積 |
| H3 | MOD 備註僅有 §4.4 所列句型 | 36/36 句成立（23 份 MOD） | 新句型 → AC-11 FAIL |

---

## 4. 資料模型

所有 JSON：UTF-8、`ensure_ascii=False`、key 依本節定義順序、縮排 2、陣列順序依各欄位規定、結尾換行。欄位不存在一律 `null`（不省略、不用空字串）。

### 4.1 Canonical question object（`data/questions.json`）

```jsonc
{
  "id": "114-1-PHARM-P2-067",          // {year_roc}-{session}-PHARM-{subject}-{question_no:03d}；必須可反向解析且與欄位一致
  "exam_code": "114020",
  "year_roc": 114,
  "session": 1,
  "profession": "pharmacist",
  "subject": "P2",
  "stage": 1,                          // 由 subject 推導
  "question_no": 67,
  "stem": "…",                         // L2 文字（§4.7）
  "options": { "A": "…", "B": "…", "C": "…", "D": "…" },
  "accepted_answers": [["B"], ["C"], ["B", "C"]],
  "answer_status": "corrected",        // original | corrected | unverified
  "score_policy": "multi_answer",      // normal | multi_answer | all_credit
  "answer_raw_note": "第67題答B或C或BC者均給分",   // 該題對應之 MOD 備註子句逐字（L1）；無則 null
  "has_figure": false,
  "figure_refs": [],                   // 整題裁切 PNG 相對路徑，依頁序
  "empty_option_keys": [],             // 以圖形證據豁免之空選項鍵（§5.5）
  "flags": [],                         // 依字母排序；例："script_chars"
  "script_char_offsets": { "stem": [], "A": [], "B": [], "C": [], "D": [] },  // L2 文字之 Unicode code point offset，升冪
  "source": {
    "subject_file_code": "0402",
    "paper_code": "2305",
    "category_name": "藥師(一)",
    "subject_name_raw": "藥學(二)(包括藥物分析與生藥學(含中藥學))",
    "question_rev": "sha256:…",        // 指向 manifest revision
    "ans_rev": "sha256:…",             // 無 ANS → null
    "mod_rev": "sha256:…",             // 無 MOD → null
    "mod_page_rev": "sha256:…"         // answer_status == original 時必填：據以判定 absent 之科目頁 HTML revision
  }
}
```

**`accepted_answers` canonical 形狀**：集合內依字母升冪；集合之間依（長度，字典序）升冪；禁止重複元素與重複集合。

| `score_policy` | `accepted_answers` 唯一合法形狀 |
|---|---|
| `normal` | 恰一個 singleton，如 `[["B"]]` |
| `multi_answer` | ≥2 個互異非空集合，且恰等於 §4.4 句型展開結果 |
| `all_credit` | 恰為 `[]` |

**`answer_status` 與來源欄位**：

| 來源組合 | `answer_status` | 答案取自 |
|---|---|---|
| MOD 存在（`mod_rev` 非 null） | `corrected` | MOD |
| 僅 ANS，且 tuple 之 `mod_page_rev` 經 compile 重算為 `absent` 並符合 90 天條件（§4.6） | `original` | ANS |
| 僅 ANS，其他情況 | `unverified` | ANS |
| 無 ANS 且無 MOD | 不產生題目；該科 `parked`（reason `answer_missing`） | — |

`answer_status` 整科一致。

### 4.2 考試層級物件

**輸入** `inputs/exams.json`（人工維護，屬 snapshot，compile 不得寫入、AC-5 不得刪除）：

```jsonc
{
  "exam_code": "114020",
  "exam_date": "2025-02-08",           // 最後一天考試日，Asia/Taipei
  "exam_date_source_url": "https://…", // 考選部考試日程公告
  "exam_date_source_quote": "…"        // 審查者自來源頁逐字摘錄之日期文字（MG-1 核對項）
}
```

**輸出** `data/exams.json`（compile 產物，可刪除重建）＝ 輸入全部欄位 + compile 推導欄位：`year_roc`、`session`、`text_fidelity: { "scripts": "flattened" | "size_encoded" }`（由 L0 是否存在小字型字元判定）。

discovery 出現之 `exam_code` 在 `inputs/exams.json` 無對應 → 該場全部 tuple `withheld:[exam_date_missing]`。

### 4.3 `subjects.json`（跨年度科目對照）

| 代碼 | 114 年起名稱 | 113 年舊名 | stage |
|---|---|---|---|
| P1 | 藥學(一)(包括藥理學與藥物化學) | 藥理學與藥物化學 | 1 |
| P2 | 藥學(二)(包括藥物分析與生藥學(含中藥學)) | 藥物分析與生藥學(含中藥學) | 1 |
| P3 | 藥學(三)(包括藥劑學與生物藥劑學) | 藥劑學與生物藥劑學 | 1 |
| P4 | 藥學(四)(包括調劑學與臨床藥學) | 調劑學與臨床藥學 | 2 |
| P5 | 藥學(五)(包括藥物治療學) | 藥物治療學 | 2 |
| P6 | 藥學(六)(包括藥事行政與法規) | 藥事行政與法規 | 2 |

對應以 PDF 表頭「科目名稱」之 L1 文字，經相容漢字正規化、去除 `(試題代號：…)` 後精確比對；比對不到 → FAIL（不做模糊比對）。

### 4.4 MOD 備註句型（決定性，窮舉）

| 句型（L1，經相容漢字正規化） | 展開 |
|---|---|
| `第{n}題答{X}或{Y}或{XY}者均給分` | `[[X],[Y],[X,Y]]`，`multi_answer` |
| `第{n}題答{X}或{Y}者均給分` | `[[X],[Y]]`，`multi_answer` |
| `第{n}題一律給分` | `[]`，`all_credit` |

多句以 `，` 分隔。備註全文必須被上述句型**完全消耗**（無殘餘字元）；任一殘餘 → FAIL。

### 4.5 正規化規則 T（決定性，L1 → L2）

| 項目 | 規則 |
|---|---|
| CJK 相容漢字 | **僅** U+F900–FAFF、U+2F00–2FDF 逐字 NFKC；禁止全量 NFKC |
| 全形英數 | 全形英數（U+FF10–19、FF21–3A、FF41–5A）→ 半形；答案 PDF `ＡＢＣＤ` → `ABCD`。**標點不轉換**（v0.5：半形 `,` 轉全形會破壞 `10,000` 等數值，原規則「標點統一全形」刪除） |
| 控制字元 | Unicode Cc（`\n` 除外）移除。實測 Word 殘留不可見 U+0081 夾於題幹與①之間，渲染無字形 |
| 空白 | 連續空白（含 U+3000、NBSP、Tab）折疊為一；**僅兩側皆為非空白 ASCII 時保留**，其餘（中文間、中英交界）移除 |
| 上下標 | **不還原**（D3）。115 起以字型大小 < 本文 0.8 倍判定，記錄 L2 offset |

T 逐字元 1→1（除空白折疊與控制字元移除），故 small 旗標可隨字元移動。T 必須冪等：`T(T(x)) == T(x)`。T 以外之任何字元變更均為違規。

### 4.5.1 L1 組行與切分（決定性，屬 L1 定義）

| 項目 | 規則 |
|---|---|
| 組行 | 本文字型字元以「垂直重疊 > 字高 50%」聚為一行；小字型字元（< 本文 0.8 倍）併入垂直重疊最多之本文行，再依 x 排序。**不使用** `extract_text_lines`：115 年下標以略低 baseline 排版，會被切成獨立一行並排到本行之後（`β₂ receptor` → `β receptor … 2`） |
| 詞間空白 | (1) 有空白 glyph：丟棄之條件為「glyph 起點深入前一字元 > 1pt **且** 前後可見字元視覺間距 < 1pt」，其餘保留。Word 2013/2021 產出之 PDF 在清單標記後第一字元處放一個重疊空白（`A.g uanylyl` 實為 `A.guanylyl`，`a spirin` 實為 `aspirin`）；斜體學名之空白視覺間距 ≈ 0 但未重疊（`Streptococcus pneumoniae`）必須保留。(2) 無空白 glyph：視覺字距 ≥ 2pt 推定為空白（Skia 產出之 PDF 常省略空白 glyph）。規則依據為 2026-09 對全部 36 份試題 PDF 之空白 glyph 分類統計與渲染比對 |
| 題號 | 行首 `{n}.`，n 必須等於下一個預期題號，**且行首 x 位於全文件最左邊界 +2pt 內**（題幹續行與選項皆為懸掛縮排，實測縮排 ≥ 10pt）。不限制 `.` 後字元（題幹可為 `14.25℃時…`、`2.57歲女性…`） |
| 選項 | 行首 `{K}.`，K 必須等於下一個預期選項；同行內以「空白 + 下一個 K.」切出後續選項；標記本身不進 L2 |
| 行接合 | 前一行右端 ≥ 版心右界 − 2 × 本文字級 → 軟換行：兩側為 ASCII 非連字號與 ASCII 英數時補一空白，否則直接接合；否則硬換行，保留 `\n` |
| 首題前 | `※` 開頭 → `instruction`，其餘 → `header` |

### 4.6 `manifest.json`（acquire 產物，核心狀態）

manifest 只記錄**觀測到什麼、存在哪裡**；所有「判定」（universe、MOD 有無、positive control）由 compile 從不可變的 HTML／PDF snapshot 重新計算，manifest 不存判定結果或布林值。

```jsonc
{
  "schema_version": 1,
  "pages": [                                   // 所有抓過的 HTML 頁面；依 rev 排序；append-only
    {
      "rev": "sha256:…", "role": "year_list",  // year_list（y=）| subject_list（y=&e=）
      "url": "…", "fetched_at": "…", "http_status": 200, "final_url": "…",
      "content_digest": "sha256:…",            // 僅供「是否變更」判斷，見下方「頁面 revision 新增條件」
      "raw_path": "raw/pages/{sha8}.html"
    }
  ],
  "discovery": {                               // 當前 discovery 所依頁面
    "year_list_revs": { "2024": "sha256:…", "2025": "sha256:…", "2026": "sha256:…" },  // 西元年 → year_list 頁
    "subject_list_revs": { "114020": "sha256:…" }                                        // exam_code → 當前 subject_list 頁
  },
  "tuples": [                                  // 依 (exam_code, subject) 排序；(exam_code, subject) 唯一
    {
      "exam_code": "114020", "subject": "P2",
      "category_code": "…", "subject_file_code": "0402",
      "revisions": [                           // append-only；依 (fetched_at, rev) 升冪
        {
          "rev": "sha256:…", "kind": "Q",      // Q | ANS | MOD
          "url": "…", "fetched_at": "…",
          "raw_path": "raw/114/114020/P2_Q_{sha8}.pdf"
        }
      ],
      "current": { "Q": "sha256:…", "ANS": "sha256:…", "MOD": null },
      "mod_page_rev": "sha256:…",              // 最近一次為 MOD 檢查所抓之 subject_list 頁
      "parked": null                           // 或 { "reason": "parse_fail", "stage": "acquire|compile", "detail": "…", "since": "…" }
    }
  ]
}
```

**不變量（AC-9 驗證）**：
- `current.Q` 必填；每個非 null `current.{kind}` 在同 tuple `revisions` 中恰有一筆且 `kind` 相符。
- `rev` 在整份 manifest 唯一；`raw_path` 存在且 SHA256 == `rev`。
- `revisions` 依 (fetched_at, rev) 升冪。
- `discovery` 引用之每個 rev 皆存在於 `pages`。

**Universe（compile 重算）**：解析 `discovery.year_list_revs` 所指頁面之 `<select>` option，取民國 113 年起、其 subject_list 頁含類科「藥師」之 `exam_code`；universe ＝ 該集合 × {P1..P6}。`tuples` 必須與 universe **完全相等**（AC-0）。任一 year_list 頁缺失或無法解析 → 整次 compile FAIL，不得以部分 universe 繼續。

**MOD 判定（compile 重算，依 H1 定案之規則）**：對 `mod_page_rev` 所指頁面：
- `present`：頁面含該科 MOD 連結 → 必須有 `current.MOD`，否則 FAIL。
- `absent`：以下全成立——`http_status == 200`；`final_url` 之 code == 該 `exam_code`；**positive control**：同頁同科 Q 連結可解析，且其參數與 `current.Q` 之 URL 相同；頁面不含該科 MOD 連結。
- 其他一律 `inconclusive`。**404、空頁、解析不到任何連結皆非 `absent`。**
- `original` 條件：判定為 `absent`，**且** 該頁 `fetched_at ≥ exam_date + 90 天**（更正窗口已過）。只看 `mod_page_rev`（最新一次），較舊的 `absent` 不得沿用。

**頁面 revision 新增條件**：重抓之頁面與當前 rev 比對，下列任一成立才 append 新 page revision，否則沿用當前 rev：
- `content_digest` 不同。subject_list 頁之 digest 只涵蓋該場考試名稱與**藥師科目列**之解析結果（compile 之 MOD 判定與身分比對只讀這些）；年度考試下拉選單、同場他類科之變動不計。區塊解析失敗退回整頁比對。year_list 頁去除 ASP.NET 隱藏欄位後整頁比對。
- `http_status` 或 `final_url` 不同。
- 跨更正窗口：當前 rev 抓於 `exam_date + 90` 之前、今日已過（D12）。

當前 rev 之 digest 一律由其 raw 重算，不讀 manifest 欄位，digest 定義變更不致整批換 rev。理由：subject_list rev 即 MG-1 `revs.mod_page`，無關變動換 rev 會使人工審查全數 `mg1_stale`（2026-10-28 實例：年度選單新增 115111／115150）。

**raw 不可變**：PDF 與 HTML 皆內容定址；同一 (tuple, kind) 出現新 hash → append revision、更新 `current`、PR 明示差異；舊檔保留，禁止覆寫。

**parked 生命週期**：每個 tuple 至多一筆**當前** `parked`；問題解除後設回 `null`，歷史由 Git 保留。reason code：`fetch_fail`、`identity_mismatch`、`parse_fail`、`answer_missing`、`note_unparsed`、`format_drift`、`text_layer_loss`（AC-16）。compile 階段新產生之 parked 寫入 `release/coverage.json`（compile 不寫 manifest）。

**PR 觸發**：僅在 revision 新增、`mod_page_rev` 之判定結果改變、`parked` 改變，或某 tuple 首次滿足 `original` 條件時開 PR；判定未變之月度重抓不開 PR（HTML 仍存入 `raw/pages/`，於下次有變更之 PR 一併提交）。

### 4.7 文字層次與字元歸屬

| 層 | 定義 | 用途 |
|---|---|---|
| L0 | pdfplumber 原始 `page.chars` | 疊印證據、風險標籤偵測 |
| L1 | `page.dedupe_chars()` 後之字元 | 表頭身分、MOD 備註、MG-1 比對基準 |
| L2 | `T(L1)` | canonical `stem`/`options` |

**字元歸屬契約**：每頁每個 L1 字元必須恰歸屬下列之一，記錄於 intermediate：
- `q:{n}:stem`
- `q:{n}:opt:{K}`
- `q:{n}:marker`（題號／選項標記）
- 排除類別：`header`（首頁表頭區）、`instruction`（`※` 開頭之注意事項）、`page_footer`（頁碼、`請接背面`、`背面尚有試題` 等，窮舉於 parser 設定）

未歸屬或重複歸屬之字元 → 該科 `parse_fail`。L0→L1 被移除字元清單（字元、頁、座標）一併記錄。

### 4.8 `release/`（compile 產物）

- `release/questions.json`：eligible 題目（§5.4）
- `release/coverage.json`：

```jsonc
{
  "release_date": "2026-09-25",
  "tuples": [                                  // 與 universe 一一對應，依 (exam_code, subject) 排序
    {
      "exam_code": "114020", "subject": "P2",
      "status": "released",                    // released | parked | withheld
      "reasons": [],                           // 排序陣列；released 時為 []
      "revs": { "Q": "sha256:…", "ANS": "sha256:…", "MOD": null, "mod_page": "sha256:…" }
    }
  ]
}
```

- `parked` reasons：§4.6 reason code（acquire 或 compile 產生）
- `withheld` reasons（可多個）：`too_recent`、`unverified`、`exam_date_missing`、`mg1_missing`、`mg1_stale`、`mg1_pending`、`mg1_failed`
- `status` 優先序：`parked` > `withheld` > `released`

---

## 5. 管線架構

```
━━ acquire（線上，非決定性；只「觀測並保存」，不做判定）━━
[1] discover   → 抓 year_list、subject_list HTML 存入 raw/pages/，更新 manifest.discovery 與各 tuple 之 mod_page_rev
[2] fetch      → 下載 Q / ANS / MOD，驗證表頭身分，append revision、更新 current
       ↓ snapshot = raw/ + manifest.json + inputs/
━━ compile（離線，決定性；輸入僅 snapshot + release_date）━━
[3] derive     → 自 HTML 重算 universe 與 MOD 判定；自 PDF 重算表頭身分
[4] parse      → L0 → L1 → 字元歸屬 → L2；版面範圍、圖形判定、裁切 PNG（僅讀 current revisions）
[5] validate   → 跑自動 AC
[6] eligible   → 計算 release 資格（§5.4）
[7] render     → data/、release/、dist/
```

**設計原則**

1. **純規則式，無 LLM。** 解析失敗 → 科目 `parked`。
2. **保證分四類，不互相替代。**
   - 來源身分：表頭 tuple 驗證（AC-12）
   - 結構一致：題數、題號集合（AC-1、AC-11）
   - 答案值：逐題來源值 == canonical（AC-14）
   - 文字忠實度：字元歸屬 + T 可證偽性（AC-7）+ 人工抽樣（MG-1）

   **結構檢查不能證明題幹字元忠實**（疊印案例即為反例）。
3. **acquire 只存證據，compile 做判定。** manifest 不存 universe、MOD 有無、positive control 等判定結果。
4. **raw 進版控且不可變**（§4.6）。手動下載檔置於 `oracle/manual/`（gitignore），僅作 M1 驗證基準。
5. **`sys.exit(1)`** 於所有 `except` 區塊。
6. **compile 不讀網路、不讀系統時間、不依賴前次產物、只讀 `current` revisions**；`release_date` 為必填參數。

### 5.1 時間語意

- 時區：Asia/Taipei；日期比較以日為單位。
- `age = release_date − exam_date`（天）。
- release 資格：`age ≥ 90`。
- `original` 答案：`mod_page_rev` 之 `fetched_at` 日期 ≥ `exam_date + 90`。
- MOD 複查範圍（acquire）：`age ≤ 180`，以 run 當日為 `release_date`。

### 5.2 端點結果分類（acquire）

| 類別 | 條件 | 行為 |
|---|---|---|
| success | HTTP 200、預期之 Content-Type、PDF 以 `%PDF-` 開頭且可開啟、表頭身分相符 | 寫入 revision／page |
| retryable | 逾時、429、5xx、連線錯誤 | 重試 3 次（指數退避）；仍失敗 → 本次 run 失敗，**不修改 manifest**，`sys.exit(1)` |
| unusable | 非 PDF（HTML 偽裝）、截斷、表頭身分不符、redirect 至其他 code | 科目 `parked`（`fetch_fail`／`identity_mismatch`），`sys.exit(1)` |

subject_list 頁之非 200 或 redirect 仍存入 `pages`（保留證據），compile 會判為 `inconclusive`。

### 5.3 併發

- GitHub Actions 設 `concurrency: sync`，`cancel-in-progress: false`，序列化執行。
- sync PR 記錄其 base commit；base ≠ 當前 main → 視為衝突，關閉重跑，不自動 rebase。

### 5.4 Release 資格（compile 時計算）

題目 eligible ⇔ 以下全成立：

| # | 條件 | 不成立時 `coverage` |
|---|---|---|
| E1 | tuple ∈ universe，manifest 與 compile 均未 parked | `parked:[reason]` |
| E2 | tuple 全部自動 AC 通過 | `parked:[parse_fail…]` |
| E3 | `answer_status ∈ {corrected, original}` | `withheld:[unverified]` |
| E4 | `inputs/exams.json` 有該場且 `age ≥ 90` | `withheld:[exam_date_missing]` 或 `[too_recent]` |
| E5 | `review/{exam_code}.json` 存在、其 revs == 本次 compile 實際使用之 current revs、全部 pass | `withheld:[mg1_missing]`／`[mg1_stale]`（revs 或樣本集合不符）／`[mg1_failed]`（任一題 fail）／`[mg1_pending]`（無 fail 但有題未判定、缺審查者或缺日期摘錄） |

不符者整科列入 `coverage.json`，不得靜默缺漏。

### 5.5 圖形判定（D4）

- 題目版面範圍：題號行 top ～ 下一題題號行 top（跨頁分段）。選項範圍：該選項標記行 top ～ 下一選項標記（或題目範圍末端）。
- 圖形物件：`image`、`curve`、`line`、`rect`，**排除高度 ≥ 頁高 50% 之物件**（實測每頁皆有一條貫穿頁框線）。
- 題目範圍內有任一圖形物件 → `has_figure: true`。
- 選項文字為空之豁免：該**選項自身範圍**內有圖形物件，並列入 `empty_option_keys`。
- `figure_refs`：依題目範圍裁切整題頁面 PNG（DPI 150；renderer 版本由 `uv.lock` 鎖定），不抽取個別物件。
- M0 實測：105 題範圍內有 image 物件；2 題僅有向量物件（113090 P3 第 66 題、114090 P3 第 8 題）。

---

## 6. 驗收條件

### 6.1 自動 AC（pytest，CI 未全綠不得 merge）

每條皆須附**反例 fixture**：注入違規資料時該測試必須 FAIL。

| ID | 可證偽斷言 | 必備反例 fixture |
|---|---|---|
| AC-0 | compile 自 `discovery` 所指 HTML 重算之 universe 非空，且 == manifest `tuples` 之 (exam_code, subject) 集合；`coverage.json` 之 tuple 集合 == universe | 刪除一科；**刪除整場六科**；**漏掉最新一場**（HTML 有、tuples 無）；重複一科；year_list 頁缺失 |
| AC-1 | 每個非 parked tuple：答案 PDF 表頭題數 N > 0；試題題號集合 == 答案題號集合 == `{1..N}` | 題數 0、漏第 k 題、重複第 k 題 |
| AC-2 | 每題選項標記 A→B→C→D 各恰一次且依序、皆位於該題範圍內；L2 選項文字非空，除非該鍵 ∈ `empty_option_keys` 且該選項自身範圍內有圖形物件 | 空選項但圖在他選項；選項順序錯；選項跨入下一題 |
| AC-3 | `(score_policy, accepted_answers)` 符合 §4.1 真值表與 canonical 形狀 | `[[]]`、`normal` 配多答、未排序、重複集合 |
| AC-4 | 每題 `id` 反向解析結果 == 各欄位；`id` 與 `(exam_code, subject, question_no)` 一對一 | ID 與 question_no 不一致、同 ID 兩題 |
| AC-5 | CI 上兩個全新 job（相同 runner 映像、相同 `uv.lock`）對同一 snapshot、同一 `release_date` 各自 compile：`data/`、`release/`、`dist/`、figures 全部檔案 SHA256 相同；`inputs/`、`raw/`、`manifest.json` 於 compile 前後 SHA256 不變 | 注入 `datetime.now()`、dict 無序輸出、`.apkg` zip 內含時間戳時 FAIL；compile 寫入 `inputs/` 時 FAIL |
| AC-6 | 以手寫 fixture（E1–E5 各一組：僅該條件不成立、其他皆成立）驗證 eligible 集合 == **手寫預期集合**，且 `coverage` reasons == 手寫預期；另驗 `release/questions.json` == eligible 集合 | 每個 E 條件逐項翻轉；手動刪一題 eligible 題；手動加入一題 unverified 題 |
| AC-7 | 字元歸屬契約（§4.7）：每個 L1 字元恰歸屬一次、無未歸屬；排除類別字元僅出現在其定義區域；每段 L2 == T(該段 L1)；T 冪等；stem 非空 | **L1 與 L2 同時截斷一段而 L0 不變**；某題幹字元被歸入 `page_footer`；T 以外改字（如 `mg`→`毫克`） |
| AC-8 | 於指定 `release_date`：release 不含 `age < 90` 之考試、不含 `unverified`；每個 `original` 題之 `mod_page_rev` 經重算為 `absent`，且其 `fetched_at` ≥ `exam_date + 90` | `age == 89`；`original` 但頁面 redirect；`original` 但 absent 觀測在考後第 60 天；positive control 之 Q 參數 ≠ `current.Q` |
| AC-9 | manifest 不變量（§4.6）全部成立；canonical 每個 `*_rev` == 該 tuple `current` 對應值（`mod_page_rev` == tuple `mod_page_rev`） | `current` 指向他 kind 或不存在之 rev；新增 current 後 canonical 仍指舊 rev；rev 重複 |
| AC-11 | 對**每個有 MOD 之科目**：MOD 答案表覆蓋 `{1..N}`；`＃` 題號集合 == 備註題號集合（無重複、越界、額外）；備註被 §4.4 完全消耗；若 ANS 並存：非 `＃` 題 ANS == MOD 逐題相同 | MOD-only 科目備註缺一句；備註多一題；ANS/MOD 非 `＃` 題不同；未知句型 |
| AC-12 | compile 自每個 current revision 之 PDF 表頭（L1）重算之考試名稱、類科、科目、試題代號 == tuple；同一 tuple 之 Q/ANS/MOD 表頭互相一致；所有 tuple 之 `current.Q` 互異 | 六科 Q 指向同一場；Q 屬 114020 但 tuple 記為 114090；ANS/MOD 互換 |
| AC-13 | 疊印：113020 P1 第 54 題 L2 含 `C-14` 且不含 `C-1144`；L0→L1 移除清單已記錄；**不同座標之合法相鄰重複字元（如 `C-11`、`ll`）不得被移除** | 未去重時 FAIL；以字串層級去重時合法重複被刪而 FAIL |
| AC-14 | 逐題答案值：`corrected` 非 `＃` 題 `accepted_answers == [[MOD 表值]]`；`＃` 題 == §4.4 展開結果；`original`／`unverified` 題 == `[[ANS 表值]]` | 改一題答案值但形狀、題數、provenance 全部合法；`＃` 題展開成他題之備註 |
| AC-15 | 回歸下限（以 **current revision** 為準）：113020 P1 L0→L1 移除字元數 == 696（首頁表頭 480 + 題幹 216），且 `dedupe` 偵測器於第 54 題觸發；`figure` 標籤題集合含 113090-P3-066（純向量圖）且總數 ≥ 100；`compat` 標籤涵蓋 ≥ 12 科；115020 六科皆有 `script` 標籤；八種風險標籤皆有成員。（114090 P3 第 8 題於 M0 之 oracle 版為帶框線配方表，站方替換後之現行版無框線，已不屬圖形題） | 風險偵測器全部回傳空集合時 FAIL |
| AC-16 | 文字層交叉驗證：以 pdfium 為第二抽取器，逐頁比對非空白字元（經相容漢字正規化、排除 Cc 與連字號變體）；任一方獨有之字元 → 該科 `parked:text_layer_loss`。113020 P1 必須被偵測（圈號 U+F00D–F012 遺失） | 自 L1 移除某字元全部出現；乾淨檔案必須無差異 |

### 6.2 人工閘門（manual gate）

| ID | 內容 | CI 驗證方式 |
|---|---|---|
| MG-1 | 每場一份 `review/{exam_code}.json`：（a）核對 `inputs/exams.json` 之日期與來源頁一致，摘錄 `exam_date_source_quote`；（b）以下演算法選出 20 題，逐題比對 PDF 視覺原文與 L2（預期差異僅限 T） | 證據檔存在；revs == 本次 compile 使用之 current revs；題目 ID 集合 == 以演算法重算之集合；每題有 pass/fail 與審查者 |

**MG-1 抽樣演算法（決定性）**：

1. 候選集合：該場全部題目，依 `id` 排序。
2. 風險標籤由 **L0 層偵測器**產生，不依賴 parser 分段結果：
   - `figure`：題目範圍內有圖形物件
   - `dedupe`：L0→L1 有移除
   - `compat`：含相容漢字
   - `script`：含小字型字元
   - `table`：範圍內有 ≥2 條水平線
   - `crosspage`：跨頁
   - `corrected`：`＃` 題
   - `edge`：各科第 1 題與最後一題
3. 貪婪覆蓋：依上列標籤順序，每個標籤若尚未被已選題覆蓋，選該標籤成員中 `sha256(seed + id)` 最小者。
4. 已選 > 20：依標籤順序保留至 20 題（每標籤至少一題優先）；< 20：自剩餘候選依 `sha256(seed + id)` 升冪補足。
5. `seed` = 該場六科 `current.Q` rev 依 subject 排序串接。
6. 某標籤於該場無成員 → 證據檔記錄「不適用」；AC-15 確保 v1 範圍內偵測器不會整體失效。

---

## 7. 目錄結構

```
taiwan-pharmacist-exam-data/
├── README.md / CLAUDE.md / CHANGELOG.md / spec.md
├── pyproject.toml + uv.lock  # uv 管理；Python 版本鎖定
├── subjects.json
├── manifest.json             # acquire 產物（§4.6）
├── inputs/exams.json         # 人工輸入（snapshot 一部分）
├── src/
│   ├── acquire/{discover,fetch}.py   # 端點契約集中於 discover
│   ├── build/{pdftext,qparse,apdf,crosscheck,derive,assemble,validate,eligible,run}.py   # 即 compile（避開 builtin 名稱）
│   └── render/{markdown,csv,anki}.py
├── tests/                    # AC-0 ~ AC-16 + 反例 fixtures
├── review/{exam_code}.json   # MG-1 證據
├── raw/
│   ├── pages/{sha8}.html     # discovery 與 MOD 判定證據（不可變）
│   └── {year_roc}/{exam_code}/{subject}_{kind}_{sha8}.pdf   # 不可變
├── oracle/manual/            # 手動下載檔（gitignore）
├── data/{questions,exams}.json + figures/   # compile 產物
├── release/{questions,coverage}.json         # compile 產物
├── dist/                     # 衍生格式（gitignore，CI 產出）
└── .github/workflows/sync.yml
```

---

## 8. 自動化

| 項目 | 設定 |
|---|---|
| 觸發 | cron 每月 1 日 + `workflow_dispatch`；`concurrency: sync` 序列化 |
| 行為 | acquire：(1) 重抓 year_list，發現新 `exam_code`；(2) 對 `age ≤ 180` 之考試重抓 subject_list 頁；符合 §4.6「PR 觸發」條件才 compile（`release_date` = run 當日 Asia/Taipei，寫入 PR 描述）並開 PR，**不自動 merge** |
| 人工閘門 | 新考試或 current revs 變更 → MG-1 證據須隨 PR 提交，否則該場 `withheld:[mg1_*]` |
| 失敗 | `sys.exit(1)`；Actions 紅燈即為通知 |

---

## 9. 里程碑

核心契約（§4.6 manifest／MOD 判定／raw revision／parked、§4.7 字元歸屬、§4.8 coverage、§5.4 release 資格）於 v0.4 凍結；變更須更新 spec 版本並記入修訂紀錄。cron 與衍生格式在後。

| M | 內容 | 出場條件 |
|---|---|---|
| **M0** | Parser 可行性探針 | ✅ 完成（§9.1） |
| M1 | acquire | ✅ 2026-09-25。universe 全部 Q/ANS/MOD 與 HTML 取得；每份 oracle 檔須落入三類之一：SHA256 相同／站方重新產生（字元多重集合相同）／站方較新（CreationDate 較晚，列出供人工確認）；雙方各自通過表頭身分驗證；H1 解決；manifest 通過 AC-9。實測 53／9／1 |
| M2 | compile | AC-0 ~ AC-16 全綠（universe 全部場次），每條反例 fixture 皆 FAIL |
| M3 | render | 每筆衍生記錄含 canonical `id`；規格指定之投影欄位（id、stem、options、accepted_answers、answer_status、score_policy、source 聲明）與 canonical 相等；不要求自衍生格式重建 canonical |
| M4 | 探索 + GitHub Actions | 110–112 逐年跑相容性探索，產出報告與 parked 記錄（不進 `data/`）；cron 正常；CHANGELOG 建立 |

### 9.1 M0 結果（2026-09-25，oracle/manual 5 場 30 科）

| 指標 | 結果 |
|---|---|
| 文字層字元 | 每科 6.6k–13.7k；`(cid:)` 0；PUA 0 |
| 題數命中 | 30/30 科 == 答案 PDF（P1–P5 80 題、P6 50 題；合計 2,250 題。v0.4 以前誤記為 2,300） |
| 選項 ABCD 結構 | 2,250/2,250 |
| 圖形 | 105 題範圍內有 image 物件；2 題僅向量物件；每頁一條貫穿頁框線須排除 |
| CJK 相容漢字 | 約 65 處 |
| 上下標 | 113–114 扁平化；115 小字型字元約 200 個 |
| 疊印假粗體 | 全部試題 PDF 首頁表頭；題幹內僅 113020 P1（216 字元） |
| 科目對應 | L1 + 相容漢字正規化後 63/63 PDF 表頭精確對應 `subjects.json` |
| 更正答案 | 19/30 科有 MOD；114090 三科 ANS+MOD 並存 |

---

## 10. 風險登錄

| 風險 | 影響 | 機率 | 緩解 |
|---|---|---|---|
| MOD 端點不明（H1） | 無法取得更正答案、無法判定 `absent` | 中 | 未解則所有 ANS-only 科目 `unverified`，AC-8 阻擋 |
| 更正晚於 90 天公告（H2） | 已發布初版答案錯誤 | 低 | 180 天複查 + PR |
| MOD 備註新句型（H3） | 答案語意錯誤 | 低 | AC-11 完全消耗檢查 → FAIL |
| 站方原址替換 PDF | provenance 斷裂 | 低 | raw 不可變 + append revision（§4.6） |
| 站方改版／端點變更 | 管線中斷 | 中 | 端點契約集中於 `discover.py`；CI 紅燈 |
| Session 狀態致錯置 | 資料錯置（已發生一次） | 中 | 回應 code 驗證 + AC-12 表頭與 Q 互異 |
| 爬取被視為濫用 | 存取受限 | 低 | 1.5s 節流、辨識性 UA、月頻 |
| 跨年度格式漂移 | 舊年度解析失敗 | 高 | 110–112 僅探索（N9） |
| 扁平化上下標歧義 | 下游誤讀數值 | 中 | 不改寫；`text_fidelity` + README 明示 |
| 下游改寫題幹 | 違反引用聲明 | 中 | README 使用條款；`id` + `source` 可偵測 |

---

## 11. 決策紀錄

| # | 決策 | 理由 |
|---|---|---|
| D1 | `accepted_answers` 為答案集合陣列，canonical 排序；`answer_raw_note` 逐字 | 「答A或B」≠「答A或B或AB」 |
| D2 | 自訂 `P1`–`P6`；官方代碼僅存 `source` | 官方代碼跨年變動 |
| D3 | 上下標不還原，僅標記證據 | 還原即改寫 |
| D4 | 圖片題納入 release，整題裁切；圖形含向量物件 | 排除會使 P1 系統性缺題；實測有純向量圖題 |
| D5 | 手動下載檔僅作 M1 oracle | 無 URL/擷取時間 |
| D6 | `original` 須 compile 重算 `absent`（見 D12）；180 天複查；90 天閘門 | 寧可延遲，不發布將被更正之答案 |
| D7 | v1 release 限 113 年起；110–112 僅探索 | 以實測格式範圍為準 |
| D8 | acquire／compile 分離，僅 compile 承諾決定性 | 線上同步與 byte-identical 本質衝突 |
| D9 | 刪除逐題 `verified`，release 資格 compile 時計算 | 儲存之布林值會與其所代表的驗證漂移 |
| D10 | parked 粒度為科目；同場其他科可發布，但 `coverage.json` 必列；manifest 只存當前 parked，歷史交 Git | 寧缺勿錯，缺漏必須可見；避免自建事件史 |
| D11 | acquire 只存證據（HTML／PDF），universe、MOD 有無、表頭身分全部由 compile 重算 | 儲存之判定結果與布林值不可重驗 |
| D12 | `original` 僅依最新一次 subject_list 頁，且須於考後 ≥90 天抓取 | 舊的 absent 不代表更正窗口已過 |
| D13 | 人工輸入集中於 `inputs/`，與 compile 產物分離 | clean build 不得刪除人工資料 |

---

## 12. 下一步

1. M1（acquire，首要解 H1）與 M2（compile，以 `oracle/manual/` 為夾具）平行啟動。
2. 實作完成後以 `/codex-review` 區塊 4 對照本規格稽核（特別是 AC 反例 fixture 是否真的存在且會 FAIL）。

---

## 修訂紀錄

### v0.7（2026-10-28）— 頁面 revision 新增條件

| 改動 | 依據 |
|---|---|
| §4.6 明定頁面 revision 新增條件；subject_list digest 限該場藥師科目列；比對加入 `final_url`；當前 rev digest 由 raw 重算 | 年度選單新增他場考試即換 rev，使 115020 MG-1 判 `mg1_stale`；原實作另有 digest 前綴不一致致每次重抓皆換 rev |

### v0.6（2026-09-27）— MG-1 狀態細分

| 改動 | 依據 |
|---|---|
| 新增 withheld reason `mg1_pending`；樣本集合不符改判 `mg1_stale` | review-init 剛產生之空範本被判 `mg1_failed`，與「人工判定不符」無法區分 |

### v0.5（2026-09-25）— M1/M2 實作回寫

| 改動 | 依據 |
|---|---|
| H1 解決：`t=M`；頁面結構與 positive control 依據寫入 §3.1 | M1 實測 |
| universe 為 6 場（含 115090）；總題數更正為 2,250（M0 五場）| M1 實測；v0.4 以前誤算 |
| 站方原址替換 PDF 列入約束；M1 出場條件改為 oracle 三分類 | 實測 9 份重新產生、1 份 MOD 二次更正 |
| T 刪除「標點統一全形」、新增控制字元移除、空白規則精確化 | `10,000` 會被破壞；U+0081 實例 |
| 新增 §4.5.1 L1 組行與切分規則（自組行、空白 glyph 判定、題號左邊界） | `a spirin`、`β receptor … 2`、`14.25℃` 三起靜默錯誤 |
| 新增 AC-16 文字層交叉驗證與 reason `text_layer_loss` | 113020 P1 圈號遺失 |
| AC-15 改以 current revision 為準（696 字、113090-P3-066） | 114090 P3 第 8 題於站方替換後已非圖形題 |
| 跨文件身分一致性不比考試名稱全文 | 答案 PDF 列入併考類科，與試題 PDF 不同長 |
| 程式目錄 `src/tped/build/`（即 compile） | 避開 builtin 名稱 |

### v0.4（2026-09-25）— 依 `.ai-review/plan-verdict-r2.md`

| 改動 | 依據 |
|---|---|
| manifest 新增 `pages`、`discovery`；universe 由 compile 自 HTML 重算；AC-0 反例加「刪整場」「漏最新一場」 | S1-1、S3-1 |
| `inputs/exams.json`（人工、snapshot）與 `data/exams.json`（compile 投影）分離；D13；AC-5 驗 inputs 不變 | S1-2 |
| parked 改為 tuple 內單一當前狀態，歷史交 Git | S1-3、S4-3 |
| `original` 僅依最新 `mod_page_rev`，且抓取於考後 ≥90 天；D12 | S1-4 |
| `coverage.json` 結構化 schema、多原因、狀態優先序、綁 release_date 與 revs | S1-5 |
| MOD 判定改由 compile 自 HTML 重算；positive control 須與 `current.Q` URL 一致；移除 `mod_observations` 與 `mod_observation_id`，改為 `mod_page_rev`；D11 | S2-1、S4-2 |
| compile 只讀 current；AC-9 加 canonical rev == current 與 manifest 不變量 | S2-2、S2-3、S3-7 |
| G4／AC-5 限定鎖定工具鏈 + CI runner 映像，不承諾跨作業系統 | S2-4、S3-3 |
| 新增 AC-14 逐題答案值 | S3-2 |
| AC-6 改為手寫預期集合 + E1–E5 逐項翻轉 | S3-4 |
| §4.7 字元歸屬契約；AC-7 反例「L1+L2 同時截斷」 | S3-5 |
| `exam_date_source_quote` 併入 MG-1 核對 | S3-6 |
| MG-1 單一貪婪覆蓋演算法；風險標籤來自 L0 偵測器；新增 AC-15 M0 回歸下限 | S3-8（部分接受）、S4-5 |
| PR 僅在判定改變時開啟 | S4-2 |

### v0.3（2026-09-25）— 依 `.ai-review/plan-verdict.md`

| 改動 | 依據 |
|---|---|
| G4 拆 acquire／compile；新增 D8；AC-5 擴至全部 compile 產物、自乾淨狀態重跑 | R2-1、R3-AC5、R4-1 |
| 新增 §4.6 manifest schema（tuples、revisions、current、mod_observations、parked） | R2-4、R4-3 |
| negative MOD observation 定義（positive control、404/空頁非 absent） | R1-3、R2-2 |
| raw 不可變、內容定址路徑、append revision | R1-5 |
| parked 狀態模型、reason code、科目粒度；D10；`coverage.json` | R1-2 |
| universe 完整性 AC-0；`coverage.json` 恰覆蓋一次 | R1-1、R3-C2 |
| §5.2 端點結果三分類 | R1-4 |
| §5.3 `concurrency` 序列化 + base commit 衝突 | R1-6（部分接受） |
| §5.1 時區與日期語意；`release_date` 顯式參數；compile 不讀系統時間 | R1-7 |
| 欄位 null 語意；`*_rev` 取代 url/sha256 重複欄位 | R1-8 |
| `script_char_offsets` 改 L2 code point、涵蓋 options | R1-9 |
| N9：110–112 僅探索；M4 改寫 | R1-10 |
| 刪除 `verified`、`extraction`；§5.4 release 資格；D9；AC-6 改集合相等 | R2-3、R3-AC6、R4-2 |
| 設計原則 2 改為四類保證並明示結構不證忠實 | R2-5（部分接受） |
| §5.5 圖形含向量物件、排除頁框、逐選項豁免、`empty_option_keys` | R2-6、R3-AC2 |
| §4.7 L0/L1/L2 三層；MG-1 比對基準明定 | R2-7 |
| `accepted_answers` canonical 形狀與真值表 | R2-8、R3-AC3 |
| `textContent` 移至 README | R2-9 |
| AC 拆自動／人工；MG-1 證據檔綁 revision | R3-C1 |
| M1 oracle 與 crawler 各自通過 AC-12 | R3-C3 |
| AC-1、AC-4、AC-7、AC-9、AC-12 改寫為可證偽斷言；每條附反例 fixture | R3-AC1/4/7/9/12 |
| AC-8 綁 negative observation；`exam_date` 人工填入附來源（N10） | R3-AC8（部分接受） |
| MG-1 決定性分層抽樣 | R3-AC10、R4-6 |
| AC-11 擴至所有 MOD 科目、完全消耗檢查 | R3-AC11 |
| AC-13 加合法重複反例與移除清單（不測 dedupe_chars 內部幾何） | R3-AC13（部分接受） |
| M3 round-trip 改投影追溯 | R4-4 |
| §9 核心契約凍結順序 | R4-5 |

---

> 資料來源：考選部考畢試題查詢平臺（https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx）。
> 引用時請註明資料來源並確保資料之完整，不得任意增刪。
