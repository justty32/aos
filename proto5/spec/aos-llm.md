# aos-llm：問模型（程式規範）

← [proto5 README](../README.md)｜資料夾：[agent.md](agent.md)｜誰叫它：[aos-agent.md](aos-agent.md)｜它跑在哪：[cpu.md §4.1](cpu.md)、[kernel.md §1.1](kernel.md)

> 第 2 版，2026-09-24 定稿，2026-09-24 fix-r4 改命令列（`aos-llm-call` 改成 `aos-llm call`）；已實作（`lib/aos_llm_call.py`＋`cli/aos-llm`）。輪次、審查與實作沿革在檔尾〈沿革〉（09-24 試玩 r3 搬）。

一句話：**`aos-llm call AGENT_DIR` 讀 agent 的模型輸入與這顆 cpu 的模型表，呼叫一次模型，把一則 assistant message 印成一行 JSON。**
它不寫記憶、不碰 `state.json`、不跑工具，跑完就走。它是 kernel 排給 llm 池某顆 cpu 的一份普通工作；
模型表、金鑰、`aos-llm call` 自己在哪，全是那顆 cpu 的環境給的（「cpu 的環境＝工作的環境」）。

## 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| llm cpu | kernel 裡池標 `llm`（或 agent 的 `info.llm.pool`）的一顆普通 exec cpu；它的 `envs` 放 PATH、金鑰、`AOS_LLM_CONFIG` |
| llm.json | 模型表：代號 → endpoint、真名、金鑰、HTTP 逾時。住在 llm cpu 那邊，agent 家裡沒有 |
| 代號 | agent `info.llm.model` 寫的名字（例如 `small`），在 llm.json 的 `models` 裡查真名 |

## 1. 用法與環境

```
aos-llm call [AGENT_DIR]    # （09-24 fix-r4 改）舊的 aos-llm-call 拿掉；之後 llm 相關的子命令都掛在 aos-llm 底下
aos-llm -h ／ aos-llm call -h
```

`AGENT_DIR` 留空＝`.`（目前資料夾）；必須是 agent 家（[agent.md §1](agent.md)）。沒有別的旗標。裸 `aos-llm`（沒子命令）＝用法錯 2（09-24 fix-r4 補）。

要的環境（都由那顆 llm cpu 給，[kernel.md §1.1](kernel.md) 的 `info.cpus.<c>.envs` 會抄進它的 inst）：

| 變數 | 用途 | 沒有時 |
|---|---|---|
| `AOS_LLM_CONFIG` | llm.json 的**絕對路徑** | 沒設、空字串、不是絕對路徑＝`ConfigInvalid`，退 1 |
| `PATH` | 找得到 `aos-llm` 本身（工作 inst 的 `argv` 寫 `["aos-llm", "call", <agent 家>]`） | 那件工作是 exit 127 |
| 金鑰變數 | llm.json 裡 `$env` 讀的 | `EnvironmentVariableMissing`，退 1 |

K 的 info 例子：

```json
"llm": {"pool": "llm",
        "envs": {"PATH": {"$fmt": {"$val": "/abs/proto5/cli:${p}", "p": {"$env": "PATH"}}},
                 "AOS_LLM_CONFIG": "/abs/llm-home/llm.json",
                 "LMSTUDIO_KEY": {"$env": "LMSTUDIO_KEY"}}}
```

`envs` 只在那顆 cpu 第一次建家時抄進去；之後要改得照 kernel.md §1.1 的步驟（stop、改 `K/cpus/<c>/inst.json`、boot）。
llm.json 本身可以隨時改，下一次問就生效（每次跑都重讀）。

## 2. llm.json

（09-24 試玩 r3 改）例子用 LiteLLM；任何 OpenAI 相容端點都行。

```json
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"small": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat",
                      "api_key": {"$env": "LITELLM_KEY"}, "timeout_ms": 120000}}}
```

- 整份解指示詞，中心是 llm.json 所在的資料夾；`$env` 讀的是 aos-llm call 自己的環境（＝那顆 cpu 的環境）。頂層整份不能是指示詞。
- 讀不到＝`ReadFailed`；不是 JSON＝`JsonSyntax`；頂層不是物件＝`NotAnObject`；指示詞錯照 [directives.md §6](directives.md)。

