# `knowledge/aos/me/self_history.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/me/self_history.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 改你自己的對話歷史

工具 `self_history` 就是對準你自己的 `aos-agent history`。它列出、刪除、摘要或取代你自己對話裡的訊息。改動從你的下一輪起生效。

每則訊息有一個從 1 開始的行號。一次呼叫一個 op（JSON 就是工具的參數）：

- 列出：`{"op": "ls"}`（最後 20 則訊息，每則截到 200 字元）。加 `"all": true` 列出每一則，`"long": true` 給全文，`"range": "5-"` 只看某些行，`"json": true` 用 JSON
- 刪除第 3 到 4 行：`{"op": "rm", "range": "3-4"}`
- 把第 1 到 6 行換成一則你寫的訊息：`{"op": "summarize", "range": "1-6", "text": "User said their favorite color is blue."}`（新訊息的 role 是 `user`，除非你給 `"role"`；它以 `[aos] summary: lines 1-6, 6 messages.` 開頭）
- 把第 2 行換成一則全新的訊息：`{"op": "set", "line": 2, "message": {"role": "user", "content": "..."}}`

範圍是 `"N"`、`"A-B"`、`"A-"`（A 到最後）或 `"-K"`（最後 K 則，例如 `"-3"`）。

規則與錯誤：`aos/me/self_history.json#/rules`。

---

**`#/rules`**

# self_history：規則與錯誤

- 先用 `ls`。它的最後一行告訴你哪些行被鎖住。
- 進行中的那一步被鎖住：呼叫 `self_history` 的那則訊息和它之後的一切。碰到被鎖住的行是 `RangeBad`。
- 預設什麼都不會丟：被移除或被取代的訊息會移到你 stack 裡的 `history_removed.jsonl`。`rm`、`summarize` 和 `set` 接受 `"keep": "FILE"`（改把原文放那裡）或 `"no_keep": true`（不保留）。
- 有些訊息有 `aos` 鍵（信上是 `{"letter": ...}`，最終回覆上是 `{"answer_to": [...]}`）：它讓提問的人找得到他那封信的回覆。用 `set` 時，把舊的 `aos` 鍵抄進新訊息。被移除或被取代的回覆在 `history_removed.jsonl` 裡還找得到，但用了 `keep` 或 `no_keep` 就找不到。
- 如果你的身體是外部 CLI（eca，例如 claude），一次改動會讓你的下一輪開一段新對話，把改過的紀錄帶過去。
- `DaemonMissing`、`DaemonFailed`、`InstanceMissing`：這個功能暫時不能用；照實說，之後最多再試一次（`aos/errors.json#/common`）。
- `MessageBad`：`message` 不是一個 JSON 物件。`HistoryMissing`、`HistoryBad`（你的對話歷史讀不了）、`InterfaceBad`（你定義的 `interfaces.json` 壞了）：要人來修；回報。
