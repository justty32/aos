← [agent](README.md)｜[spec 總導航](../README.md)

# 事件紀錄 `log/events.jsonl` 與用量 `log/usage.jsonl`

（09-24 工具大開發時代第一波第 4 隊，T-events）量六軸要從地基記：每批什麼時候開始、什麼時候結束、成不成、花多久、用了多少 token。
人看：`aos-agent events [--last N] [--usage] [--json]`（[cli-memory.md](../aos-agent/cli-memory.md)）。實作 [`lib/aos_agent_events.py`](../../lib/aos_agent_events.py)。

## 1. `log/events.jsonl`

agent 家裡一行一個 JSON 物件，只追加。共同欄位：

| 鍵 | 意思 |
|---|---|
| `at` | 本機時間 ISO 8601，到毫秒、帶時區 |
| `ev` | 事件種類（下表） |
| `id` | 去重用的身分：批 id（建批時存在 `batch.id`；改版前的批從工作名去掉最後的 `-<序號>` 推，例 `aw-bob-1790000000000000000-77`）、消費 id、或壓縮前記憶的 sha；沒有＝`null` |

| `ev` | 什麼時候記 | 其他欄位 |
|---|---|---|
| `intake` | idle 收完輸入、寫完記憶，提交 state 之前 | `files`（收到的原檔名）、`messages`（接進記憶幾則） |
| `think_start`／`act_start` | 一批全部送出，提交 `sent: true` 之前 | `base_len`；act 另有 `tools`（每個 call 的工具名，照順序） |
| `think_end` | 結清，提交 `batch: null` 之前 | `ok`、`ms`；失敗另有 `reason`（白話）、`count`（算不算一次連敗）；成功另有 `tool_calls`（模型這次叫了幾個工具） |
| `act_end` | 同上 | `ok`（全部成功才 true）、`calls`：`[{"tool", "ok", "ms"}]`（沒送出去的那種——沒這個工具、被權限牆擋——`ok: false`、`ms: null`） |
| `compact` | 壓縮寫完 archive、換記憶之前（[compact.md](compact.md)） | `auto`、`reason`、`keep_rounds`、`max_tokens`、`before`／`after`（`{count, tokens}`）、`over`、`archive` |
| `compact_fail` | 自動壓縮或申請做不成 | `auto`、`reason`、`error` |

- `ms` 是 kernel 回音裡的**經過時間**，不是 cpu 秒；cpu 秒與記憶體這版不記（`null` 就是沒有）。
- 收回時把回音的 `ms` 與「這件成不成」記在 `batch.calls[]` 的 `ms`、`ok` 兩個鍵（[state.md §4.3](state.md) 允許的額外鍵，讀驗不看），結清時才寫進事件；所以崩在收回與結清之間也不會丟。
- **寫的人只有一個**：持 `.tick.lock` 的那一方（tick 本身，或 `aos-agent compact`）。
- **至少一次**：每個事件都在「提交那一步」之前寫；崩了重做會再寫一次同一行（同 `ev`＋`id`）。讀的人照 `ev`＋`id` 去重（`id` 是 `null` 的不去重），`aos-agent events` 已經去重。所以行程崩潰只會「記了兩次」，不會「做了沒記」；例外是寫檔本身失敗（下一條）。上一行寫到一半（短寫）時新行先補換行，不黏在一起。
- **寫不進去不擋路**：`log/` 不能寫、磁碟滿，只丟掉這一行，tick 照常。壞掉的行（寫到一半、手改壞）讀的時候跳過。
- 追加是一次 `write`（`O_APPEND`），一行在幾 KB 以內。檔案不輪替、不清；要清就在 agent 停著時自己刪（刪了只是少了歷史）。

## 2. `log/usage.jsonl`

`aos-llm call` 拿到 2xx、而且本文是 JSON 物件時追加一行（不管 message 驗不驗得過）：

```json
{"at": "2026-09-24T18:20:01.123+08:00", "batch": "aw-bob-1790000000000000000-77", "alias": "default",
 "model": "deepseek-chat", "ms": 2310, "usage": {"prompt_tokens": 812, "completion_tokens": 40, "total_tokens": 852}}
```

- `batch`：環境變數 `AOS_LLM_BATCH`；aos-agent 送 think 時把它寫進那件工作 inst 的 `envs`（[send.md §5.4](../aos-agent/send.md) 的 inst 多這一格）。手動跑、改版前寫的 inst＝`null`。
- `usage`：端點回的原樣（沒回＝`null`）；`ms` 是這次 HTTP 花的時間。
- 寫的人只有 `aos-llm call`；一個 agent 同時最多一個 think 在跑（被取消的舊問可能重疊，各寫各的一行，不會交錯）。寫不進去不影響這一問。
- 事件與用量用批 id 對得起來：`think_start`／`think_end` 的 `id` ＝ 用量的 `batch`。
