# taiwan-pharmacist-exam-data

考選部藥師國考測驗式試題的結構化、可稽核題庫。純規則式抽取（無 LLM），每題可追溯至不可變之來源 PDF revision，並套用官方更正答案。

> **狀態：M1（擷取）、M2（編譯）完成；release 尚待 MG-1 人工抽樣審查**，目前 `release/questions.json` 為空。規格見 [`spec.md`](spec.md)。

## 範圍

- 藥師第一、二階段六科（P1–P6），v1 涵蓋 **113 年起**
- 答案以考選部「測驗題標準答案更正」為準；一律給分、多重答案以 `accepted_answers`（答案集合之陣列）表示
- 圖片題保留整題裁切影像（`data/figures/`），不做圖形內容解讀

## 使用哪個檔案

| 檔案 | 內容 |
|---|---|
| `release/questions.json` | **下游請用這份**：通過全部自動驗收＋人工抽樣、考後 ≥ 90 天之題目 |
| `release/coverage.json` | 每一科是否發布、未發布原因（`parked`／`withheld`） |
| `data/questions.json` | canonical 全集（含尚未通過人工抽樣者），供稽核 |

## 已知限制

- 113–114 年 PDF 的上下標已被扁平化（如 `Ca2+`、`10-15`），本專案**不還原**；115 年起以 `script_char_offsets` 標示小字型字元位置
- 考後未滿 90 天之考試不進 release（實測 114 年第一次藥學(三)於考後 53 天、73 天兩度更正答案）
- 113 年第一次藥學(一)因 PDF 文字層遺失圈號①–⑥（18 字），整科 `parked`，不發布

## 指令

```
uv run tped acquire                              # 線上擷取（每請求間隔 1.5 秒）
uv run tped compile --release-date YYYY-MM-DD    # 離線編譯（決定性）
uv run tped review-init EXAM_CODE                # 產生 MG-1 人工抽樣範本
uv run tped review-serve                         # 本機審查頁 http://127.0.0.1:8765/
uv run pytest                                    # AC-0 ~ AC-16
```

## 使用條款

- 題目資料：依著作權法第 9 條第 1 項第 5 款，為 Public Domain
- 本專案自加標註：CC BY 4.0
- 程式碼：MIT
- 下游使用**不得改寫題幹或選項**；請保留 `id` 與 `source` 欄位

## 下游建議

- 前端渲染題幹請用 `textContent`，不要用 `innerHTML`
- 作答判定以集合比對：使用者作答集合 ∈ `accepted_answers` 即正確；`score_policy == "all_credit"` 一律正確

---

> 資料來源：考選部考畢試題查詢平臺（https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx）。
> 引用時請註明資料來源並確保資料之完整，不得任意增刪。