| 鍵 | 型別 | 沒寫時 | 不合 |
|---|---|---|---|
| `_metainfo` | 物件，`_type`＝`"llm_config"`、`_version`＝整數 1（bool 不算） | 必填 | 沒寫、不是物件、缺 `_type` 或缺 `_version`、`_type` 不是 `"llm_config"`＝`ConfigInvalid`；有 `_version` 但不是整數 1（含 bool）＝`UnsupportedVersion`。`_metainfo` 裡其他 key 忽略 |
| `models` | 物件，key 是代號 | 必填 | `ConfigInvalid` |
| `models.<代號>.endpoint` | 非空字串 | 必填 | `ConfigInvalid` |
| `models.<代號>.model` | 非空字串（真名） | 必填 | `ConfigInvalid` |
| `models.<代號>.api_key` | 字串或 `null` | 不帶 | `ConfigInvalid`；空字串＝不帶 |
| `models.<代號>.timeout_ms` | 正整數（bool 不算） | 120000 | `ConfigInvalid` |
| 其他 key | — | — | 忽略 |

整份一起驗：任何一筆形狀不對整份不收，不只看用到的那筆。`info.llm.model` 的代號不在 `models` 裡＝`UnknownModel`。

## 3. 讀 agent 家

跑起來那一刻才讀（所以排隊期間人改了人格、記憶、工具，問的是改過的）：

- `info.json`：讀 JSON（`ReadFailed`／`JsonSyntax`／`NotAnObject`），頂層不能是指示詞；然後**只解驗六格**：`_metainfo`、`system`、`history`、`tools`、`llm.model`、`llm.params`，
  規則照 [agent.md §3](agent.md)（中心 agent 家，`$env` 在這顆 cpu 的環境解）。`llm` 本身要是物件（先不解它，只取 `model`、`params` 兩格各自解）；
  其他格（`llm.pool`、`llm.timeout_ms`、`tool_pool`、`tick`、不認得的 key）**不解、不驗**，那是 aos-agent 的事。
  所以六格以外的 `$env` 只要 agent 那顆 cpu 有就行；六格裡的 `$env` 兩顆 cpu 都要有、而且同值（agent.md §2）。
  **實作提醒**：挑欄位解時要帶著原 JSON 的文件與位置去解（例如解 `/llm/params` 就用整份文件、位置 `/llm/params`），不能先切出小物件再解——
  不然 `$ref:""`（指自己這份檔）與相對 `$at`（`./`、`../`）會找錯地方（[directives.md §3.2](directives.md)）。
- 人格、記憶、工具檔：原樣讀，照 agent.md §3.1～§3.3 驗。**不讀 `state.json`**。

讀驗錯的代號照 [agent.md §5](agent.md)。

## 4. 組 body

- 人格 `content` 非空 → 第一則 `{"role": "system", "content": …}`；後面原樣接記憶陣列。
- 工具照檔案順序合併，每個元素拿掉所有 `_` 開頭的頂層 key（`_meta`、`_timeout_ms`…）；合併後是空陣列就不送 `tools`。
- `info.llm.params` 併進 body；其中 `model`、`messages`、`tools`、`stream` 四個 key 忽略。
- `body.model`＝llm.json 那筆的真名；`stream` 不送（不串流）。

## 5. HTTP、驗、輸出

`POST <endpoint 去掉結尾的 />/chat/completions`，JSON body；`api_key` 是非空字串才帶 `Authorization: Bearer <key>`。
不串流、不重試；整次請求的上限＝llm.json 那筆的 `timeout_ms`。

回來之後依序：2xx → 是 JSON 物件 → 有 `choices[0].message` 且是物件 → 正規化（下面）→ 照 [agent.md §3.2](agent.md) 驗成**模型回的 assistant**
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

## 6. 兩個逾時各管什麼

| 逾時 | 設在哪 | 管什麼 | 撞到時 agent 看到 |
|---|---|---|---|
| 內圈：HTTP | llm.json 那筆的 `timeout_ms`（預設 120000） | aos-llm call 等模型回話多久 | 回音 `kind=child`、`code=1`；原因在 `log/llm.err` 的 `Timeout` 行 |
| 外圈：工作 | agent 的 `info.llm.timeout_ms`（預設 125000），就是 kernel `add` 的 `timeout_ms` | 這件工作在 cpu 上整個跑多久（含讀檔、組 body、HTTP），到了 cpu 砍整組 | 回音 `timed_out=true` |

