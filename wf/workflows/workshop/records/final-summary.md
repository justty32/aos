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

沒有真實負載前，現在回答也只是猜：

- **四位獨立地都點名：**World／root fd、多世界 A／B／C、proc-table／capability、路徑或 UUID、MCP／skill 的完整形狀。
- **四位都退回或延後：**公開 Publish；**三位**另點名 kernel 分層與通用 Effect／恢復；**工程師**再加斷電 fsync。

等第二個 world、活搬、外呼事故或重複腳本真的出現，答案會自己浮出來。立即缺的只有安全投遞 `deliver`。

## 明天早上第一個動作

**四位全都指向：不要再讀，直接在 WSL 跑真實切片。**這正是已開始的 T5 實驗。

- **工程師：**`aos init /tmp/aos-smoke`，用 instruction 跑一次 `codex exec`，再跑 `aos exec`。
- **架構師：**同一 smoke world，讓 prompt 依 `wf/WORKFLOWS.md` 路由真實請求，記第一個卡點。
- **研究人員：**先只實作 `aos deliver` 與測試；不做 publish、effect、lane。
- **開發者：**用 aos 跑一條 workshop 指令，只驗證能否產出 raw 回答。

## 四句話

- **工程師：**先讓一個 workflows 的真實痛點完整跑通，再讓實驗決定架構；因為 aos 的目的不是造作業系統，而是變得比 workflows 好用。
- **架構師：**先讓 aos 跑完一次你真的會用的 workflow；只有實驗反覆卡住的地方，才配進 core。因為 aos 的目的不是成為 OS，而是讓原本不好用的 workflows 變好用。
- **研究人員：**先讓 agent 直接呼叫 `aos deliver`，跑通一個真回合，再談作業系統；因為「複用、簡潔」只能由實際重複的痛點證明。
- **開發者：**先讓 aos 真的替 workflows 少掉一個手動步驟，再談它像不像 OS；因為「不好用」才是起點，kernel、lane、MCP 都只是候選手段。

## 這個專案會怎麼死

**四位獨立地說的是同一種死法：**第一個「模型→工具→模型」還沒跑通，就先把 aos 做成比 workflows 更完整、更難用的作業系統；文件與抽象先耗光作者的興趣。

## 他們自己改了什麼

- **工程師：**從先收 Publish／Effect／receipt，退到只補 Deliver。
- **架構師：**從先定 World／能力／耐久效果，退到讓真 workflow 逼架構長出來。
- **研究人員：**收回 World／Effect／自然語言 adapter；改成 agent 判斷、Deliver 交接。
- **開發者：**收回解析模型文字；改成 agent 直接呼叫會驗證的 tool。

這四個 session 到此為止；續場 session id 不再列出，之後要談就重新開場。
