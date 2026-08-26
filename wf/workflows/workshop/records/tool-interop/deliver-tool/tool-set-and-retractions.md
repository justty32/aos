# 追問輪：最小 tool 組、一套 CLI，與四位收回的

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

Deliver 之外的收攏：runtime 最小 tool 組是哪幾支、同一套 CLI 能不能同時服務 skill／MCP／腳本，以及使用者一句話之後四位各自收回的自然語言 adapter。

---

## 最小 tool 組

| 功能 | 入選情況 | 共同語意 | 命名差異 |
|---|---|---|---|
| **Deliver** | **4／4** | 驗證後原子投一批，不執行 | 四位都叫 `aos deliver` |
| **Status／Inspect** | **4／4** | JSON 回 world/version、idle／ready／running／blocked、pending queue、`.runi`，可選查 receipt | 架構師、研究人員、開發者叫 `status`；工程師叫 `inspect` |
| **Exec** | **4／4** | 推指定 world 一回合；輸出與退出另按 executor 契約 | 四位都叫 `exec`，研究人員稱「推一步」 |
| **Init** | 三位提到，但不列入 runtime 三支 | 建立 world／版面 | 工程師說它屬建置期；研究人員、開發者列為初次使用；架構師的最小組沒列 |

世界內容不用另造 read tool：資深架構師指出 coding agent 本來就有 read／ls；pi 也已有 read、write、
edit、bash。aos 的 tool set 應補磁碟交接語意，不重做 agent 已有的檔案工具。

## 一套 CLI 能不能同時服務 skill／MCP／腳本

**四位 4／4 都答「一套語意夠」。**pi skill 與 shell 腳本直接執行 CLI；MCP 只把 typed arguments、
stdin、stdout、stderr、退出碼轉接成 tool result，不能另寫一套投遞命名與驗證規則。

實作層仍有一個小分叉：工程師偏好共用 lib＋CLI，MCP façade 直接呼叫 lib；架構師、研究人員偏好
MCP 轉呼 CLI；開發者接受同一 lib 或 CLI。共同限制不是「一定 spawn subprocess」，而是**只有一份
Deliver 語意與 parser**。

## 四位收回／改寫的

使用者那句「直接給 tool」之後，**四位各自都收回了主輪的自然語言解析層**：

| 誰 | 收回什麼 | 改成什麼 |
|---|---|---|
| 工程師 | `agent JSON → adapter → deliver` 中 adapter 負責解析／猜測 | adapter 只轉 tool protocol；agent 直接呼叫 Deliver |
| 架構師 | adapter 解析 agent 自然語言，再驗 instruction | tool-call 的 arguments 就是待驗 payload；失敗作為 tool result 回模型修正 |
| 研究人員 | `aos prompt \| pi \| aos ingest --adapter pi` | 取消 ingest；agent 呼叫 Deliver，final 文字不進交接 |
| 開發者 | `aos accept W --adapter pi` | 取消 accept／解析；stdout→stdin 只傳上下文，instruction 由 tool-call Deliver |

連帶收回的還有 `response.bad/`／`agent.invalid` 作為正常解析失敗路徑：模型若 tool-call 錯，Deliver
直接回結構化錯誤；模型 final 文字本來就不是 instruction，不需要隔離。原始 response 若要留作
觀測仍可由 agent／driver 保存，但不再由一支 ingest 猜它是不是 JSON。
