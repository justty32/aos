> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# call-loop — 工具怎麼被呼叫、結果怎麼回來

← [tools/README](README.md)｜登記表 [registry](registry.md)｜表述 [description](description.md)

現況（`core/agent/src/step.cpp`、`tools.cpp`）：N 回合 `step` 投遞工具 inst、N+1 loop 執行、N+2 `step` 收 `batch/N+1/out/<id>.json` 並**立刻**再思考——結果延遲兩回合。
版控規則同 heartbeat：登記表是靜態清單進版控；`batch/`、`pending`、`ask/` 是動態狀態不進。

## 一、對照 `tools.cpp`／`step.cpp` 的差異清單

| 現況（行號） | 問題 | 改法選項 |
|---|---|---|
| `{args}` 單字串代入（`tools.cpp:92–105`） | 把 `"-la ."` 塞成一個 argv，斷掉 PROTOCOL §2 的 list | A 保留只給 `sh`；**B 登記 `args: list\|string`，list 逐項展開**；C 具名槽 |
| 未知工具只寫 note（`step.cpp:183–186`） | 模型收不到、不能改選 | A 維持；**B 下回合送結構化 `tool` 錯誤**；C 當 step 失敗 |
| `args` 非字串就 `nullopt`（`tools.cpp:127–130`） | 型別錯與「沒呼叫」不可分 | A 維持；**B 依登記 `args` 型別回 `invalid_args`** |
| 只投一條（`step.cpp:170–176`，id 尾 `-0`） | 不能並行 | A 限一條；**B 末行 JSON array 投 `-0,-1…`**；C 原生 tool calls |
| pending 只認 `pending.turn+1/out`（`step.cpp:108–129`） | 慢跑／補跑／外部結果收不到 | A 維持；B pending 記 id、掃後續 batch |
| 結果拼成文字、各截 4000 字（`step.cpp:34–76`） | signal／時間／機讀欄位消失 | A 保留；**B `tool` 訊息放固定 JSON**；C 大輸出落檔只帶路徑 |
| 名冊住 `agents/<name>/tools.json`（`paths.cpp:70`） | 世界工具與 agent 准入混為一談 | 見 [registry](registry.md) 一 |

## 二、三回合往返要不要壓

| 選項 | 延遲 | 動 core/loop？ | 代價 |
|---|---|---|---|
| A 不壓，回合制就是這樣 | N→N+2 | 否 | 互動慢；但語意最乾淨 |
| B step 內同步 fork 工具 | N 內 | 否 | **繞過 `batch/` 帳本，跟 pi 同病**；不建議 |
| C loop 加「尾巴批」：一批完成後若 out 產生新 inbox inst，同回合再跑一批 | N→N+1 | **是**，改 PROTOCOL §5 | 「一回合一批」不再成立；要設尾巴上限、補恢復語意 |
| D 收結果同 step 立刻思考 | N→N+2 | 否 | **已是現況** |

**建議**：原型維持 A／D；互動速度真成痛點再做 C（每回合最多一尾巴批）。

## 三、錯誤怎麼結構化退回

選項：A 繼續拼文字（最省，但模型要猜格式）；**B 所有結果用同一 `tool` 訊息、content 是固定 JSON**；C 用後端原生 tool-result（要先接 `aos llm --tools`，見 [description](description.md)）。

B 的固定形狀（成功也同形，`error` 缺席即成功）：

```json
{"call_id":"agent-bob-tool-7-0","tool":"ls","ok":false,"result":null,
 "error":{"type":"unknown_tool","message":"沒有登記 lss","retryable":false}}
```

| 情況 | `error.type` | `result` | `retryable` 來源 |
|---|---|---|---|
| 不在名冊 | `unknown_tool` | null | false |
| args 型別不符登記 | `invalid_args` | null | false |
| exit≠0 | `exit_nonzero` | 完整 PROTOCOL §3 結果 | 登記項 `exit_codes[code].retryable`，缺席 false |
| 逾時 signal 9 | `timeout` | 完整結果 | true，但**不自動**重投 |
| exec 126／127 | `not_executable`／`not_found` | 完整結果 | false |

截斷時加 `truncated: true`。**自動重投**要同時滿足 `retryable`＋登記 `guarantee: idempotent`＋重試預算——原型先不做，只把錯誤交回模型。代價：多一個 schema、舊 history 有相容期。

## 四、危險工具要不要問人

| 選項 | 內容 | 代價 |
|---|---|---|
| A 不管 | 沿 verdicts「權限／安全交上層」；名冊只描述可用工具 | 把 `sh` 登記給模型＝信任啟動 loop 的人 |
| B 登記 `confirm: true` | 投遞前寫進 `agents/<name>/ask/`、`aos agent state` 顯示 waiting、人用 `aos say` 批准 | 要 request id、批准綁定、逾時／重啟語意 |
| C 白名單即安全 | 不在名單不能叫 | 把可見性誤當安全；名單內的 `sh` 照樣危險 |

**建議**：原型 A；要把 agent 交給非開發者用時才加 B。C 不該宣稱提供安全。

## 五、pi 引擎繞過 inst 的洞

`engine_pi.cpp:131–138` 已解析 `tool_execution_start` 但只縮成字串；`PI_OFFLINE=1 pi --help` 證實有 `--tools` allowlist、`--no-builtin-tools`、`--extension`，而現行 argv 用了 `--no-extensions`（`engine_pi.cpp:52–55`）。

| 接法 | 帳本完整度 | 改動量 | 回合延遲 |
|---|---|---|---|
| **A 事件回填**：`step_pi` 把每對 start/end 寫成 `batch/<turn>/out/<step-id>-tool-<k>.json`，形狀套 §3，`exit` 由 `isError` 合成，加 `origin:"pi"`、`pi_call_id`、`tool_name`、`args` | 高（動作＋結果可追，但 exit 是合成值不是 POSIX status） | 中，只動 `engine_pi.cpp` | 0 |
| B 收窄成一個自訂 `aos_deliver` 工具（extension＋`--tools aos_deliver`），強迫 pi 走 inbox | 完整（真 inst） | 大；extension 自訂 tool ABI 尚未驗 | 工具 N+1、收 N+2 |
| C 接受洞、只記 log | 只有最後文字 | 0 | 0 |

**建議**：先 A，誠實標 `origin:"pi"`；B 留給「統一治理」那天。代價：A 的帳本是觀測紀錄、不可重播。

## 六、多步工具鏈

| 選項 | PROTOCOL 現有機制夠嗎 | 代價 |
|---|---|---|
| A 只允許一個（現況） | 夠 | 串接靠下一次思考，慢 |
| **B call array 並行**，投 `-0,-1…`，pending 已是 calls array 且 all-of 等結果 | 夠（§5 本來就並行） | 改 parser／deliver／prompt |
| C `stdin: {"from":"<id>"}` 引用前一條 stdout | **不夠**：§2 stdin 只許字串、同批沒有資料流 | 要 DAG、拓撲排程、失敗規則，動 core/loop |
| D 交給 `sh -lc` | 夠 | 帳本只見一個 shell tool，可觀測性下降 |

**建議**：先 B；C 暫緩；D 當有意識的逃生門。
