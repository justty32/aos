# 追問輪：最小 tool 組、一套 CLI，與不設自然語言解析層

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

Deliver 之外的收攏：runtime 最小 tool 組是哪幾支、同一套 CLI 能不能同時服務 skill／MCP／腳本，以及不設自然語言 adapter。

---

## 最小 tool 組

runtime 最小組是三支（四位一致）：

| 功能 | 共同語意 | 命名 |
|---|---|---|
| **Deliver** | 驗證後原子投一批，不執行 | `aos deliver` |
| **Status／Inspect** | JSON 回 world/version、idle／ready／running／blocked、pending queue、`.runi`，可選查 receipt | `status` 或 `inspect`，未定 |
| **Exec** | 推指定 world 一回合；輸出與退出另按 executor 契約 | `exec` |

**Init**（建立 world／版面）屬建置期／初次使用，不列入 runtime 三支。

世界內容不另造 read tool：coding agent 本來就有 read／ls，pi 也已有 read、write、edit、bash。aos 的
tool set 補的是磁碟交接語意，不重做 agent 已有的檔案工具。

## 一套 CLI 能不能同時服務 skill／MCP／腳本

「一套語意夠」。pi skill 與 shell 腳本直接執行 CLI；MCP 只把 typed arguments、stdin、stdout、stderr、
退出碼轉接成 tool result，不另寫一套投遞命名與驗證規則。

MCP façade 可直接呼叫共用 lib，也可轉呼 CLI；限制不是「一定 spawn subprocess」，而是**只有一份
Deliver 語意與 parser**。

## 不設自然語言解析層

照使用者那句「直接給 tool」（原話見[本場索引](../README.md)）：

- agent 直接 tool-call Deliver；tool-call 的 arguments 就是待驗 payload，失敗作為 tool result 回模型
  修正。adapter 只轉 tool protocol，不解析、不猜測。
- 不做 `aos prompt | pi | aos ingest --adapter pi`、`aos accept W --adapter pi` 這類解析層；
  stdout→stdin 只傳上下文，final 文字不進交接。
- `response.bad/`／`agent.invalid` 不是正常的解析失敗路徑：模型 tool-call 錯，Deliver 直接回結構化
  錯誤；模型 final 文字本來就不是 instruction，不需要隔離。原始 response 若要留作觀測，由
  agent／driver 保存。
