# taiwan-pharmacist-exam-data

考選部藥師國考測驗式試題的結構化、可稽核題庫。純規則式抽取（無 LLM），每題附完整 provenance，並套用官方更正答案。

> **狀態：規格階段（v0.2）**，尚無可用資料。規格見 [`spec.md`](spec.md)。

## 範圍

- 藥師第一、二階段六科（P1–P6），v1 涵蓋 **113 年起**
- 答案以考選部「測驗題標準答案更正」為準；一律給分、多重答案以 `accepted_answers` 表示
- 圖片題保留整題裁切影像，不做圖形內容解讀

## 已知限制

- 113–114 年 PDF 的上下標已被扁平化（如 `Ca2+`、`10-15`），本專案**不還原**，請勿假設數值字串無歧義
- 考後未滿 90 天之考試不進 release（等待更正答案公告）

## 使用條款

- 題目資料：依著作權法第 9 條第 1 項第 5 款，為 Public Domain
- 本專案自加標註：CC BY 4.0
- 程式碼：MIT
- 下游使用**不得改寫題幹或選項**；請保留 `id` 與 `source` 欄位

## 下游建議

- 前端渲染題幹請用 `textContent`，不要用 `innerHTML`
- 只使用 `release/questions.json`；`release/coverage.json` 列出每科是否發布及原因

---

> 資料來源：考選部考畢試題查詢平臺（https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx）。
> 引用時請註明資料來源並確保資料之完整，不得任意增刪。
