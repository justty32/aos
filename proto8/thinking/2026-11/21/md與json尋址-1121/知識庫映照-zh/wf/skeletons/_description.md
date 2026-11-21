# `knowledge/wf/skeletons/_description.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/skeletons/_description.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**（原文是字串陣列，7 行）

# 記憶骨架

專案自己要填的記錄與知識（決策、想法、踩坑、使用者偏好、驗證表、開發環境、code map、寫碼慣例、調查筆記、分析產物）的空殼。每份寫：放什麼、不放什麼（`holds`）、欄位（`fields`，以鍵名為鍵）、規則（`rules`），與一份 `skeleton`。

怎麼用：工作流的步驟寫「還沒有就照 `wf/skeletons/<名>.json#/skeleton` 建」時，把 `skeleton` 的值抄成工作區的 `wf/knowledge/<名>.json` 再填（`notes` 是一篇一檔的 `wf/knowledge/notes/<主題>.json`；`analysis` 的 `skeleton` 是要先建的檔名清單，建在 `wf/knowledge/analysis/<project>/`）。`skeleton` 裡寫的路徑是工作區裡的路徑。這一夾只在本庫，工作區裡沒有 `wf/skeletons/`。

現在有：`decisions`、`ideas`、`gotchas`、`user`（配 `wf/workflows/` 的 decisions、planning、gotchas、user）；`verification`、`dev-env`、`code-map`、`conventions`、`notes`、`analysis`（配開發類工作流）。
