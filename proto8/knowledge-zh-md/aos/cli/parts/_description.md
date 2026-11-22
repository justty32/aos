# `knowledge/aos/cli/parts/_description.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/parts/_description.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/parts/_description.md#/…` 對的就是它。改請改正本，再照 [README](../../../README.md) 的做法跟上這份。

---

**`#/Low-level parts`**

# 低階零件

其他指令是用這些程式組成的。你很少自己打它們：aos-agent、aos-daemon-ctl 和範本會呼叫它們。自己動手用它們，可以試一個功能、讀或改 aos 的 JSON、或看看信箱裡有什麼。

每個都有 `--help`（有子指令的：`aos-post send --help`）。旗標可以放在參數前面或後面，但要在子指令之後（`aos-post send BOX --x`，不是 `aos-post --x send`）；`aos-json set`、`add`、`append` 和 `merge` 要把旗標放在 FILE 前面。結束碼 10 的意思是「那裡沒東西」（沒有信、沒有鎖、還沒有回覆），不是錯誤。錯誤與重試：`aos/cli/errors.md`。
