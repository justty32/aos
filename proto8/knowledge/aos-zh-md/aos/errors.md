# `knowledge/aos/errors.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/errors.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 讀懂一個錯誤

怎麼看一次失敗的呼叫：`error:` 那行、`warning:` 那幾行，以及結束碼。

失敗的 aos 程式會印出一行錯誤：`program: error: Code reason`。

`self_tools: error: ToolExists math is already listed in your tools (add replace: true to replace it)`

- 第一個字 = 誰失敗了（一個程式、一個工具，或一個 agent 名字）。
- 緊接在 `error: ` 後面的那個字 = 代號。它的結尾說明是哪一類問題：看 `aos/errors.json#/codes`；最常見的代號：`aos/errors.json#/common`；在其他頁講的代號（`PhaseBad`、`BudgetMissing` ...）：`aos/errors.json#/where`。
- 剩下的 = 原因，給人看的。用法提示放在最後：`(usage: ...)`。

你呼叫的工具也會把錯誤那行印在 stdout，並以 1 結束。失敗或逾時的工具結果，也會顯示它 stderr 的最後 2048 位元組。跑超過時間限制的工具（它 `_metainfo.json` 裡的 `timeout_ms`；0 = 不限時）會被停掉。解析不了的旗標會在原因後面加上 `(see NAME --help)`；`NAME --help` 會列出這個工具的參數和它宣告的錯誤代號。

`program: warning: sentence` 不是錯誤。呼叫成功了；這行只是告訴你一件事。絕不要因為一個警告而重試。

結束碼，以及 `shell`／`run_python` 的 `[exit code N]` 那行：`aos/errors.json#/exits`。

一個工具用文字回覆而沒有錯誤行，就是成功了，即使文字寫的是「no」、「none」或「(none)」。

---

**`#/codes`**

# 錯誤代號

每種代號結尾代表什麼，以及該怎麼做。

代號是緊接在 `error: ` 後面的那個字。它的結尾：

| 結尾 | 意思 | 該怎麼做 |
|---|---|---|
| `...Bad` | 你給的某個東西格式不對或不被允許（`ArgumentsBad`、`PathBad`、`RequestBad`、`NameBad`） | 修正參數，重試一次 |
| `...Missing` | 應該存在的某個東西不存在（`PathMissing`、`FileMissing`、`WsMissing`、`DaemonMissing`、`AnswerMissing`、`BudgetMissing`） | 建立它、等它，或回報它不在。不要盲目重試 |
| `...Unknown` | 在某個清單裡找不到某個名字（`OpUnknown`、`FlagUnknown`、`CommandUnknown`、`SubagentUnknown`、`EndpointUnknown`、`ToolUnknown`） | 列出有哪些，再用清單裡的名字 |
| `...Failed` | 試著做某個動作而失敗了（`WriteFailed`、`LaunchFailed`、`EndpointFailed`、`CommandFailed`） | 通常是環境問題；重試一次，再回報 |
| `...Exists` | 那個名字的東西已經在了（`ToolExists`、`InstanceExists`、`DefExists`、`LetterExists`） | 不要覆蓋。換一個名字；只有真的要替換時才用 `replace`（`--replace`） |
| `...Rejected` | 守門的說不（`AddRejected`、`CtlRejected`） | 這是一個決定。調整（移掉某個東西、要少一點）或回報。絕不要一直重來 |
| `...Internal` | 程式裡的 bug | 帶著完整那行回報它 |

這些是常見的結尾，不是全部：有些代號的結尾不一樣（`DepthExceeded`、`SubagentQueued`、`ChildrenExist`）。讀代號後面的原因；工具自己的節點會說該怎麼做。

你最常遇到的代號：`aos/errors.json#/common`。在其他頁講的代號（`PhaseBad`、`BudgetMissing`、`InstanceExists` ...）：`aos/errors.json#/where`。

**`#/common`**：→ `$ref` `errors/common.json`（映照版：[errors/common.md](errors/common.md)）

---

**`#/exits`**

# 結束碼

- `0`：完成。
- `10`：完成，而且答案是「沒有」（沒有信、沒有鎖、還沒有回覆、檢查發現了問題）。不是錯誤：照著這個「沒有」去行動。
- `130`：被 Ctrl-C 停掉。`128+N`：被訊號 N 殺掉（`143` = TERM，常常是逾時）。`141`：給人用的指令，它的輸出管線提早關了（例如 `| head`）；不算失敗。
- 其他非零：失敗。如果它的 stderr 有 `itsname: error:`，就是程式本身失敗了；如果沒有，這個碼來自它執行的某個東西。

會執行你的指令的工具（`shell`、`run_python`）在 stdout 最後加上 `[exit code N]`：這是你的指令的結束碼，不是工具的。這裡非零表示你的指令失敗了；讀它的輸出，那就是答案。

---

**`#/where`**

# 代號在哪裡講

你常遇到、但這頁和 `aos/errors/common.json` 沒講的代號。去讀列出的地方。

| 代號 | 講在 |
|---|---|
| `PhaseBad` | `aos/agents.json#/agents_ctl`；另見 `aos/cli/agent.json#/phases`、`aos/cli/errors.json#/codes` |
| `InstanceExists` | `aos/agents.json#/agents_ctl` |
| `HoldRefused` | `aos/kernel.json#/gate`；出現在 `CtlRejected` 那行裡時：`aos/agents.json#/agents_ctl` |
| `SubagentSlotMissing` | `aos/agents/subagent.json#/errors` |
| `BudgetMissing` | `aos/brain.json#/priority` |
| `RequestBad`（腦的請求） | `aos/brain.json#/_description` |
| `DeadlineBad` | `aos/brain.json#/codes` |
| `KeyMissing` | `aos/me/self_llm.json`（op `rm`）；`aos/cli/errors.json#/codes` |
| `SchemaBad` | `aos/user_zone.json#/send` |
| `SpecBad` | `aos/tools/json_get.json#/path` |
| `FollowMissing` | `aos/tools/jsonx_set.json#/errors` |
| `KernelFailed` | `aos/kernel.json#/where_to_send`（kernel 沒有及時回覆，或拒絕了） |

講在 `aos/errors/common.json#/_description` 的：`DaemonMissing`、`InstanceMissing`、`AddRejected`、`ToolExists`、`LlmKernelMissing`。

不在這裡的代號：看印出它的那個工具的頁面（`aos/tools/<tool>.json`），指令的話看 `aos/cli/errors.json#/codes`。
