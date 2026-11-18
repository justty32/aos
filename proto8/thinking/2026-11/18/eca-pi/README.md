# eca-pi：把 pi coding agent 接成第三種 eca 行不行、怎麼接（純研究，沒改程式、沒安裝）

← [2026-11-18](../README.md)

線 eca-pi-1118，11-18。使用者原話：「幫我研究eca pi coding agent」。前情：11-16「之後還要開線做pi coding agent」（[進度檔 `pi-coding-agent`](../../../../../wf/progress.json)，範圍待確認）；10-24 照 pi 做過四支基本工具（[pi-tools](../../../2026-10/24/pi-tools/README.md)）。

## 先講結論

- **「pi」就是 Mario Zechner 做的那個 pi，但它搬家了**：2026-04 被 Earendil 收購，repo 從 `badlogic/pi-mono` 搬到 `earendil-works/pi`，npm 從 `@mariozechner/pi-coding-agent` 換成 **`@earendil-works/pi-coding-agent`**（舊名停在 0.73.1、已標 deprecated）。指令還是 `pi`，MIT。很活躍：10-01 出 1.0，11-10 已到 1.5.2。沒查到別的同名東西更像。
- **能接**。pi 給的東西跟 aos eca 要的大多對得上，而且有幾樣比 claude 還好接：自己能指定對話 id（`--session-id`，跟 claude 同招）、對話檔可以放進 aos 的小格（`--session-dir`）、有正式的 JSON 事件流與 RPC 模式（不用解析畫面）、回答途中插話是原生的（`steer`／`follow_up`）。
- **推薦先走「一問一答」那條**：照 codex 的樣子在 `cli_session` 加第三種身 `"kind": "pi"`，非互動用 `pi --mode json`（第 1 步），要「回答途中收信」再換成每輪起一次 `pi --mode rpc`（第 2 步），畫面（tmux）與 pi 外掛最後才做（第 3 步）。第 1 步大約是「當初加 codex」的一半量，一條線一兩天。細節與另外兩種接法在 [04](04-接法選項與待裁.md)。
- **最大的三個坑**：
  1. **pi 不問權限、沒有沙盒**：預設 bash、寫檔全照做，沒有 claude 那種 `dontAsk`＋白名單。要擋只能自己寫 pi 外掛（TypeScript，在 pi 行程裡跑、權限跟使用者一樣大）或整隻關進容器。
  2. **「答完了」要等對訊號**：`agent_end` 之後還可能自動重試、壓縮、接著做；要等 `agent_settled`。畫面那條路 pi 沒有現成的「講完一輪叫外部指令」設定，得自己寫外掛才有通知。
  3. **帳號與錢**：Claude 訂閱不能給 pi 用（Anthropic 只准在 Claude Code 裡用），pi 叫 claude 模型要另付 API 錢；ChatGPT 訂閱 pi 自己能登入，或接今天架的 litellm proxy（`http://localhost:4000/v1`）。pi 版本跳得快、1.0 有破壞性改動，要釘版。

## 要使用者裁的題（細節在 [04 末段](04-接法選項與待裁.md#要使用者裁的題)）

1. 範圍：做成 eca 第三種身（跟 claude、codex 並列）嗎？還是只當實驗？
2. 先做哪段：只做一問一答（推薦）／連畫面一起做。
3. 權限怎麼辦：照 pi 原樣全開（跟現在 codex `workspace-write` 差不多寬，但連沙盒都沒有）／寫一支 aos 的 pi 外掛擋危險指令／整隻放容器。
4. 模型走哪：pi 自己登 ChatGPT 訂閱／走 litellm proxy／API key。
5. 裝在哪、釘哪版：公司 WSL 還沒有 pi；家機有一份舊的（11-16 留底記的路徑，多半是舊 scope），要不要換成釘版的 `@earendil-works/pi-coding-agent@1.5.2`。

## 分檔

| 份 | 內容 |
|---|---|
| [01-aos-eca要什麼](01-aos-eca要什麼.md) | 讀 `apps/eca`、`agentlib/cli_*.py`、範本整理出的「一種 CLI 要當 eca，aos 需要它提供什麼」，哪些欄是 claude 專屬 |
| [02-pi是什麼](02-pi是什麼.md) | pi 的出處、模式、對話檔、外掛、權限、MCP、系統提示、模型與登入、壓縮（附來源） |
| [03-對照表](03-對照表.md) | 逐項比 aos 要的／pi 給的／claude 現在怎麼給，標「直接對上／要寫轉接／對不上」 |
| [04-接法選項與待裁](04-接法選項與待裁.md) | 三種接法的工作量與後果、推薦、待裁題 |
| [05-供應鏈](05-供應鏈.md) | pi 與相依有沒有事故、怎麼釘版（這次沒裝任何東西） |

## 沒做與沒驗的

- 沒裝 pi、沒跑過任何一個旗標；下面寫的旗標與事件名都是 11-18 讀官方文件（`earendil-works/pi` 主線 `packages/coding-agent/docs/`）得來，**實際行為要裝了才算數**（尤其 `--mode json` 從 stdin 吃題目、`--session-id` 在 `--session-dir` 下的行為、結束碼）。
- 讀網頁時沒遇到對我下指令的文字。
</content>
</invoke>
