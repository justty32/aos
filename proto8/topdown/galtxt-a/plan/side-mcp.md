# 支線：假如要把這套弄成 MCP，該怎麼做（fable，2026-10-25）

← [lessons.md](lessons.md)｜前例：[thinking 2026-10-24-ai-tools](../../../thinking/2026-10-24-ai-tools.md)（10-24 決定不做 MCP server：多一層協定、多一個常駐行程；CLI＋skill 兩邊都能用；留了「要不要另做 MCP server」一題）

使用者 10-25：「可以先想想，假如想要弄成 mcp，那該怎麼做」「這是支線任務」。只寫結論。

## 1. 「弄成 MCP」最合理指什麼

三種解讀，挑前兩種：

| 解讀 | 是什麼 | 要不要 |
|---|---|---|
| **甲：aos 資料夾程式當 MCP tools** | 一支通用轉接器 `aos-mcp`，把某個資料夾（例 `galtxt-a/`）或它 `tools/` 底下每個有 `tool.json` 的工具，暴露給 Claude Code／Codex 等外部 agent 用 `tools/call` 叫 | **要**，這是主線：外部 agent 不用 Bash 權限、不用知道 aos-exec，就能叫 aos 的函數 |
| **乙：「拆＋`_metainfo`＋收攏」的做程式程序當 MCP tools** | `metatable`、`metatable --suggest`、`collapse`、「證明不改行為」各一個 tool | **要，但不另做**：它們本來就是資料夾程式（`meta/metatable`、`meta/collapse`），補 `tool.json` 就被甲的轉接器自動暴露 |
| 丙：aos 的 agent 反過來當 MCP client（brain.py 用 MCP 叫外部工具） | 寫手叫 MCP server 上的工具 | 不做：P-41 已定工具＝`tools/<名>/`＋stdin／stdout，再掛一套協定違反 C-56 |

## 2. 對應關係（甲）

| aos | MCP | 備註 |
|---|---|---|
| 一個有 `tool.json` 的資料夾程式 `tools/<名>/` | 一個 tool；`name`＝資料夾名、`description`／`inputSchema`＝`tool.json` 的 `description`／`parameters` | `tool.json` 就是去掉 name 的 OpenAI function 物件，跟 MCP 的 `inputSchema`（JSON Schema）同一份 |
| 一隻 agent 資料夾（沒 `tool.json`，例 `galtxt-a/`） | 一個 tool，`inputSchema` 由轉接器給固定形狀：`{"question": string, "name"?: string}`（寫進 `ws/new/<name>`、跑到 idle 退 10、回 `ws/out/<name>`） | 就是 `lib/agent/agent_tool.py` 的 `run_agent` 包成 MCP；每次叫開新小格（P-17） |
| `arguments`（JSON）→ stdin | `tools/call` 的 `arguments` 序列化成 stdin | 同 P-41 |
| stdout 整段 | `content: [{"type": "text", "text": stdout}]` | 結構工具印的一行 JSON 照字面放文字，不另轉 `structuredContent`（第一版） |
| 退非 0、stderr／stdout 一行「名: 代號 原因」 | `isError: true`，`content` 放那一行 | 代號在文字開頭，外部 agent 看得到（跟 lib/README 規則 3「stdout 也印」一致） |
| 退 10（idle 正常停） | 不是錯：agent 跑完了 | 轉接器只在包 agent 時看得到；P-35 的 loop 已把 10 轉成 0 |
| `_metainfo.side_effect=false`＋`writes` 空 | `annotations.readOnlyHint: true` | lint、metatable 是 |
| `_metainfo.idempotent` | `annotations.idempotentHint` | |
| `writes` 有 `ws:` 以外（刪檔、寄信）或 `side_effect=true` 且不可逆 | `annotations.destructiveHint: true`；只有 `stack:`／`ws:out` 的寫＝false | galtxt-a 根：寫 out／done、不可逆性低 → false |
| `resource` 含 `llm` 或 `net` | `annotations.openWorldHint: true` | 寫手、評審、根 |
| `time_ms.val`／`max`、`llm_tokens` | 沒有對應的標準欄；放 `annotations` 的私有 key（`x_aos_time_ms`…）或 `description` 末尾 | C-48 私有 key 的精神 |
| `AOS_WS`、`AOS_STACK` | 轉接器啟動參數 `--ws`、`--stack`；每個 tool call 給 `$AOS_STACK/<名>/` 小格 | P-17 |
| 長時間的 agent（根一題 15～25 s、上限分鐘級） | `tools/call` 同步等；超過 10 s 每隔幾秒送 `notifications/progress`（讀 `trace.jsonl` 行數當進度）；逾時 ＝ 殺整群（P-36）、回 `isError` | 更長的（分鐟級）第二版再做「start／status／result」三個 tool，status 讀 `state.txt`＋trace |

