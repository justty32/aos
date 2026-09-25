← [daemon／kernel 調查報告（astra）](../2026-09-22-daemon-kernel-report-astra.md)（分檔 5/6）｜所在：3. aos-kernel｜[上一份](04-aos-kernel-崩潰到llm介面.md)｜[下一份](06-文件落差與proto5相容.md)

**3.16 `K/llm/` 檔案與完整欄位**

| 路徑 | 格式／誰寫誰讀 | 搬移／刪除 |
|---|---|---|
| `endpoints.json` | module 初建範例；使用者改；handle/tick/worker/status 讀 | `.tmp`→replace |
| `requests/<id>.json` | request＋`_aos`；handle submit 寫；tick 讀 | dispatch 時 replace 到 running；壞單移 done |
| `requests/running/<id>.json` | 帶 worker metadata 的 request；tick 寫；worker/後續 tick 讀 | 結果存在、worker 死或逾時後移 done |
| `requests/done/<id>.json` | 原 request 與既有 `_aos` | 保留；llm rm 刪 |
| `results/<id>.json` | worker 或 scheduler 寫結果；CLI／agent 讀 | `.tmp`→replace；llm rm 刪；讀完不刪 |
| `state.json` | 最近 tick 的儀表 | 每 tick 原子覆寫 |
| `usage.jsonl` | worker append，每行 JSON | 不自動清理；llm rm 不刪歷史 |
| `llm-cpu.log` | tick 文字 append | 不自動清理 |
| `log/<id>.log` | worker stderr append | llm rm 不刪 |
| 各 `<path>.tmp` | 原子發佈暫存 | 正常 replace；沒有通用回收 |
| `inst.json` | module 模式**不建立** | 獨立 llm-cpu 模式才有 |

LLM `atomic_json()` 會 fsync **檔案**後 replace，但沒有 fsync 父目錄。其 syscall 發佈包了兩層暫存，會先經 `<ticket>.json.tmp.tmp`，再到 `.tmp`，最後正式 `.json`。

來源：[llm_cpu_home.py:15](../../../proto4-5/llm_cpu_home.py)、[llm_cpu_home.py:43](../../../proto4-5/llm_cpu_home.py)、[llm_cpu_module.py:218](../../../proto4-5/llm_cpu_module.py)。

`endpoints.json`：

| 欄位 | 型別 | 預設／要求 |
|---|---|---|
| `default` | 字串 | 初建 `"local"` |
| `endpoints` | 物件陣列 | 初建只一個 local；name 不可重複 |
| `endpoints[].name` | 字串 | 初建 `"local"`；home loader 要字串，實際呼叫再要求非空 |
| `.kind` | 字串 | 初建 `"openai"`；排程只接受 openai |
| `.base_url` | 非空字串 | 初建 `http://localhost:1234/v1` |
| `.model` | 非空字串 | 初建 `"loaded-model-id"` |
| `.max_concurrent` | 正整數，非 bool | 初建 `1`；排程必需 |
| `.timeout_ms` | 正整數，非 bool | 初建 `300000`；排程必需 |
| `.enabled` | 預期布林 | 省略當 true；必須是 `True` 才派工 |
| `.api_key_env` | 非空字串，可省 | 指環境變數名稱，未提供則不加 Bearer key |
| `.strict_model` | 布林，可省 | 呼叫層預設 true |

LLM request：

| 欄位 | 型別／預設 | 驗證／用途 |
|---|---|---|
| `messages` | 非空陣列，必填 | 排程只驗陣列非空；元素沒有完整 schema 驗證 |
| `endpoint` | 字串，可省 | 省略用 endpoints.default；須存在 |
| `priority` | 整數，非 bool；預設0 | 越大越先，允許負數 |
| `timeout_ms` | 正整數，非 bool，可省 | 省略使用 endpoint timeout |
| `params` | 物件，可省 | 併入 HTTP body；model/stream 最後由呼叫層覆蓋固定 |
| `tools` | 陣列，可省 | 排程驗證未檢此欄；worker 呼叫層驗陣列，內容原樣傳 |
| `tool_choice` | 任意 JSON，可省 | 呼叫層原樣傳，不驗 schema |
| `id` | 未嚴格驗型別，可省 | worker 會覆蓋成檔名 id |
| `model` | 不允許出現 | 出現即拒絕，即使值為 null |
| `_aos` | 物件 metadata，可省 | submit/dispatch 增補；其他自帶 metadata 可保留 |
| 其他 key | 任意 | 留在儲存 request；HTTP 不會整包原樣傳送 |

