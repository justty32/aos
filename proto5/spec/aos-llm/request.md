← [aos-llm](README.md)｜[spec 總導航](../README.md)

# 3. 讀 agent 家

跑起來那一刻才讀（所以排隊期間人改了人格、記憶、工具，問的是改過的）：

- `info.json`：讀 JSON（`ReadFailed`／`JsonSyntax`／`NotAnObject`），頂層不能是指示詞；然後**只解驗六格**：`_metainfo`、`system`、`history`、`tools`、`llm.model`、`llm.params`，
  規則照 [agent.md §3](../agent/info.md)（中心 agent 家，`$env` 在這顆 cpu 的環境解）。`llm` 本身要是物件（先不解它，只取 `model`、`params` 兩格各自解）；
  其他格（`llm.pool`、`llm.timeout_ms`、`tool_pool`、`tick`、不認得的 key）**不解、不驗**，那是 aos-agent 的事。
  所以六格以外的 `$env` 只要 agent 那顆 cpu 有就行；六格裡的 `$env` 兩顆 cpu 都要有、而且同值（agent.md §2）。
  **實作提醒**：挑欄位解時要帶著原 JSON 的文件與位置去解（例如解 `/llm/params` 就用整份文件、位置 `/llm/params`），不能先切出小物件再解——
  不然 `$ref:""`（指自己這份檔）與相對 `$at`（`./`、`../`）會找錯地方（[directives.md §3.2](../directives/ref.md)）。
- 人格、記憶、工具檔：原樣讀，照 agent.md §3.1～§3.3 驗。**不讀 `state.json`**。

讀驗錯的代號照 [agent.md §5](../agent/errors.md)。

# 4. 組 body

- 人格 `content` 非空 → 第一則 `{"role": "system", "content": …}`；後面原樣接記憶陣列。
- 工具照檔案順序合併，每個元素拿掉所有 `_` 開頭的頂層 key（`_meta`、`_timeout_ms`…）；合併後是空陣列就不送 `tools`。
- `info.llm.params` 併進 body；其中 `model`、`messages`、`tools`、`stream` 四個 key 忽略。
- `body.model`＝llm.json 那筆的真名；`stream` 不送（不串流）。

# 5. HTTP、驗、輸出

（09-24 第 4 隊補）拿到 2xx、本文是 JSON 物件時，另外追加一行到 `<AGENT_DIR>/log/usage.jsonl`（端點回的 `usage`、批 id 取自環境變數 `AOS_LLM_BATCH`；[agent/events.md §2](../agent/events.md)）；寫不進去不影響輸出與退出碼。這是 aos-llm 唯一寫的檔。

`POST <endpoint 去掉結尾的 />/chat/completions`，JSON body；`api_key` 是非空字串才帶 `Authorization: Bearer <key>`。
不串流、不重試；整次請求的上限＝llm.json 那筆的 `timeout_ms`。

回來之後依序：2xx → 是 JSON 物件 → 有 `choices[0].message` 且是物件 → 正規化（下面）→ 照 [agent.md §3.2](../agent/info.md) 驗成**模型回的 assistant**
（`role` 是 `assistant`；`content` 字串或 null、null 時 `tool_calls` 非空；`tool_calls` 每項 `id` 非空字串、`type` 是 `function`、
`function.name` 非空字串、`function.arguments` 是字串、`id` 不重複）。任何一步不過＝`EngineFailed`。

正規化只有兩件，**照這個順序**：① `tool_calls` 是空陣列 → 拿掉這個 key；② 這時 `content` 是 null 又沒有 `tool_calls` → 補成 `""`。其他欄位原樣留著。
（所以 `{"content": null, "tool_calls": []}` 會變成 `{"content": ""}`、驗得過。）

| 結果 | stdout | stderr | 退出碼 |
|---|---|---|---|
| 成功 | 那個 message 物件，**一行** JSON（`ensure_ascii=False`，結尾一個換行） | 無 | 0 |
| HTTP 逾時 | 無 | `aos-llm: Timeout: <白話>` | 1 |
| 連不上、非 2xx、不是 JSON、缺 message、message 驗不過 | 無 | `aos-llm: EngineFailed: <白話>`（非 2xx 附狀態碼與回應開頭一段） | 1 |
| 設定、agent 家、代號讀驗錯 | 無 | `aos-llm: <代號>: <白話>` | 1 |
| 用法錯 | 無 | argparse | 2 |

（09-24 試玩 r2 補）`Timeout` 與 `EngineFailed` 的白話尾巴都附 `（endpoint <endpoint>，模型 <代號>→<真名>）`，不印 `api_key`。

stdout 只會有這一行，所以工作 inst 把 stdout 指到一個檔，agent 就能整份讀回來；失敗時 stdout 是空的，詳細原因在工作 inst 指定的 stderr 檔（aos-agent 用 `log/llm.err`）。