外圈設得比內圈大一點，正常是內圈先到、aos-llm call 自己乾淨地退 1；外圈只是保險（例如 DNS 卡住）。兩者都不含在 kernel 排隊的時間。
agent 看不到 llm.json（它在 llm cpu 那邊、金鑰也只在那邊），所以外圈只能由 agent 自己的 `info.llm.timeout_ms` 給，兩邊要人自己配好。
兩種逾時對 agent 都是「問模型失敗一次」（[aos-agent.md §6.1](aos-agent.md)）。

## 7. 給程式用

```python
body = aos_llm_call.build_request(agent_dir, config)   # 只組、不打；config 是讀驗好的 llm.json
msg  = aos_llm_call.call(agent_dir)                    # 讀 AOS_LLM_CONFIG、組、打、驗，回 message dict；失敗丟帶 code／msg 的例外
```

## 8. 這份沒管的

串流、重試、多個 choices、token 計數；記憶太長；llm.json 的管理介面（使用者構想的 `aos-agent llms`，[thinking/aos-agent.md](../../thinking/aos-agent.md)）；
同一顆 cpu 服務多份不同的 llm.json（要不同表就開不同池的 cpu）。

## 9. 已拍板的前提（使用者定的，不重問）

1. **沒有同步工具**：問模型是往 kernel `add --once` 的普通工作，這支程式就是那件工作的 `argv[0]`。取捨：最快也要等一格 tick。
2. **agent 先進現有的池**：問模型派往 `info.llm.pool` 那個現有的池，不給 agent 開專屬 cpu。
3. **llm.json 放 llm cpu 那邊**（cpu 的環境＝工作的環境）：模型表（endpoint／真名／api_key／timeout_ms）跟 aos-llm call 同住，
   靠那顆 cpu 的 `envs` 設 `AOS_LLM_CONFIG=/abs/llm.json` 找到；agent 的 `info.llm` 只剩 `model`、`params`、`pool`、`timeout_ms`。

## 調度者裁決（第 2～3 輪，實作層級）

1. llm.json 的 `_metainfo` 必填，`_type` 叫 `llm_config`、`_version` 只認整數 1。
2. 設定錯的代號用新的 `ConfigInvalid`（不是沿用舊名；舊 llm-cpu 叫 `EngineInvalid`）；讀檔、JSON、指示詞錯用各自原本的代號。
3. **執行時讀** agent 家：人格、記憶、工具、`info.llm` 在這支程式跑起來那一刻讀，不是 aos-agent 送件那一刻。
4. 模型回的 message 在印之前就照 [agent.md §3.2](agent.md) 驗；不合＝`EngineFailed`，不印。
5. 印之前的正規化只做兩件、順序固定：先拿掉空的 `tool_calls`，再把「`content` 是 null 又沒 `tool_calls`」補成 `""`。
6. `api_key` 空字串＝不帶 `Authorization`，跟 null／沒寫一樣。
7. （第 3 輪）讀 agent 的 `info.json` **只解驗用得到的六格**（§3），其他格原樣不碰——agent 那邊只在自己 cpu 成立的 `$env` 不會讓這裡失敗。

## 沿革

原標題：`aos-llm-call：問模型一次（程式規範，第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；已實作）`

> 2026-09-23 草稿；2026-09-24 照 審查報告「定稿前必改」與使用者三件裁決改成第 2 輪；同日照 第 2 輪審查 改成第 3 輪；第 3 輪審查 判可定稿，第 4 輪只補一條實作提醒。（審查與實作紀錄在 [rearch 筆記](../notes/2026-09-23-rearch/README.md)）
> **已實作**（2026-09-24，T9）：`lib/aos_llm_call.py`＋`cli/aos-llm-call`，實作發現見 agent-impl-findings。
> 這份把兩件事合成一支普通程式。調度者裁決在檔尾（09-24 試玩 r3 搬），已拍板的前提在 §9。
> 2026-09-24 fix-r4：入口 `aos-llm-call` 改成 `aos-llm call`（新入口 `cli/aos-llm`，stderr 前綴 `aos-llm: `），規範檔名 aos-llm-call.md 改成 aos-llm.md。