`_aos` 全部由現有排程器產生的欄位：

| 欄位 | 型別 | 初值／寫入時機 |
|---|---|---|
| `request_sha256` | 64字元十六進位字串 | submit 算正規化請求指紋 |
| `submitted` | UTC ISO-8601 字串，毫秒精度 | submit 時 |
| `endpoint` | 字串 | dispatch 選定 endpoint 時 |
| `pid` | 整數或 null | dispatch 先 null；worker Popen 後改 Linux PID |
| `started` | number | dispatch 的 `time.time()` |

指紋是 `sort_keys=True`、緊湊 JSON、UTF-8 的 SHA-256；會排除 `_aos` 裡上述五個排程器欄位。**不會補齊 endpoint/default、priority 等語意預設再比較**，所以省略預設與明寫預設不必然是相同指紋。

同名查找順序：requests → running → results → done。內容同指紋視為既有同單；不同則拒絕。CLI 命中同單可直接成功或等既有 result，無須 kernel 活著。

來源：[llm_cpu_home.py:115](../../../proto4-5/llm_cpu_home.py)、[llm_cpu_request.py:21](../../../proto4-5/llm_cpu_request.py)、[llm_cpu_tick.py:110](../../../proto4-5/llm_cpu_tick.py)、[aos_llm.py:89](../../../proto4-5/aos_llm.py)。

result 全欄位：

| 欄位 | 型別／值 | 寫入與含義 |
|---|---|---|
| `ok` | boolean | 成功／失敗 |
| `id` | 字串 | request 檔名 id |
| `endpoint` | 字串或 null | 選定 endpoint；無法辨識時 null |
| `model` | 供應商原值，通常字串或 null | 實際回應 model；無有效回應通常 null |
| `model_requested` | 字串或 null | endpoint 設定的 model |
| `text` | 供應商 content 原值，通常字串或 null | 不做嚴格字串驗證 |
| `finish_reason` | 供應商原值或 null | 第一個 choice 的 finish_reason |
| `usage` | 物件 | 下列五欄 |
| `usage.prompt` | 通常整數或 null | prompt_tokens 原值 |
| `usage.completion` | 通常整數或 null | completion_tokens 原值 |
| `usage.total` | 通常整數或 null | total_tokens 原值 |
| `usage.cached` | 通常整數或 null | prompt_tokens_details.cached_tokens 原值 |
| `usage.reasoning` | 通常整數或 null | completion_tokens_details.reasoning_tokens 原值 |
| `ms` | 整數 | 呼叫耗時毫秒；scheduler 自造錯誤為0 |
| `raw` | 任意 JSON 或 null | 原供應商資料；不限定額外欄位 |
| `notes` | 陣列 | worker 呼叫結果有，通常 `[]`；**scheduler 的 `_error_result()` 不寫此欄** |
| `notes[].kind` | 字串 | 目前可有 `model_preflight_skipped` |
| `notes[].msg` | 字串 | 預檢失敗但仍送 chat 的說明 |
| `notes[].error` | 錯誤物件 | 預檢錯誤，形狀同 error |
| `error` | null 或物件 | 成功 null；失敗如下 |
| `error.kind` | 字串 | 錯誤種類 |
| `error.msg` | 字串 | 錯誤說明 |
| `error.status` | 整數或 null | HTTP status 或無 |
| `error.retryable` | boolean | 資訊標記，沒有自動重試 |
| `request_sha256` | 字串或 null | worker／scheduler 加到結果，供同單辨識 |

`raw` 的供應商資料不是 kernel 定義的固定 schema；agent 用到其中的 `choices[0].message`，包含可能的 `tool_calls`。

來源：[aos_llm.py:24](../../../proto4-5/aos_llm.py)、[aos_llm.py:186](../../../proto4-5/aos_llm.py)、[llm_cpu_tick.py:15](../../../proto4-5/llm_cpu_tick.py)、[llm_cpu_worker.py:37](../../../proto4-5/llm_cpu_worker.py)。

其他 JSON：

