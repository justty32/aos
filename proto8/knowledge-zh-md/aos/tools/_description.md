# `knowledge/aos/tools/_description.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/_description.md`，跟到正本 commit `578a7c762`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/_description.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

這個資料夾裡有頁面的每個內建工具一個節點：它做什麼、什麼時候用（以及改用哪個工具）、它的參數、附真實輸出的範例，還有它的錯誤。在別頁說明的工具（mailbox_send、self_tools、subagent、agent_def ……）在這裡沒有頁面：這個資料夾的 index 把它列成一個指標列。指標列的鍵是到那一節的路徑，從這個資料夾算起：`../mailbox.json#/tools` 就是 `aos/mailbox.md#/Mailbox tools`；用 json_get 讀它。board_* 工具（工具包 comm：aos/packs.md#/comm）、ws_write（工具包 ws-write：只在你自己的工作區裡寫文字檔）以及 claude 和 codex（不在任何工具包：把一件工作交給 Claude Code 或 Codex CLI，唯讀，在你的工作區裡）目前既沒有頁面也沒有指標。哪些工具在哪個工具包裡：aos/packs.md。
