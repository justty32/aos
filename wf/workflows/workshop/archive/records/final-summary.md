# 七場研討會總結
← [workshop](../README.md)

| | |
|---|---|
| **主題** | 七場研討會最後發言 |
| **日期** | 2026-08-25 |
| **參與身份** | 資深工程師／資深架構師／資深研究人員（OS／體系結構）／要接這個工具的開發者 |
| **狀態** | **已結束** |

## 他不必回答的問題

> **窩不想看惹…QQ。**

沒有真實負載前，回答也只是猜：World／root fd、多世界 A／B／C、proc-table／capability、路徑或 UUID、
MCP／skill 的完整形狀；公開 Publish、kernel 分層、通用 Effect／恢復、斷電 fsync 也都延後。

等第二個 world、活搬、外呼事故或重複腳本真的出現，答案會自己浮出來。立即缺的只有安全投遞 `deliver`。

## 明天早上第一個動作

**不要再讀，直接在 WSL 跑真實切片**（即 T5 實驗）。可選的起手：

- `aos init /tmp/aos-smoke`，用 instruction 跑一次 `codex exec`，再跑 `aos exec`。
- 同一 smoke world，讓 prompt 依 `wf/WORKFLOWS.md` 路由真實請求，記第一個卡點。
- 先只實作 `aos deliver` 與測試；不做 publish、effect、lane。
- 用 aos 跑一條 workshop 指令，只驗證能否產出 raw 回答。

## 方向

- **先讓 aos 跑通一條你真的會用的 workflow、替它少掉一個手動步驟**，再讓實驗決定架構；只有實驗反覆卡住
  的地方才配進 core。aos 的目的不是成為 OS，而是讓原本不好用的 workflows 變好用；kernel、lane、MCP 都只是候選手段。
- 「複用、簡潔」只能由實際重複的痛點證明。
- **agent 判斷、直接呼叫會驗證的 tool（`aos deliver`）交接**，不解析模型文字。

## 這個專案會怎麼死

第一個「模型→工具→模型」還沒跑通，就先把 aos 做成比 workflows 更完整、更難用的作業系統；文件與抽象
先耗光作者的興趣。

這四個 session 到此為止；續場 session id 不再列出，之後要談就重新開場。
