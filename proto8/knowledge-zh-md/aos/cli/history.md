# `knowledge/aos/cli/history.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/history.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 一個 agent 的對話歷史

用 aos-agent history 來列出、刪除、摘要或替換一個 agent 對話裡的訊息。

```sh
aos-agent history -t NAME ls            # the last 20 messages, one per line: LINE, ROLE, TEXT (cut at 200 characters; -l for full text); a first line says how many earlier ones are not shown
aos-agent history -t NAME ls -a         # every message
aos-agent history -t NAME ls -j 5-      # lines 5 to the end, as JSON
aos-agent history -t NAME ls -n 3      # the last 3 messages (-n -3 is the same)
aos-agent history -t NAME rm 3-4
aos-agent history -t NAME summarize 1-6 "User said their favorite color is blue."
aos-agent history -t NAME set 2 '{"role": "user", "content": "..."}'
```

在 `summarize RANGE TEXT` 和 `set LINE JSON` 裡，`-` 代表從 stdin 讀 TEXT 或 JSON。`summarize` 寫入一則訊息，內容是 `[aos] summary: lines A-B, N messages. TEXT`（role 是 `user`，除非給了 `--role`）；`set` 照給的樣子寫入訊息。

沒給動作就是 `ls`。範圍是 `N`、`A-B` 或 `A-`（A 到最後）。要最後 K 則訊息，就給 `-n K`（或 `--last K`）來代替範圍：`ls -n 3`、`rm -n 2`、`summarize -n 2 TEXT`；`-n -3` 跟 `-n 3` 意思一樣。`--target NAME` 預設是 `$AOS_AGENT`，沒有就是 stack 為目前資料夾的那個 agent（aos/cli/flags.json#/target）。

有些訊息除了 `role` 和 `content` 之外，還有一個 `aos` 鍵：從信來的訊息上是 `{"letter": NAME}`，最終回覆上是 `{"answer_to": [NAME, ...]}`。`aos-agent ask` 和 `listen --letter` 就是靠這個找到某一封信的回覆。`ls` 不顯示它；`ls -j` 會顯示。`set` 照給的樣子寫入訊息，所以要把舊的 `aos` 鍵抄進去，才能保住這個對應；`summarize` 寫入的訊息沒有這個鍵。

被移除或被替換的訊息，會保留在對話歷史旁邊的 `history_removed.jsonl`；`ask` 和 `listen --letter` 在那裡仍然找得到回覆。`--keep FILE` 把它們放到別處；`--no-keep` 把它們丟掉（會先問，rm、summarize 和 set 也一樣；`-y` 跳過詢問）。

先暫停正在跑的 agent：`aos-agent ctl pause NAME`。正在跑的 fsm agent 會在它下一次請求時用上這個改動。eca agent（claude、codex）會在它下一個回合開一段新對話，並把改過的紀錄帶過去。

錯誤：`TargetMissing`、`HistoryMissing`、`RangeBad`（範圍不對，或對話歷史是空的）。還有 `HistoryBad`（對話歷史讀不了）、`MessageBad`（set：不是一個 JSON 物件）、`WriteFailed`。

更多旗標：執行 `aos-agent history --help`。

agent 用工具 `self_history` 改自己的對話歷史：看 `aos/me.json#/self_history`。
