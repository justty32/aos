# `knowledge/wf/knowledge/_description.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/knowledge/_description.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**（原文是字串陣列，5 行）

# 出廠的知識節點

工作流會指過來查的知識與判準。這一夾照工作區 `wf/knowledge/` 的佈局放，路徑讀法同 `wf/workflows/` 那夾。專案自己的記憶（偏好、決策、踩坑記錄、code map…）不在這裡，在各工作區自己的 `wf/knowledge/`；它們的空殼在 `wf/skeletons/`。

現在有：`workflow-template.json`（新工作流節點的骨架）、`content-trim.json`（內容精簡的判準）、`gotchas.json`（整理與拆檔踩過的坑）、`live-lists.json`（活清單 progress.json 怎麼寫、骨架）、`iron-rules.json`（工作區 `AGENTS.md` 的鐵律與入口行）、`dev-dispatch.json`（開發類工作流怎麼分、碰原始碼前先讀什麼）、`code-map-rules.json`（code map 的真相層優先序與維護鏈）、`green-is-not-checked.json`（綠燈不等於有檢查）。
