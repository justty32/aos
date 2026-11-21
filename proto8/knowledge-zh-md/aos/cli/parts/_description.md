# `knowledge/aos/cli/parts/_description.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/_description.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 低階零件

其他指令是用這些程式組成的。你很少自己打它們：aos-agent、aos-daemon-ctl 和範本會呼叫它們。自己動手用它們，可以試一個功能、讀或改 aos 的 JSON、或看看信箱裡有什麼。

每個都有 `--help`（有子指令的：`aos-post send --help`）。旗標可以放在參數前面或後面，但要在子指令之後（`aos-post send BOX --x`，不是 `aos-post --x send`）；`aos-json set`、`add`、`append` 和 `merge` 要把旗標放在 FILE 前面。結束碼 10 的意思是「那裡沒東西」（沒有信、沒有鎖、還沒有回覆），不是錯誤。錯誤與重試：`aos/cli/errors.json`。