## 3. 要不要一支通用的 `aos-mcp` 轉接器

**要，而且只要這一支**：`aos-mcp [--ws WS] DIR...`，stdio 傳輸，把每個 DIR 當一個 tool；DIR 底下有 `tools/` 就連 `tools/*/`（有 `tool.json` 的）一起列。它只做：`tools/list`（掃 `tool.json`＋`_metainfo` 組 annotations）、`tools/call`（`AOS_STACK=$STACK/<名>/ aos-exec --ws WS DIR`，stdin 進、stdout 出、結束碼→isError）、progress、逾時。不懂任何一個 tool 的內容（C-52）。Python 標準庫寫得出來（JSON-RPC over stdio 幾十行），不引 SDK。

## 4. 跟 proto8 原則有沒有衝突

| 條 | 衝突 | 後果／怎麼收 |
|---|---|---|
| C-61／P-33 工具不用 PATH、放在叫它的那格裡 | MCP server 是常駐行程、工具靠名字叫 | 轉接器只在「aos 之外」用（外部 agent 進來的門），aos 內部照舊；aos 的 agent 不當 MCP client（丙不做） |
| P-41 工具＝stdin／stdout、對話落 history.jsonl | MCP 的對話在外部 agent 那邊，aos 看不到 | 可接受：外部 agent 的對話本來就不是 aos 的；aos 只多了小格裡的 stdin／stdout 紀錄 |
| C-52 每層只管自己 | 轉接器為了 progress 去讀 agent 的 `trace.jsonl`／`state.txt` | 偷看下層。收法：progress 第一版只回「還在跑、過了幾秒」不讀 stack；要看就當它是「有機制」的那種（讀的是慣例檔名、不解內容） |
| P-20 失敗停下等人、不自動重試 | MCP client（Claude Code）很可能看到 isError 就重叫 | 第二次叫是新小格、從頭跑，不是「接著做」；要接著做得暴露 `resume` 這個 tool（同一小格再 `aos-exec`）。描述裡寫清楚，不然外部 agent 會重付整題的腦 |
| N-57 aos 只訂六個環境變數 | 轉接器自己要 `--ws`、`--stack`、逾時 | 都是命令列參數，不加 `AOS_*`；逾時取 `_metainfo.time_ms.max`，沒寫就用參數預設 |
| C-56 KISS、10-24「不做 MCP：多一層協定多一個常駐行程」 | 還是多一層 | 只在「外部 agent 不能給 Bash 權限」時才值得；能給 Bash 就繼續用 CLI＋skill。這條是開工前的門檻 |
| M10 `_metainfo` 模型看不到 | annotations 會被 client 的模型看到 | 只搬 4 個布林 hint，不搬數字；數字放私有 key 給 client 程式、不進 description |

## 5. 最小原型（介面＋範圍，不實作）

- 位置：`proto8/ai_tools/bin/aos-mcp`（跟 aos-ai 同層，嘗試性質）。
- 介面：`aos-mcp [--ws WS] [--stack DIR] [--timeout-s N] DIR...`，stdio JSON-RPC；只實作 `initialize`、`tools/list`、`tools/call`、`notifications/progress`；錯誤一行 `aos-mcp: 代號 原因` 退 1（`ArgumentsBad`、`WsMissing`、`ToolMissing`、`ToolJsonBad`）。
- 範圍：用 galtxt-a 試兩個 tool——`lint`（readOnly、確定性、一秒回）與 `galtxt-a`（agent、openWorld、十幾秒、要 progress）；Claude Code 以 `claude mcp add` 掛上、跑一題、拿到 answer。
- 驗收：`tools/list` 的 annotations 跟 `_metainfo` 一致（純程式對）；`tools/call lint` 的 `isError` 與結束碼一致；agent 那條逾時時整棵子樹被收掉、小格留著給人看。
- 不做：資源（resources/）、提示（prompts/）、HTTP 傳輸、aos 當 client。

**10-27 實作的偏離**（[thinking 10-26 playground](../../../thinking/2026-10-26-playground.md#10-27接-aos-工具mcp)）：放在 `proto8/extras/ai_tools/bin/aos-mcp`（ai_tools 10-26 搬進 extras）；先試 lib/base 的 clock、math、read，不試 galtxt-a；沒做 progress、也沒做「agent 資料夾當 tool」；`destructiveHint` 不給；多一份 `<stack>/calls.jsonl` 記每次呼叫。