| 檔／欄位 | 型別、初值、寫入者 |
|---|---|
| state `ticks` | 整數，初值0；每次成功走到存檔的 llm tick＋1 |
| state `running` | 整數，初值0；running 數量 |
| state `endpoints` | 物件，初值 `{}`；endpoint name→running 整數 |
| usage `at` | UTC ISO 字串；worker 寫 |
| usage `id` | 字串 |
| usage `endpoint` | 字串或 null |
| usage `model` | 供應商原值或 null |
| usage `prompt` | token 原值或 null |
| usage `completion` | token 原值或 null |
| usage `total` | token 原值或 null |
| usage `cached` | token 原值或 null |
| usage `reasoning` | token 原值或 null |
| usage `ms` | 整數 |
| usage `ok` | boolean |

usage 由 worker 寫結果後 append；scheduler 自己退的壞單、spawn 失敗等沒有經 worker 的 usage 寫入路徑。

**3.17 LLM 每格排程與生命週期**

| 次序 | 動作 |
|---|---|
| 1 | 讀 endpoints；失敗只記 emergency log，這格返回 |
| 2 | 收 running：result 存在即搬 request 到 done |
| 3 | running metadata 壞／worker PID 不活且無 result | 寫 `worker_died` result，再搬 done |
| 4 | worker 超過 request/endpoint timeout＋5000ms | TERM worker PID，寫 timeout result，搬 done |
| 5 | 驗 queued requests | 壞單寫 bad_request result，搬 done |
| 6 | 排序 | priority 降冪 → request mtime_ns 升冪 → 檔名字典序 |
| 7 | 派工 | endpoint 未滿 max_concurrent 才派；request 加 metadata，移 running，開背景 worker |
| 8 | worker 啟動 | Python subprocess，`start_new_session=True`，stdin/stdout `/dev/null`，stderr 寫 log/id.log |
| 9 | Popen 失敗 | 寫 spawn result，request 搬 done |
| 10 | 寫 state、append llm-cpu.log | state 只是最近儀表；資料夾位置與 result 才是各單現況 |

worker 不透過 daemon add，也不占用 `K/cpus/n.json` 的一個普通行程槽。kernel tick 結束後它仍可繼續。沒有通用「daemon stop 就收掉所有 LLM worker」的路徑。

來源：[llm_cpu_tick.py:72](../../../proto4-5/llm_cpu_tick.py)、[llm_cpu_tick.py:192](../../../proto4-5/llm_cpu_tick.py)、[llm_cpu_tick.py:231](../../../proto4-5/llm_cpu_tick.py)。

**3.18 kernel 必須支撑的既有使用事實**

| 使用者 | 現有依賴 |
|---|---|
| proto4-5 LLM module | config module 路徑、NAME/OPS、四 hook、syscall request/done、每 tick 呼叫 module |
| LLM 背景 worker | kernel module 的同步一格能派出跨 tick 存活的 subprocess |
| LLM 呼叫者 | syscall 成功與模型完成分兩階段；以 result 檔出現判斷結果 |
| proto4-7 agent idle | 沒信時保存自身狀態，退出101 |
| agent ask | 組 messages/tools，透過 `aos_py.llm_submit()` 呼叫 `aos-kernel llm ... --name ...`；不加 `--wait`；成功保存 result 路徑，退出0 |
| agent wait | result 未出現時退出101；由 agent 自己數到600次檢查，不是 kernel 的等待期限 |
| agent 結果處理 | 讀 `ok/error` 與 `raw.choices[0].message`，不是讀 syscall msg |
| agent 收工 | `agent.json.stop is true` 時退出100 |
| agent 錯誤 | 一般模型錯誤自行記帳，通常退出0；設定／資料等真正錯誤退出1 |
| agent kernel 設定 | README 要求使用 `bad_after=0`；這不關掉 kernel 的 aos 自身失敗退件 |
| agent 請求身份 | `<name>-e<epoch>-q<question>-s<step>`；reset 增 epoch，避免撞舊單 |
| result 保存 | agent 不替 LLM 排程清帳，結果保留在 K |

這些是現有程式的依賴；**沒有要求 kernel 知道 agent 的四格、信箱、工具或 messages 格式**。

