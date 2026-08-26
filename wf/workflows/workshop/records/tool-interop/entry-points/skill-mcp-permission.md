# aos 工具協作 — skill／MCP／權限三個接法

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

三個入口各自怎麼接：pi 走 `.agents/skills/aos/SKILL.md`、支援 MCP 的 agent 走無狀態薄殼、隔離責任交給入口 agent 所在的容器。

---

## skills 怎麼接

**四位獨立地都選 `.agents/skills/aos/SKILL.md`**，因為 pi 會發現這個跨 agent 路徑，也能用
`--skill <path>` 明載。skill 應告訴 coding agent：

- 什麼情況用 aos，以及 Deliver → Status → Exec 的次序；
- 每支命令的參數、JSON stdout／stderr 與退出碼；
- `.runi` 代表什麼，blocked 時不要自行刪；
- **禁止直接寫 `.aos/inst.tempd`**，必須呼叫 Deliver；
- exec 等於讓 world 跑 POSIX 指令，何時需要批准／container；
- recovery 與錯誤修正範例。

工程師把 `references/` 指向磁碟規格、`assets/*.json` 放 instruction 模板；架構師提
`scripts/validate-reply`，但追問輪拿掉自然語言解析後，這類 script 應只驗 tool payload／參考資料，
不再猜 final 文字。開發者也讓 skill 帶規格與必要腳本。

四位還特別分開三個容易混的詞：**skill 是上層 agent 的操作手冊；workflow 是耐久政策／流程；
instruction template 是資產。**三者可以放在同一個 skill package 方便取用，不能當成同一概念。

對 pi 而言，skill 本身主要是文字指引，實際呼叫可由既有 bash tool 執行 `aos`。若要在 pi 裡註冊
有 typed schema 的原生 tool，依 pi 的立場應寫 extension；四位本輪沒有設計 extension 介面。

## MCP 怎麼接，或為什麼 pi 不接

pi 已明確選擇**不做 MCP**。所以「aos 作為 pi 的 MCP」這條字面路徑不成立；pi 的第一級整合面是
CLI＋SKILL.md，或更深時使用 pi extension。

對支援 MCP 的其他 coding agent，**四位獨立地都提出無狀態薄殼**：

| MCP tool（合併命名） | 轉接的 aos 語意 | 是否預設暴露 |
|---|---|---|
| `aos_status(world)`／`world_status(path)` | `aos status WORLD --json`；回 queue、world/version、`.runi` | 是 |
| `aos_deliver(world, instructions[, key])` | 同一份 Deliver parser、驗證與原子投遞 | 是 |
| `aos_exec(world)`／`step(path)`／`exec_once(path)` | `aos exec WORLD` 推一回合 | 四位都要求比 status／deliver 更嚴格；預設關閉或明示開啟 |
| `aos_runi(world)`／receipt query | Status／Inspect 的局部查詢 | 研究人員、工程師提出；是否獨立成 tool 未定 |

MCP server 每次呼叫都重讀 world folder，**記憶體不是狀態真源**；用 `--root`／root allowlist 限制
可見 world，不提供任意 shell。它可以 subprocess 轉 CLI，也可以共用 lib，但不能重新實作投遞
協定、改錯誤 code 或另養 session 真相。

## 權限這塊

pi 沒有權限系統，aos 也不是 sandbox。**四位獨立地都把隔離責任交給入口 agent 所在的
container／micro-VM／OS sandbox**，而不是在 executor 裡長一套批准彈窗。

共同的最小暴露面是：

- Status／Inspect 可預設開；
- Deliver 與 Exec 分開授權。Deliver 雖不立即執行，但可排入危險 POSIX instruction，所以仍需
  root allowlist／instruction template 或等待人審；
- Exec 等同允許 world 跑 bash／任意 POSIX 指令，MCP server 必須同權或更低權，且預設不開；
- adapter／skill 不接受模型任意 argv 直通高權 shell；具名工具映射、人工批准或 container 由上層
  coding agent 負責。

資深架構師的邊界是「批准政策屬 agent extension 或沙盒，不塞進 executor」；要接工具的開發者
則主張 agent 預設只排隊，Exec 明開或由人操作。這也留下待問的產品選擇：互動 agent 是否預設可
Exec，還是只能 Deliver 等待批准。
