# aos 工具協作 — skill／MCP／權限三個接法

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

三個入口各自怎麼接：pi 走 `.agents/skills/aos/SKILL.md`、支援 MCP 的 agent 走無狀態薄殼、隔離責任交給入口 agent 所在的容器。

---

## skills 怎麼接

用 `.agents/skills/aos/SKILL.md`：pi 會發現這個跨 agent 路徑，也能用 `--skill <path>` 明載。skill
應告訴 coding agent：

- 什麼情況用 aos，以及 Deliver → Status → Exec 的次序；
- 每支命令的參數、JSON stdout／stderr 與退出碼；
- `.runi` 代表什麼，blocked 時不要自行刪；
- **禁止直接寫 `.aos/inst.tempd`**，必須呼叫 Deliver；
- exec 等於讓 world 跑 POSIX 指令，何時需要批准／container；
- recovery 與錯誤修正範例。

skill package 可帶：`references/` 指向磁碟規格、`assets/*.json` 放 instruction 模板、必要腳本。腳本
只驗 tool payload／參考資料，不猜 final 文字。

三個容易混的詞要分開：**skill 是上層 agent 的操作手冊；workflow 是耐久政策／流程；instruction
template 是資產。**三者可以放在同一個 skill package 方便取用，不能當成同一概念。

對 pi 而言，skill 主要是文字指引，實際呼叫由既有 bash tool 執行 `aos`。要在 pi 裡註冊有 typed schema
的原生 tool，依 pi 的立場應寫 extension；extension 介面本場沒有設計。

## MCP 怎麼接，或為什麼 pi 不接

pi 已明確選擇**不做 MCP**。所以「aos 作為 pi 的 MCP」這條字面路徑不成立；pi 的第一級整合面是
CLI＋SKILL.md，或更深時使用 pi extension。

對支援 MCP 的其他 coding agent，做**無狀態薄殼**：

| MCP tool（合併命名） | 轉接的 aos 語意 | 是否預設暴露 |
|---|---|---|
| `aos_status(world)`／`world_status(path)` | `aos status WORLD --json`；回 queue、world/version、`.runi` | 是 |
| `aos_deliver(world, instructions[, key])` | 同一份 Deliver parser、驗證與原子投遞 | 是 |
| `aos_exec(world)`／`step(path)`／`exec_once(path)` | `aos exec WORLD` 推一回合 | 比 status／deliver 更嚴格；預設關閉或明示開啟 |
| `aos_runi(world)`／receipt query | Status／Inspect 的局部查詢 | 是否獨立成 tool 未定 |

MCP server 每次呼叫都重讀 world folder，**記憶體不是狀態真源**；用 `--root`／root allowlist 限制
可見 world，不提供任意 shell。它可以 subprocess 轉 CLI，也可以共用 lib，但不能重新實作投遞
協定、改錯誤 code 或另養 session 真相。

## 權限這塊

pi 沒有權限系統，aos 也不是 sandbox。隔離責任交給入口 agent 所在的 container／micro-VM／OS sandbox，
不在 executor 裡長一套批准彈窗；批准政策屬 agent extension 或沙盒。

最小暴露面：

- Status／Inspect 可預設開；
- Deliver 與 Exec 分開授權。Deliver 雖不立即執行，但可排入危險 POSIX instruction，所以仍需
  root allowlist／instruction template 或等待人審；
- Exec 等同允許 world 跑 bash／任意 POSIX 指令，MCP server 必須同權或更低權，且預設不開；
- adapter／skill 不接受模型任意 argv 直通高權 shell；具名工具映射、人工批准或 container 由上層
  coding agent 負責。

待問的產品選擇：互動 agent 是否預設可 Exec，還是只能 Deliver、等待批准（或由人操作 Exec）。
