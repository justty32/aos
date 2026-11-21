# `knowledge/aos/me/self_system.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/me/self_system.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 改你自己的系統文字

工具 `self_system` 就是對準你的 `aos-agent system`；只有你自己的複本會變，你的定義不變。

- 看：`{"op": "get"}`（`"long": true` 會多加第一行 FROM TAB FILE：agent、definition 或 none）
- 改：`{"op": "set", "text": "..."}`（整段新的文字；先 `get` 才能保留舊的行）
- 復原：`{"op": "reset"}`

什麼時候生效：agent-fsm = 你下一次腦呼叫（它取代定義的；空的 = 沒有系統訊息）；eca claude = 你下一輪（附加在後）；eca codex = 你下一個新對話；eca pi = 你下一輪（附加在後）；開著的畫面 = 重新打開時。

每次改都會讓你的 prompt 快取失誤一次：在你的工作改變時才改，不要每輪都改。壞掉的文字由人來修：`aos-agent system --target <you> reset`。模型設定是 `self_llm`。`SystemMissing` = 你的定義沒宣告系統檔。`SystemBad` = 你的複本或你定義的系統檔讀不了，或定義宣告錯了；必須由人來修。

為什麼依身體而不同（以及對話歷史怎麼處理）：`aos/body.json#/system_history`。
