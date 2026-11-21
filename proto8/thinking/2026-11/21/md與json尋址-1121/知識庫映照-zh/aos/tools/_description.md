# `knowledge/aos/tools/_description.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/_description.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

這個資料夾裡有頁面的每個內建工具一個節點：它做什麼、什麼時候用（以及改用哪個工具）、它的參數、附真實輸出的範例，還有它的錯誤。在別頁說明的工具（mailbox_send、self_tools、subagent、agent_def ……）在這裡沒有頁面：這個資料夾的 index 把它列成一個指標列。指標列的鍵是到那一節的路徑，從這個資料夾算起：`../mailbox.json#/tools` 就是 `aos/mailbox.json#/tools`；用 json_get 讀它。board_* 工具（工具包 comm：aos/packs.json#/comm）、ws_write（工具包 ws-write：只在你自己的工作區裡寫文字檔）以及 claude 和 codex（不在任何工具包：把一件工作交給 Claude Code 或 Codex CLI，唯讀，在你的工作區裡）目前既沒有頁面也沒有指標。哪些工具在哪個工具包裡：aos/packs.json。