來源：[proto4-5/README.md:101](../../../proto4-5/README.md)、[proto4-7/README.md:57](../../../proto4-7/README.md)、[state_machine.py:94](../../../proto4-7/state_machine.py)、[state_machine.py:172](../../../proto4-7/state_machine.py)、[aos_py.py:150](../../../proto4-6/aos_py.py)。

**3.19 錯誤代號**

kernel 核心自己的 CLI／syscall **沒有統一具名 error code**，多為中文 msg＋退出1/2。inst 驗證則保留下列 `InstError.code`：

| 代號 | 現在用途 |
|---|---|
| `ReadFailed` | inst 讀不到 |
| `JsonSyntax` | inst JSON 語法錯 |
| `NotAnObject` | 頂層解完非物件 |
| `MetainfoInvalid` | metainfo 非物件或缺必要欄位；null 例外被當預設 |
| `UnsupportedInstType` | `_type` 不是 `"posix"` |
| `UnsupportedInstVersion` | `_version` 不是整數1，bool 也拒絕 |
| `EmptyArgv` | argv 缺少、空，或第一項空字串 |
| `FieldTypeMismatch` | 欄位解完型別不符 |
| `EnvKeyInvalid` | 環境 key 不合法 |
| `UnknownDirective` | 不認得的指示詞 |
| `DirectiveValueTypeMismatch` | 指示詞／選項值型別不符 |
| `FormatVariableInvalid` | fmt 變數名不合法 |
| `UnknownOption` | 不支援或重複的 option |
| `OptionConflict` | 選項互斥或帶值條件不符 |
| `EnvironmentVariableMissing` | env 變數不存在 |
| `UnknownFormatVariable` | 模板使用未定義變數 |
| `ReferenceReadFailed` | ref 檔讀不到 |
| `ReferenceJsonInvalid` | ref 檔不是合法 JSON |
| `ReferencePointerInvalid` | pointer 語法／位置不合法 |
| `ReferenceCycle` | 同一解析鏈重遇相同文件及位置 |

來源：[aos_inst.py:76](../../../proto4-3/aos_inst.py)、[aos_inst_resolve.py:27](../../../proto4-3/aos_inst_resolve.py)。

LLM result 的 `error.kind`：

| 種類 | 來源 |
|---|---|
| `bad_request` | 請求／endpoint 不合格 |
| `no_api_key` | 指定環境變數不存在 |
| `http` | HTTP 錯誤 |
| `connect` | 連線錯誤 |
| `timeout` | HTTP timeout，或排程器判 worker 超時 |
| `bad_json` | 回應不是合法 JSON／不是物件 |
| `bad_response` | 回應缺必要結構 |
| `model_not_found` | strict 預檢不含要求模型 |
| `model_mismatch` | 實際回覆模型不符 |
| `worker_died` | running 壞記錄，或 worker 消失無結果 |
| `spawn` | worker 起不來 |
| `internal` | worker 外圍捕捉到其他例外 |

HTTP 429／5xx、一般連線與 HTTP timeout 可標 retryable=true；這個欄位本身不觸發重試。

**3.20 測試旁證範圍**

| 測試 | 已有斷言 |
|---|---|
| [test_kernel_init.py:19](../../../proto4-3/test/test_kernel_init.py) | init 檔案／預設、拒絕重灌、add 正規化／配名、queue 退件、syscall 回音 |
| [test_kernel_exit.py:18](../../../proto4-3/test/test_kernel_exit.py) | waiting 保留／讓位、bad_after、runs 倒退清計數、特殊碼清連敗 |
| [test_kernel_daemon.py:14](../../../proto4-3/test/test_kernel_daemon.py) | boot flags、done、125 退件、FIFO 輪替、CPU 補回、換檔不留空窗 |
| [test_kernel_fix_r6.py:50](../../../proto4-3/test/test_kernel_fix_r6.py) | 清 done/bad、同名重排、daemon 狀態文案、欄寬 |
| [test_module.py:51](../../../proto4-3/test/test_module.py) | module 路徑、tick/status/cli/syscall、缺 module 不打死 tick |
| [proto4-5/test/test_module.py:198](../../../proto4-5/test/test_module.py) | LLM 等回單撤單、結果超時、同名同指紋、既有 result 等待 |

測試沒有把「最新快照推算」變成完整事件歷史，也沒有提供跨 swap 連敗保存、單行程不重疊執行或 crash transaction 的保證。

---

