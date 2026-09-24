本次以工作樹中的程式碼為準，完成唯讀調查，未修改檔案、未呼叫真模型。指定的實作與測試已逐檔閱讀；以下區分「程式實際行為」「既有測試涵蓋」及「由執行順序推導的崩潰／競態窗口」。

最核心的事實是：**proto4-7 把模型請求交給 kernel 的 `llm` module；module 排入檔案佇列，再啟動獨立 OS worker 做同步 HTTP。agent 留下結果檔路徑，日後重新被執行時查檔。kernel 收到 101 後只處理排程，不知道 agent 在等哪個檔。**

這裡稱為「LLM cpu」的 worker，**沒有登記成 `K/cpus/` 裡的一顆普通 cpu**。module 的排程函式在 kernel tick 行程內執行；模型呼叫則在它啟動的背景 worker 行程中執行。[派工實作](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:192)、[kernel 呼叫順序](/home/guanyu/projs/aos/proto4-3/aos_kernel_tick.py:41)

**0．proto5 術語與本次讀到的現況**

| 項目 | proto5 現況 | 與本報告的對照 |
|---|---|---|
| agent 資料夾 | `info.json` 描述設定，`state.json` 記執行狀態 | proto4-7 使用 `agent.json`，沒有這套 `info.json` 格式 |
| 狀態 | `idle → think → act`；`waits` 是進格前的等待表 | proto4-7 有明確的 `ask`、`wait` 兩格，沒有 `waits` 表 |
| 模型設定 | `info.engine`：`endpoint`、`model`、`params`、`api_key`、`timeout_ms` | proto4-5 的 `endpoint` 請求欄位是**設定名稱**；URL 欄位叫 `base_url` |
| 問模型 | `aos_llm_ask.call(engine, body)` 同步回傳 `choices[0].message` | proto4-5 第一層回傳較大的 result envelope，原始 message 藏在 `raw.choices[0].message` |
| 工具 | OpenAI tools 陣列，每個工具另有 `_meta` inst | proto4-7 是 `tools/<名稱>/tool.json` ＋ `run` |
| 記憶 | `info.history` 指向的檔案 | proto4-7 固定 `messages.json` |
| 已存在的實作 | 工作樹已有 `proto5/lib/aos_agent.py`、`proto5/cli/aos-agent`；`think` 第 220 行直接呼叫 `aos_llm_ask.call(...)` | README「程式還沒寫」已落後，不能据此認定只有規範 |

來源：[proto5 agent 格式](/home/guanyu/projs/aos/proto5/spec/agent.md:15)、[三格規範](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:22)、[engine 與請求規範](../../proto5.1/spec/aos-llm-ask.md)、[函式庫說明](/home/guanyu/projs/aos/proto5/lib/README.md:243)、[現有同步 think](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:215)。

---

**1．proto4-5 第一層：`aos-llm`**

**1.1 檔案分工**

| 檔案 | 實際職責 |
|---|---|
| [aos-llm](/home/guanyu/projs/aos/proto4-5/aos-llm:1) | 薄入口，呼叫 `aos_llm.main()` |
| [aos_llm.py](/home/guanyu/projs/aos/proto4-5/aos_llm.py:89) | endpoint／request 驗證、HTTP、模型預檢、result 正規化 |
| [aos_llm_cli.py](/home/guanyu/projs/aos/proto4-5/aos_llm_cli.py:15) | endpoint 檔選取、REQ／OUT 檔案與 stdin/stdout、CLI 退出碼 |
| [llm_cpu_worker.py](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:37) | 第二層的使用者：直接 import `aos_llm.call()`，沒有再啟動 `aos-llm` CLI |

`aos_llm.call(endpoint, req)` 本身不讀寫請求／結果檔；它會讀取 API key 環境變數，並同步存取 HTTP。

**1.2 endpoint 設定檔的兩種形狀**

單一 endpoint：

```json
{
  "name": "local",
  "kind": "openai",
  "base_url": "http://localhost:1234/v1",
  "model": "loaded-model-id",
  "timeout_ms": 300000
}
```

多 endpoint 文件：

```json
{
  "default": "local",
  "endpoints": [
    {
      "name": "local",
      "kind": "openai",
      "base_url": "http://localhost:1234/v1",
      "model": "loaded-model-id",
      "max_concurrent": 1,
      "timeout_ms": 300000
    }
  ]
}
```

| 文件／欄位 | 型別與預設 | 第一層行為 | 第二層差別 |
|---|---|---|---|
| 頂層 `default` | 字串 | 多 endpoint 檔不帶 `#name` 時選它；必須非空且剛好匹配一筆 | `load_endpoints()` 要求字串；請求省略 `endpoint` 時使用 |
| 頂層 `endpoints` | 陣列 | 從中找唯一匹配的 `name` | 每筆須為物件且有字串 `name`；重名使設定載入失敗 |
| `name` | 非空字串 | 必填；寫進 result 的 `endpoint` | 作為容量與請求路由的 key |
| `kind` | 字串，必須 `"openai"` | 必填；其他值 `bad_request` | 同樣只支援 openai；process 尚未實作 |
| `base_url` | 非空字串 | 必填；去尾端 `/` 後接 API 路徑 | 必填 |
| `model` | 非空字串 | `call` 必填；`models` 不要求它存在 | 必填 |
| `enabled` | 省略為 `true` | 必須是 Python 的 `True`，其他值均視為未啟用 | 相同 |
| `timeout_ms` | 正整數，排除 bool | 省略為 `300000` | **必填**，同樣須正整數 |
| `max_concurrent` | 第一層不使用 | 不驗、不影響呼叫 | **必填正整數，排除 bool，至少 1** |
| `api_key_env` | 非空字串，可省略 | 指定環境變數名稱；變數不存在回 `no_api_key` | worker 環境中解析 |
| `strict_model` | bool，省略為 `true` | 控制 `/models` 預檢及回覆 model 比對 | worker 沿用 |
| `argv` | 沒有支援的執行語意 | 不會用來啟動 process endpoint | README 的 process 範例只是保留形狀，仍被拒絕 |
| 其他欄位 | 沒有通用嚴格 schema | 不使用的欄位不會送給供應商 | 不使用的欄位保留在設定物件中 |

來源：[第一層驗證](/home/guanyu/projs/aos/proto4-5/aos_llm.py:45)、[CLI 選 endpoint](/home/guanyu/projs/aos/proto4-5/aos_llm_cli.py:20)、[第二層載設定](/home/guanyu/projs/aos/proto4-5/llm_cpu_home.py:149)、[第二層 endpoint 驗證](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:127)。

API key 細節：

| 情況 | 行為 |
|---|---|
| 沒寫 `api_key_env` | 不送 Authorization |
| 有寫，環境變數不存在 | `no_api_key`，不打 HTTP |
| 環境變數存在但值為空字串 | 仍組 `Authorization: Bearer `，沒有把空值視為缺 key |
| module／worker 模式 | worker 繼承排程行程的環境；沒有從 agent 的請求 JSON 傳遞 API key |

來源：[headers](/home/guanyu/projs/aos/proto4-5/aos_llm.py:73)、[worker 啟動](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:209)。

**1.3 命令列**

| 命令 | 輸入／輸出 |
|---|---|
| `aos-llm call ENDPOINT REQ OUT [--timeout-ms N]` | 同步問一次，輸出完整 result |
| `ENDPOINT=endpoint.json` | 單一 endpoint 物件 |
| `ENDPOINT=endpoints.json#local` | 多 endpoint 文件內的具名項目 |
| `ENDPOINT=endpoints.json` | 多 endpoint 文件的 `default` |
| `REQ=-` | 從 stdin 讀整份 JSON |
| `OUT=-` | stdout 一行緊湊 JSON 加換行 |
| `OUT=檔案` | 寫 `<OUT>.tmp`、flush、fsync 檔案，再 `os.replace` |
| `--timeout-ms N` | 正整數；覆寫 request 的 `timeout_ms`，因此也蓋過 endpoint |
| `aos-llm models ENDPOINT` | GET `/models`，將取得的字串 id 一行一個印出 |

單一 endpoint 檔加 `#name` 會被拒絕。OUT 不會自動建立父目錄。第一層沒有 `--wait`、排隊、`--dry-run` 或重試旗標。[CLI 實作](/home/guanyu/projs/aos/proto4-5/aos_llm_cli.py:20)

**1.4 請求欄位與 HTTP body**

| REQ 欄位 | 驗證／用途 |
|---|---|
| `messages` | 必填非空陣列；沒有逐則驗 role/content |
| `model` | **只要出現就拒絕**；模型固定由 endpoint 決定 |
| `id` | 可省略；第一層不驗型別，原值放進 result，省略為 null |
| `priority` | 可省略；有寫須整數且不能 bool；不參與第一層執行順序 |
| `timeout_ms` | 正整數且不能 bool；優先於 endpoint |
| `params` | 物件；內容併入 HTTP body |
| `tools` | 有写須陣列；內容不逐項驗證，原樣送 |
| `tool_choice` | 原樣送，沒有本地型別驗證 |
| `endpoint` | 第一層不用它選路；CLI 已先選好 endpoint |
| `_aos`／其他頂層欄位 | 不直接送進 HTTP body |

組 body 的**實際順序**：

| 順序 | 操作 |
|---|---|
| 1 | 建 `{"model": endpoint.model, "messages": req.messages, "stream": false}` |
| 2 | `body.update(req.params or {})` |
| 3 | request 頂層若有 `tools`／`tool_choice`，覆蓋 body 對應欄位 |
| 4 | 再把 `model`、`stream` 強制設回 endpoint model／false |

因此：

- `params.model`、`params.stream` 無法改掉固定值。
- **`params.messages` 可以覆蓋原本的 `req.messages`。**
- request 沒有頂層 `tools` 時，`params.tools` 可以留在 body。
- request 顯式給 `tools:[]` 時，會送出空陣列；第一層不把它省略。
- 請求中的 `id`、`priority`、`timeout_ms`、`endpoint` 不會因為是頂層欄位而送進 body。

來源：[請求驗證及 body 組裝](/home/guanyu/projs/aos/proto4-5/aos_llm.py:95)。`params.messages` 覆蓋行為另以純記憶體 `_open` 替身確認，未連網。

**1.5 HTTP 與 strict model**

| 階段 | 行為 |
|---|---|
| URL | `base_url.rstrip("/") + "/chat/completions"` |
| 方法／編碼 | POST；JSON UTF-8、`ensure_ascii=False` |
| Header | `Content-Type: application/json`；視 key 設定加 Bearer |
| 串流 | 固定 `stream:false`，讀完整 response |
| 預檢 | `strict_model:true` 時，先 GET 同一 base URL 的 `/models` |
| 預檢成功，找不到精確 model id | 回 `model_not_found`；不送 chat |
| 預檢失敗 | 不阻止 chat；在 `notes` 加 `model_preflight_skipped` 與預檢錯誤 |
| chat 回覆 | strict 模式要求回覆 `raw.model == endpoint.model`，否則 `model_mismatch` |
| `strict_model:false` | 預檢與回覆 model 比對都略過 |
| timeout | `/models` 與 chat 各自使用同一 timeout 值；不是兩次 HTTP 共用的一個總 deadline |

`models()` 要求回應物件含 `data` 陣列；只收其中為物件且 `id` 是字串的項目，其他項目略過。[預檢與 POST](/home/guanyu/projs/aos/proto4-5/aos_llm.py:125)、[models](/home/guanyu/projs/aos/proto4-5/aos_llm.py:204)

**1.6 回應完整結構**

第一層的正常成功 result 形狀如下：

```json
{
  "ok": true,
  "id": "r1",
  "endpoint": "local",
  "model": "actual-model-id",
  "model_requested": "configured-model-id",
  "text": "回答",
  "finish_reason": "stop",
  "usage": {
    "prompt": 11,
    "completion": 7,
    "total": 18,
    "cached": 3,
    "reasoning": 2
  },
  "ms": 123,
  "raw": {
    "model": "actual-model-id",
    "choices": [
      {
        "message": {
          "role": "assistant",
          "content": "回答"
        },
        "finish_reason": "stop"
      }
    ]
  },
  "notes": [],
  "error": null
}
```

| 欄位 | 實際來源／型別 |
|---|---|
| `ok` | bool |
| `id` | request 原值；沒寫為 null |
| `endpoint` | endpoint 的名稱 |
| `model` | 供應商回覆的 `model`；尚未拿到可用回覆時 null |
| `model_requested` | endpoint 設定的 model |
| `text` | `raw.choices[0].message.content`；**未限制一定是字串**，null 也能成功 |
| `finish_reason` | `choices[0].finish_reason`；沒寫 null |
| `usage.prompt` | `usage.prompt_tokens` |
| `usage.completion` | `usage.completion_tokens` |
| `usage.total` | `usage.total_tokens` |
| `usage.cached` | `usage.prompt_tokens_details.cached_tokens` |
| `usage.reasoning` | `usage.completion_tokens_details.reasoning_tokens` |
| usage 缺少值 | null；不自行加總、不補 0、不換算費用 |
| `ms` | 從 `call()` 開始的 monotonic 經過時間，毫秒四捨五入；含預檢 |
| `raw` | 完整解析後的供應商 JSON；某些錯誤為 null |
| `notes` | 陣列，正常空陣列；預檢失敗時放說明 |
| `error` | 成功 null；失敗為下列物件 |

失敗 `error`：

```json
{
  "kind": "http",
  "msg": "供應商錯誤本文",
  "status": 500,
  "retryable": true
}
```

失敗 result 仍保留上述 envelope；`text`、`finish_reason` 為 null。`model_not_found` 的 `raw` 特別使用 `{"preflight": <models 原始回覆>}`。

`tool_calls` **不提升到 result 頂層**，保留在 `raw.choices[0].message.tool_calls`。回覆有 `content:null` 與 tool calls 可以成功；若完全缺 `content`，第一層會回 `bad_response`。[usage／錯誤 envelope](/home/guanyu/projs/aos/proto4-5/aos_llm.py:11)、[成功回覆擷取](/home/guanyu/projs/aos/proto4-5/aos_llm.py:174)

**1.7 錯誤與退出碼**

| `error.kind` | 觸發 | `retryable` |
|---|---|---|
| `bad_request` | endpoint／request 驗證失敗，或 POST request 建構失敗 | false |
| `no_api_key` | 指定的環境變數不存在 | false |
| `model_not_found` | `/models` 成功但沒有設定 id | false |
| `model_mismatch` | strict 模式回覆 model 不同或缺少 | false |
| `http` | HTTPError；`status` 記 HTTP code，`msg` 優先使用 response body | 429、500–599 為 true |
| `timeout` | TimeoutError／socket timeout／URLError 內含 timeout | true |
| `connect` | 其他 URLError，或 chat 呼叫中的 OSError | true |
| `bad_json` | response 無法解析 JSON，或 JSON 頂層不是物件 | false |
| `bad_response` | 缺 `choices[0].message.content` 等已捕捉的形狀錯誤 | false |

| CLI 結果 | 退出碼 | OUT |
|---|---:|---|
| `call` 得到 `ok:true` | 0 | 寫 result |
| `call` 得到 `ok:false` | 1 | **仍寫 result**；stderr 印 `aos-llm: kind: msg` |
| REQ 無法讀取／JSON 語法錯 | 2 | 不產生正常 result |
| ENDPOINT 檔解不開／選不到唯一 endpoint | 2 | 同上 |
| 用法／timeout 旗標錯 | 2 | 同上 |
| OUT 寫入失敗 | 2 | 呼叫可能已經完成，但結果沒有正常交付 |
| `models` 成功 | 0 | stdout 每行一個 id |
| `models` 設定／HTTP／回覆錯誤 | 1 | stderr 印錯誤 |
| `models` ENDPOINT 檔解不開 | 2 | stderr 印錯誤 |

第一層不因 `retryable:true` 自動重試。另外，函式不是對任意畸形回覆都保證回 result：例如非空非物件的 `prompt_tokens_details` 會讓 `_usage()` 拋 `AttributeError`；直接 CLI 沒有總括捕捉，第二層 worker 才會把這類例外包成 `internal`。此例外路徑已用純記憶體替身確認。[CLI 邊界](/home/guanyu/projs/aos/proto4-5/aos_llm_cli.py:93)、[worker 例外封裝](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:37)

---

**2．proto4-5 第二層：llm-cpu**

**2.1 程式分工**

| 檔案 | 職責 |
|---|---|
| [llm_cpu.py](/home/guanyu/projs/aos/proto4-5/llm_cpu.py:11) | `init`／`tick`／`submit`／`ls`／內部 `worker` CLI |
| [llm_cpu_home.py](/home/guanyu/projs/aos/proto4-5/llm_cpu_home.py:43) | 建家、原子 JSON、submit、endpoint 文件、獨立模式 ls |
| [llm_cpu_request.py](/home/guanyu/projs/aos/proto4-5/llm_cpu_request.py:15) | ID 驗證、請求指紋、查同名單所在位置 |
| [llm_cpu_tick.py](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:231) | 收尾、驗件、排序、容量、派工、snapshot／log |
| [llm_cpu_worker.py](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:37) | 在背景同步問模型、寫結果與 usage |
| [llm_cpu_module.py](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:13) | 接 kernel 的四個 hook；syscall、兩段等待、module 摘要 |
| [llm_cpu_manage.py](/home/guanyu/projs/aos/proto4-5/llm_cpu_manage.py:31) | `aos-kernel llm ls/rm`，直接查檔／殺 worker／刪單 |

**2.2 家目錄與讀寫責任**

以下以 `L` 表示 llm-cpu 的家；module 模式固定 `L=K/llm`。

```text
L/
  endpoints.json
  inst.json                  獨立模式才建立
  state.json
  usage.jsonl
  llm-cpu.log
  tick.err                   執行獨立模式 inst 時才會出現
  requests/
    <id>.json
    running/
      <id>.json
    done/
      <id>.json
  results/
    <id>.json
  log/
    <id>.log
```

| 路徑 | 內容／型別 | 誰寫 | 誰讀／消費 |
|---|---|---|---|
| `endpoints.json` | `{default:string,endpoints:array}` | init 建範例；後續由外部設定 | tick、worker、submit handler、ls/status |
| `inst.json` | `{argv:[絕對 llm-cpu,"tick","."],cwd:絕對 L,stderr:"tick.err"}` | 獨立模式 init | aos-exec／排程它的人 |
| `state.json` | `{ticks:int,running:int,endpoints:{name:int}}` | init；成功走完的 tick | 下一 tick 讀 ticks；module status |
| `requests/<id>.json` | 尚未派工的 request | submit、module handler；dispatch 補 metadata | tick |
| `requests/running/<id>.json` | request ＋ `_aos` 執行 metadata | tick 移入、補 PID | worker、後續 tick、ls/rm |
| `requests/done/<id>.json` | 原 request 的封存，不是 response | tick 收尾／退件移入 | ls、同名檢查、rm |
| `results/<id>.json` | 第一層 result ＋ `request_sha256`，或 scheduler 自產錯誤 result | worker 或 tick | agent、CLI wait、ls；tick 查存在 |
| `log/<id>.log` | worker stderr，append 模式 | tick 開檔，worker 寫 | 人讀；rm 不清此檔 |
| `usage.jsonl` | 每行一筆 usage 摘要 | init 建空檔；worker append | 沒有內建計費／彙總讀取器 |
| `llm-cpu.log` | tick 摘要或 tick error 文字 | init 建空檔；tick append | 人讀 |
| `tick.err` | 獨立 inst 的 stderr | aos-exec 執行 inst 時建立／重寫 | 人讀 |
| `*.tmp` | 寫檔中間檔 | 各寫入者 | 正常 scanner 只收 `.json`，不收 `.json.tmp` |

`state.json` 初值：

```json
{"ticks":0,"running":0,"endpoints":{}}
```

其中 `endpoints` 的 value 是**各 endpoint 正在 running 的件數**，不是 endpoint 設定物件。真正佇列／執行狀態由各資料夾中的檔案決定。[建家](/home/guanyu/projs/aos/proto4-5/llm_cpu_home.py:43)、[snapshot](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:242)

init 只產生一個 local endpoint：`http://localhost:1234/v1`、model=`loaded-model-id`、容量 1、timeout 300000。DIR 已存在就退 1，不覆寫，也不修補缺少的子目錄。

**2.3 請求檔完整格式**

使用者可提交的欄位集合：

```json
{
  "id": "optional-body-id",
  "endpoint": "local",
  "messages": [
    {"role": "user", "content": "問題"}
  ],
  "priority": 0,
  "timeout_ms": 300000,
  "params": {
    "temperature": 0.2
  },
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "echo",
        "parameters": {
          "type": "object",
          "properties": {}
        }
      }
    }
  ],
  "tool_choice": "auto"
}
```

| 欄位 | 第二層規則 |
|---|---|
| `messages` | 必填非空陣列，內容不逐則驗 |
| `endpoint` | 可省略，使用 default；有寫須字串且名稱存在 |
| `priority` | 省略 0；整數、排除 bool；越大越先 |
| `timeout_ms` | 可省略；有寫為正整數、排除 bool |
| `params` | 可省略；有寫為物件 |
| `model` | 禁止出現 |
| `tools` | tick 的 request validator **沒有驗**；worker 呼叫第一層時才驗必須是陣列 |
| `tool_choice` | 第一層原樣轉送 |
| `id` | body 內的值不是排程 ID；worker 會以檔名 ID 覆寫它 |
| `_aos` | scheduler metadata；物件以外的值在 dispatch 時被替換 |
| 其他欄位 | 沒有拒絕未知 key；仍可能影響 request hash |

排程 ID 來自 `--name`／module ticket 的 `id`／未指定時的 `time.time_ns()`。限制是 `[A-Za-z0-9._-]+`，但額外禁止 `"."`、`".."`、以及以 `.tmp` 結尾。[ID 驗證](/home/guanyu/projs/aos/proto4-5/llm_cpu_request.py:7)、[request 驗證](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:110)

進入 running 後，request 多出：

```json
{
  "_aos": {
    "request_sha256": "SHA-256 十六進位字串",
    "submitted": "2026-09-22T01:00:00.000+00:00",
    "endpoint": "local",
    "pid": 12345,
    "started": 1790038800.25
  }
}
```

| `_aos` 欄位 | 型別 | 寫入時點 |
|---|---|---|
| `request_sha256` | string | `submit_object()` 投遞時寫；獨立 `submit` 不自動寫這格 |
| `submitted` | UTC ISO 字串，毫秒精度 | `submit_object()` 投遞時寫 |
| `endpoint` | string | dispatch 選定路由後寫 |
| `pid` | 起初 null，spawn 後改為 int | dispatch |
| `started` | float，epoch 秒 | dispatch，啟動 worker 前 |
| 其他 `_aos` key | 未統一定義 | 若原來是物件，dispatch 保留其餘 key |

獨立模式 CLI `submit` 是**複製原始 bytes**，此時不解析、不驗 JSON，因此可以成功投入壞 JSON；下一 tick 才退件。module 使用 `submit_object()`，先驗 request，才序列化投遞。[兩種 submit](/home/guanyu/projs/aos/proto4-5/llm_cpu_home.py:74)

**2.4 回應檔格式與 usage**

worker 正常寫出的 `results/<id>.json`＝第一層完整 result，另加：

```json
{
  "request_sha256": "SHA-256 十六進位字串"
}
```

| 與第一層的差別 | 實際行為 |
|---|---|
| `id` | 一律為排程檔名 ID |
| `request_sha256` | 使用保存的 fingerprint，沒有時由 request 計算；內部早期失敗可能 null |
| worker 非預期例外 | 包成 `error.kind="internal"` 的第一層 error envelope |
| scheduler 自己退件／判 worker 死亡／逾時 | 由 `_error_result()` 組 result；`ms=0`、`raw=null`、usage 五格 null |
| scheduler 自產 result 的 `notes` | **沒有這個欄位**，與第一層 envelope 不完全一致 |
| scheduler 自產錯誤的 retryable | 現有呼叫都使用預設 false；包含 watchdog 的 timeout |

來源：[worker 寫結果](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:37)、[scheduler 錯誤 result](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:15)。

`usage.jsonl` 每行：

```json
{
  "at": "2026-09-22T01:00:00.000+00:00",
  "id": "r1",
  "endpoint": "local",
  "model": "actual-model-id",
  "prompt": 11,
  "completion": 7,
  "total": 18,
  "cached": 3,
  "reasoning": 2,
  "ms": 123,
  "ok": true
}
```

`at` 是寫 usage 時的 UTC 時間。以 `O_APPEND` 開檔，序列化後一次 `os.write()`；若序列化長度達 4096 bytes，將 model 改 null 後重組。沒有記 API key、prompt、response 本文。

不是每個終局都會有 usage：**只有 worker 的 `_write_usage()` 會寫**；tick 自行退件、`worker_died`、spawn 失敗或 watchdog timeout 不會補 usage。[usage 實作](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:16)

**2.5 一格 tick 的固定順序**

| 順序 | 操作 | 細節 |
|---:|---|---|
| 1 | 讀 endpoints | 整份設定載入失敗：記 emergency log，直接返回 |
| 2 | 收尾 running | 先看結果檔，再看 running metadata、PID、hard timeout |
| 3 | 驗 queued requests | 壞請求寫 `bad_request` result，移入 done |
| 4 | 排序 | `(-priority, st_mtime_ns, filename)` |
| 5 | 按容量派工 | endpoint 額滿就跳過這張，繼續看其他 endpoint |
| 6 | 寫 snapshot | ticks 加一，寫 running 總數及各 endpoint 件數 |
| 7 | append log | timestamp、tick、queued、running、事件；沒事件記 idle |

來源：[tick 主流程](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:231)。

| 排隊／容量性質 | 事實 |
|---|---|
| queue 上限 | 沒有件數／bytes 上限 |
| queue 逾時 | 沒有；排隊時間不算 HTTP timeout |
| 優先序 | 大 priority 優先；同 priority 比檔案 mtime，再比檔名 |
| 公平性 | 沒有 aging、使用者配額或公平分數 |
| 容量 | 每個 endpoint name 各有 `max_concurrent` |
| 相同 URL 的不同名稱 | 分別計數，沒有依 URL 合併容量 |
| 全域 worker 上限 | 沒有另外一個總上限 |
| 跨 endpoint 阻塞 | 一個 endpoint 額滿不擋其他 endpoint |
| running 計數 | 讀 `requests/running/*.json` 的 `_aos.endpoint` |
| 設定快照 | 沒有把 endpoint 設定固定在 request 中；tick 和 worker 各自重新讀設定 |

**2.6 派工與 worker**

| 步驟 | 實作 |
|---:|---|
| 1 | request 補 `_aos.endpoint`、`pid:null`、`started=time.time()` |
| 2 | 原子重寫 queued request |
| 3 | rename 到 `requests/running/<id>.json` |
| 4 | 開 `log/<id>.log`，append |
| 5 | `Popen([sys.executable, llm_cpu.py, "worker", L, id])` |
| 6 | `start_new_session=True`；stdin/stdout 都 `/dev/null`；stderr 指向上述 log |
| 7 | 把實際 PID 原子寫回 running request |
| 8 | worker 讀 running request、重新讀 endpoints、用 filename id 覆寫 request id |
| 9 | worker 同步呼叫 `aos_llm.call()` |
| 10 | 原子寫 results，append usage，退出 |
| 11 | 之後的 tick 才把 running request 移入 done |

spawn 失敗會立即寫 `spawn` 錯誤 result、將 request 移入 done。worker 不負責把 request 移入 done。[dispatch](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:192)、[worker](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:37)

**2.7 收尾、逾時、重試與撤單**

| 機制 | 判定／動作 | 所在檔 |
|---|---|---|
| 已有 result | 只判 `result_path.exists()`，不解析 result；request 移 done | [tick:72](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:72) |
| running metadata 壞 | 寫 `worker_died`，移 done | 同上 |
| PID 不存在／無有效 PID | `os.kill(pid,0)` 判存活；沒有結果則 `worker_died`，移 done | [tick:51](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:51) |
| HTTP timeout | 第一層 urllib timeout；worker 寫 timeout result | [aos_llm:154](/home/guanyu/projs/aos/proto4-5/aos_llm.py:154) |
| scheduler hard timeout | `time.time()-started > timeout_ms+5000ms`；SIGTERM **單一 PID**，寫 timeout，移 done | [tick:98](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:98) |
| hard timeout 的等待／升級 | 不等待退出，不升 SIGKILL | 同上 |
| 自動重試 | 第一層、worker、scheduler 都沒有；不消費 `retryable` 來重送 | 上述呼叫鏈 |
| `llm rm` 刪 queued | 直接刪 request/result 等同名檔 | [manage:107](/home/guanyu/projs/aos/proto4-5/llm_cpu_manage.py:107) |
| `llm rm` 刪 running | 先讀 PID；對 process group SIGTERM 等 1 秒，再 SIGKILL 等 1 秒 | [manage:85](/home/guanyu/projs/aos/proto4-5/llm_cpu_manage.py:85) |
| `llm rm` 清除範圍 | queued、running、done request、result 四处 | [manage:112](/home/guanyu/projs/aos/proto4-5/llm_cpu_manage.py:112) |
| `llm rm` 保留項目 | worker log、usage、tick log、state snapshot 不同步清除 |
| 遠端取消 | 沒有呼叫供應商 cancellation API；本地殺 worker 不等於撤回已抵達供應商的請求 |

其他明確邊界：

- hard timeout 要等下一次 tick 才檢查；tick 停止時不會自行執行。
- HTTP 預檢和 chat 可以各耗一個 timeout，但 scheduler 的 hard timeout 從 worker 派工起算，只給一個 timeout 加 5 秒。
- tick 判活只用 `kill(pid,0)`；管理指令的 `_alive()` 另讀 `/proc/<pid>/stat` 排除 zombie，兩處不相同。
- 已有結果檔優先於 PID／timeout 檢查。
- `llm rm` 遇到 running 記錄沒有可殺 PID 時退 1，保留檔案；既有測試有覆蓋。[管理測試](/home/guanyu/projs/aos/proto4-5/test/test_module_manage.py:115)

**2.8 同名／同內容的冪等範圍**

| 入口 | 同名時 |
|---|---|
| `llm-cpu submit` | 只要 queued／running／done／results 任一存在，退 1；**不比較內容** |
| `submit_object()` | 本身也拒絕既有 ID |
| `aos-kernel llm` CLI | 比較 fingerprint；相同視為既有同一張，不重送 |
| module `handle()` | 同樣比較 fingerprint，再決定呼叫 `submit_object()` |
| 相同 ID、不同內容 | 退錯，說明撞在 requests／running／results |
| 相同 ID、已完成失敗結果 | 不重試；`--wait` 讀舊失敗 result 後退 1 |
| 相同 ID、不帶 `--wait` | 同內容既有單直接退 0；不代表模型成功 |

fingerprint 是：

1. 複製 request。
2. 排除 `_aos` 中的 `request_sha256`、`endpoint`、`pid`、`started`、`submitted`。
3. `_aos` 剩空物件就移除這格。
4. JSON 使用 `sort_keys=True`、UTF-8、緊湊 separators。
5. 算 SHA-256。

它會忽略物件 key 順序與序列化空白，**沒有補入 default endpoint、priority 等預設值做語意正規化**；也不把 endpoint 設定內容納入 fingerprint。[fingerprint 與搜尋次序](/home/guanyu/projs/aos/proto4-5/llm_cpu_request.py:21)

**2.9 獨立行程模式與 kernel module 模式**

| 項目 | 獨立模式 | kernel module 模式 |
|---|---|---|
| 建家 | `llm-cpu init L` | kernel 首次執行 module tick 時 `_ensure_home()` |
| 家 | 任意 L | 固定 `K/llm/` |
| inst | 建 `L/inst.json` | 不建 |
| 推進排程 | 外部反覆叫 `llm-cpu tick [L]`／執行 inst | 每次 kernel tick import 後呼叫 module.tick |
| 投遞 | `llm-cpu submit [L] REQ --name ID` | `aos-kernel llm [K] REQ --name ID`，經 syscall |
| 等模型 | 獨立 CLI 沒有 wait 子命令 | `--wait SECS` 輪詢 result |
| 查詢 | `llm-cpu ls [L]` | `aos-kernel llm ls K` 或 kernel ls 的 module 摘要 |
| 刪單 | 獨立 CLI 沒有 rm | `aos-kernel llm rm K ID` |
| HTTP 執行者 | 背景 worker | 同一套背景 worker |
| 是否常駐服務 loop | `llm-cpu` 自己沒有常駐 loop；tick 一格就退 | 排程 hook 一格就返回 kernel |

| 命令／函式 | 退出／回傳 |
|---|---|
| `llm-cpu init` | 成功 0；已存在／建家失敗 1 |
| `llm-cpu submit` | 投遞成功 0；家、名稱、讀寫、撞名失敗 1 |
| `llm-cpu ls` | 成功 0；設定讀失敗 1 |
| `llm-cpu tick` | 捕捉 `BaseException`、嘗試記 log，**仍退 0** |
| `llm-cpu worker` | 結果及 usage 寫入成功退 0，**即使 result.ok=false**；寫入階段失敗退 1 |
| argparse 用法錯 | 2 |
| module `tick()` | 回 notes 陣列，不是子行程退出碼；例外交 kernel 記 note |
| module `handle()` | `(ok,msg)`，是收單結果，不是 LLM 結果 |
| module CLI | 接單／成功結果 0；失敗／逾時 1；解析用法錯 2 |

來源：[CLI](/home/guanyu/projs/aos/proto4-5/llm_cpu.py:35)、[module hooks](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:37)。

**2.10 `aos-kernel llm K req --wait` 的完整路徑**

| 順序 | 執行者 | 檔案／操作 |
|---:|---|---|
| 1 | kernel CLI | 找 K、載 config、載入名為 llm 的 module，交 `cli()` |
| 2 | llm CLI | 解析 REQ；指定或產生 ID；算 `K/llm/results/<id>.json` |
| 3 | llm CLI | 先檢查同名同內容；相同則直接查既有結果或回路徑 |
| 4 | llm CLI | 寫 `K/syscalls/<time_ns>-llm.json` |
| 5 | llm CLI | 等同名 `K/syscalls/done/...` 收件回音 |
| 6 | kernel tick | 呼叫 module.handle，驗 request、排入 `K/llm/requests/<id>.json` |
| 7 | kernel tick | 寫 `{ok,msg}` 回音，刪 syscall 原單 |
| 8 | llm CLI | 讀回音後刪回音檔；失敗退 1 |
| 9 | kernel tick | 同一 tick 接著跑 module.tick，有容量就可以立即派工 |
| 10 | llm CLI | 有 `--wait` 才開始第二段 result 等待；沒有就印路徑退 0 |
| 11 | worker | 做 HTTP、寫 `results/<id>.json` |
| 12 | llm CLI | 解析結果，印回答／錯誤／JSON與結果路徑，依 result.ok 退 0／1 |

syscall ticket：

```json
{
  "op": "llm",
  "id": "hello",
  "request": {
    "messages": [{"role": "user", "content": "hi"}]
  }
}
```

收件回音只有：

```json
{"ok":true,"msg":"排進去了：id=hello；結果會在 ..."}
```

不是模型 response。[module CLI](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:98)、[handle](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:37)

| 等待階段 | 時限 | 逾時後 |
|---|---|---|
| 等 kernel 收件回音 | `max(3秒, 3×config.interval_ms/1000)`，每 50ms 查一次 | 嘗試刪尚存的 syscall 原檔；退 1 |
| 等模型 result | **收件成功後**另外起算 `--wait SECS`，每 50ms 查一次 | 不刪 queued／running request，不殺 worker；印「已送出」，退 1 |
| `--wait 0` | 仍先讀一次 result | 有現成結果可成功；沒有則立即回逾時 |
| 不帶 `--wait` | 仍然等 kernel 收件回音 | 不是寫完 syscall 就立刻退出 |

`--wait` 不會幫 kernel 跑 tick。`--json` 輸出完整 result 後仍會另外印一行「結果檔：…」，所以 stdout **不是只有一個 JSON 文件**。預設只印 `result.text`；tool-call-only result 的 text=null 時會印空行。[等待實作](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:174)

兩個時序邊界，由程式順序推導、現有測試未覆蓋：

| 邊界 | 結果 |
|---|---|
| 第一個 kernel tick 之前投 LLM syscall | kernel 先 handle syscall、後跑 module.tick 建家；handle 讀不到 endpoints，先回失敗，同一 tick 稍後才建好 `K/llm` |
| 回音逾時撤單時，kernel 已讀入 ticket 但還沒刪原檔 | CLI 可能成功 unlink、印「沒送出去」；kernel 仍可用記憶體內的 ticket 完成排入 |

來源：[kernel 先 syscall 後 module tick](/home/guanyu/projs/aos/proto4-3/aos_kernel_tick.py:48)、[建家位置](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:21)、[撤單](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:154)、[syscall 未先 claim](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:86)。

**2.11 第二層的崩潰窗口**

| 中斷位置 | 重開後可見行為／限制 |
|---|---|
| result 已寫，running 尚未移 done | 下次 tick 看見 result 即移 done；此段可自然收尾 |
| result 已寫，usage 尚未 append | result 可讀；下次 tick 不補 usage |
| request 已移 running、worker 尚未開 | `pid:null`；下次 tick 判 `worker_died`，不重送 |
| worker 已開、PID 尚未寫回 | 下次 tick 可能把仍在跑的工作判為 `worker_died`；原 worker 仍可能寫結果 |
| hard timeout 發 SIGTERM 後 | scheduler 立即寫 timeout／移 done，沒有等待 worker 終止；若 worker 未終止，仍存在後續寫 result 的窗口 |
| 兩個 tick 同時跑 | 沒有鎖，會競爭相同 request／temp／running 檔 |

以上是可由寫入順序直接辨識的窗口，不是本次故障注入測試的結果。[dispatch 與 PID 寫回](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:200)、[worker 寫入順序](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:54)

---

**3．proto4-7：`aos-agent` 如何交出問題再收回**

**3.1 入口與資料夾**

`aos-agent`、`aos-user` 都只有兩行 shell，分別 `exec python3` 到 `aos_agent_cli.py`、`aos_user_cli.py`。agent CLI 引入 `proto4-6/aos_py.py`，作為呼叫 aos-exec／kernel 的 helper。[agent 入口](/home/guanyu/projs/aos/proto4-7/aos-agent:1)、[CLI import](/home/guanyu/projs/aos/proto4-7/aos_agent_cli.py:9)

| 路徑 | 內容 | 主要讀寫者 |
|---|---|---|
| `agent.json` | 名稱、system、K、限制、可選 stop | aos-user new 建；agent 讀 |
| `messages.json` | OpenAI messages 陣列，整份讀寫 | agent |
| `state.json` | 四格狀態與計數 | agent／reset；status 讀 |
| `req.json` | 最近一次 ask 組出的 request | ask 寫；不是排程器直接消費的信箱 |
| `<name>-eE-qQ-sS.req.json` | helper 臨時請求檔 | `aos_py.llm_submit` 寫，kernel CLI 讀；agent finally 刪 |
| `tools/<名>/tool.json` | description、parameters | new／外部建；ask/act 讀 |
| `tools/<名>/run` | 可執行工具 | act 經 aos-exec 跑 |
| `inbox/user/*.json` | 使用者信件 | aos-user 寫；idle 讀 |
| `inbox/user/read/` | 已讀信件 | idle rename 入內 |
| `outbox/<遞增編號>.json` | `{time,content}` | agent 寫；aos-user listen 讀 |
| `.listen-seen` | 已看 outbox 最大數字編號 | aos-user listen |
| `inst.json` | 絕對 aos-agent 路徑、cwd=A、stderr=`err.txt` | new 建；kernel 執行 |
| `err.txt` | agent stderr | 經 inst 執行時由 aos-exec 處理 |

`new` 建 agent.json、空 messages、信箱、outbox、echo/sh 工具與 inst；**不預先建立 state.json**。state 不存在時由 agent 使用預設值。[建立 agent](/home/guanyu/projs/aos/proto4-7/aos_user_cli.py:52)

**3.2 `agent.json`**

| 欄位 | 型別／預設 | 實際用途 |
|---|---|---|
| `name` | 必填非空字串 | 組 request ID；本層沒有進一步驗證是否符合 llm ID 字元限制 |
| `system` | 必填非空字串 | 每次 ask 都前置一則 system message |
| `K` | 必填非空字串 | kernel 家；正常 step 要求其為存在的目錄 |
| `max_steps_per_question` | 正整數，排除 bool；預設 60 | 限制 ask 次數，並非所有四格執行次數 |
| `tool_output_limit` | 正整數，排除 bool；預設 8000 | 工具結果字串截斷上限 |
| `stop` | 僅 `is True` 觸發 | 直接退 100；此時略過 K 存在檢查及 state/messages 載入 |

agent 只檢查 K 是目錄，不在這裡驗證 `config.json` 或 llm module 是否存在；更深的問題在 submit 時才顯現。[設定驗證](/home/guanyu/projs/aos/proto4-7/state_machine.py:25)

**3.3 `state.json` 全欄位**

預設：

```json
{
  "state": "idle",
  "epoch": 0,
  "question": 0,
  "step": 0,
  "request": null,
  "checks": 0,
  "errors": 0,
  "idle_since_error": 0,
  "stuck": false,
  "last_error": null,
  "outbox_n": 0
}
```

| 欄位 | 正常型別 | 意義／更新 |
|---|---|---|
| `state` | string | `idle`／`ask`／`wait`／`act` |
| `epoch` | 非負 int | reset 加一，用於 request ID |
| `question` | int | 每收到一個有效信件檔加一；檔內陣列仍算一題 |
| `step` | int | 每次進 ask 先加一；新題歸 0 |
| `request` | 絕對路徑字串或 null | **結果檔路徑**，不是請求物件或 syscall ID |
| `checks` | int | wait 看不到結果時加一；達 600 記錯 |
| `errors` | int | 模型／submit／文字工具修復錯誤累計；新題／reset 歸 0 |
| `idle_since_error` | int | idle 尾訊息是 user/tool 且未 stuck 時的重試等待計數 |
| `stuck` | bool | 阻止 idle 安全網再重問 |
| `last_error` | string 或 null | 最近錯誤；wait 驗收成功時清 null |
| `outbox_n` | int | 回話编号；寫信時另掃 outbox 最大编号，避免 reset 後覆蓋 |

載入時是「預設 dict 加上檔案內容」。明確驗證只有 `state` 合法、`epoch` 是非負整數且不是 bool；其餘欄位沒有逐一嚴格驗型，未知 key 也會保留。[defaults／load_state](/home/guanyu/projs/aos/proto4-7/state_machine.py:14)、[outbox 编號](/home/guanyu/projs/aos/proto4-7/mailbox.py:11)

`--reset`：讀舊 state，寫全新 defaults，只有 epoch=舊值+1；不刪 messages、outbox、舊 LLM 請求或結果。舊 state 讀壞時 reset 也會失敗。[reset](/home/guanyu/projs/aos/proto4-7/aos_agent_cli.py:26)

**3.4 四格的实际狀態轉移**

| 現在格子 | 本次做什麼 | 下一狀態／退出 |
|---|---|---|
| idle，有有效信 | 一次收一個檔、接 user messages、清新題計數 | ask，0 |
| idle，只有壞信 | 回「有一封信讀不懂」、搬 read | idle，0 |
| idle，沒信、沒待答尾訊息 | 保存 state | idle，101 |
| idle，尾訊息是 user/tool 且未 stuck | `idle_since_error++`；未滿 20 繼續等 | idle，101 |
| 同上，第 20 次 | 計數歸 0，準備重問 | ask，0 |
| ask，step 超過上限 | 寫 stuck outbox、清 request/checks | idle、stuck=true，0 |
| ask，提交成功 | 保存結果路徑、checks=0 | wait，0 |
| ask，提交失敗 | `_record_error()` | idle，0 |
| wait，結果未到，checks<600 | 保存檢查次數 | wait，101 |
| wait，第 600 次未到 | `_record_error("timeout...")` | idle，0 |
| wait，結果失敗／格式內容不合 | 記模型錯誤 | idle，0 |
| wait，結果驗收成功 | checks=0、last_error=null | act，0 |
| act，有 tool calls | 接 assistant；同步跑完全部工具，接 tool messages | ask，0 |
| act，純文字 | 接 assistant、寫 outbox | idle，0 |
| act，疑似文字 tool call 救不回 | 記模型錯誤，不把該 assistant 接入 messages | idle，0 |

來源：[idle](/home/guanyu/projs/aos/proto4-7/state_machine.py:94)、[ask](/home/guanyu/projs/aos/proto4-7/state_machine.py:119)、[wait](/home/guanyu/projs/aos/proto4-7/state_machine.py:172)、[act](/home/guanyu/projs/aos/proto4-7/state_machine.py:200)。

**3.5 `ask` 到底怎麼送出去**

| 順序 | 實際操作 |
|---:|---|
| 1 | `step += 1`，先檢查題目上限 |
| 2 | 重新讀工具表 |
| 3 | 組 `messages=[system,*messages.json]` |
| 4 | 工具表非空才加 `tools` 欄位 |
| 5 | 原子寫 `A/req.json` |
| 6 | 組 ID：`<name>-e<epoch>-q<question>-s<step>` |
| 7 | 暫時 `chdir(A)`，呼叫 `aos_py.llm_submit(K, request, name)` |
| 8 | helper 直接 `write_text()` 到 `A/<name>.req.json` |
| 9 | helper 經 `aos_py.call()` 啟動 aos-exec，再啟動 `aos-kernel llm K <reqfile> --name <name>` |
| 10 | **沒有帶 `--wait`**；但 kernel CLI 本身仍同步等收件回音 |
| 11 | helper 確認子命令 `kind=child` 且 code=0 |
| 12 | helper 不解析 stdout 路徑，直接計算並回傳 `K/llm/results/<name>.json` |
| 13 | agent finally 恢復 cwd，刪除 helper request 檔 |
| 14 | 將回傳路徑存入 `state.request`，state 改 wait，保存 |

來源：[ask](/home/guanyu/projs/aos/proto4-7/state_machine.py:119)、[llm_submit](/home/guanyu/projs/aos/proto4-6/aos_py.py:150)、[aos_py.call](/home/guanyu/projs/aos/proto4-6/aos_py.py:56)。

此 request **沒有** agent 自填的 endpoint、priority、timeout、params、model、tool_choice；使用 llm-cpu default endpoint 與其 timeout。

agent 不直接寫 `K/llm/requests/`。它寫本地 helper 檔，呼叫 kernel CLI，由 kernel syscall handler 真正投遞。

**3.6 `wait` 等什麼、怎麼判、何時退 101**

| 判定 | 行為 |
|---|---|
| `state.request` 空 | `AgentError("wait 沒有 request")`，CLI 退 1 |
| `Path(request).exists()` 為 false | checks 加一；1–599 次保存 state 後退 101 |
| 第 600 次仍無檔 | 記 timeout，checks 重設 0，轉 idle，退 0 |
| 檔存在，但讀不到／JSON 壞／頂層非物件 | AgentError，退 1；不算模型 errors |
| `result.ok is not True` | 取 error.kind/msg 記模型錯誤 |
| raw 沒有可用 `choices[0].message` 物件 | `bad_response: 沒有 choices` |
| assistant 沒有 truthy tool_calls，且 `str(result.text or "").strip()` 為空 | `empty_reply` |
| 其餘 | 轉 act；此格**不寫 messages** |

它只看結果檔，不讀 syscall 回單、不查 worker PID、不查 queued/running 狀態、不呼叫 `aos_py.wait_for()`，也不 sleep 等結果。[wait 原碼](/home/guanyu/projs/aos/proto4-7/state_machine.py:153)

600 是 **agent 實際被叫到 wait 且查不到檔的次數**，不是 600 秒，也不是 kernel tick 數。

**3.7 收回時怎麼接 messages**

| 情況 | `act` 寫入 messages 的內容 |
|---|---|
| 正式 tool_calls | 原始 `raw.choices[0].message` 原樣 append；接著每個 call 一則 `{"role":"tool","tool_call_id":...,"content":...}` |
| 文字格式 tool call 被救回 | 建 `{"role":"assistant","content":text,"tool_calls":救回的calls}`，再接 tool messages |
| 純文字回覆 | 建新的 `{"role":"assistant","content":str(result.text or "")}`；不是保留整個 raw message |
| 工具失敗／不存在／參數壞 | 仍是 tool message 的 content，下一輪交模型看 |
| 正常回答 | 同時寫一封 outbox；清 request/checks，回 idle |

有 calls 時，一格內按順序同步跑完所有 calls。最後 `_save()` **先重寫 messages，再重寫 state**。result 留在 K，不消費、不改名、不刪。[act／save](/home/guanyu/projs/aos/proto4-7/state_machine.py:200)

**3.8 錯誤、重試、逾時**

| 情況 | 處理 |
|---|---|
| submit helper 例外 | errors+1、last_error=`submit: ...`、回 idle，退 0 |
| result.ok=false | 記 errors；不看 `retryable` 是否 true |
| result 缺 choices／空白回答 | 記 errors |
| 文字工具呼叫救不回 | 記 errors |
| 正式工具不存在／非零退出／工具參數 JSON 壞 | 形成 tool result；**不增加 agent.errors** |
| `_record_error` 共同行為 | errors+1，idle_since_error=0、checks=0、state=idle |
| errors>=5 | stuck=true，寫「連錯 5 次…」outbox |
| 成功模型／工具輪 | **不把 errors 歸零** |
| 新有效信件 | 清 errors、stuck、last_error、step、request 等，question+1 |
| idle 自動重試 | 只有記憶尾巴為 user/tool、未 stuck，累計 20 次 idle 後轉 ask |
| 重試的 request ID | 下一個 ask 又 step+1，所以使用新 ID |
| agent 等結果超時 | 不撤銷原 request、不殺 worker |
| stop／reset | 不取消已送出的 LLM 工作 |
| wait／act 讀壞結果檔 | 退 1；沒有轉成可重試的模型 errors |

`_record_error()` 沒有清 `request`；錯誤後的 idle state 可能仍顯示上一個結果路徑。下一次成功 submit 才覆寫。[錯誤記錄](/home/guanyu/projs/aos/proto4-7/state_machine.py:78)、[idle 重試條件](/home/guanyu/projs/aos/proto4-7/state_machine.py:108)

**3.9 崩在中間的實際保障與缺口**

下列窗口由寫入順序推導；proto4-7 測試沒有故障注入驗證。

| 中斷點 | 留下的狀態／後果 |
|---|---|
| idle 已把信搬進 read，messages 尚未保存 | 信已不在未讀 inbox；沒有從 read 自動重播的機制 |
| idle 已寫 messages，尚未寫 state | state 仍 idle，messages 尾端是 user；無新信時可在 20 次 idle 後回 ask，但 question 等記帳沒有同步落下 |
| ask 已被 kernel 收下，尚未保存 wait state | 重開仍可能是舊 ask；step 重算出同 ID，同 request 可由 module 冪等接回 |
| 同上，但 system／messages／tools 已變 | 同 ID 不同 fingerprint，被拒；沒有保證所有 ask 重入都冪等 |
| wait 驗收後、state 尚未改 act | 下次再驗一次同 result；此時尚無 messages／工具副作用 |
| act 已執行部分工具，尚未保存 messages | 重開仍 act，會再跑工具；無逐工具完成紀錄 |
| act 已保存 messages，尚未保存 state | 重開仍 act，仍讀同 result，再 append assistant/tool、再跑工具；沒有用 messages 尾巴去重 |
| 純文字 act 已寫 outbox，尚未保存 state | 下次可能再寫一封；outbox 掃最大编号能避免覆蓋，但不避免重複回話 |
| helper 檔寫出後程序被硬殺 | finally 不一定執行，可能留下 `<name>.req.json` |
| 多份 agent 同時跑 | 沒有鎖；state、messages、outbox、temp 檔可競爭 |

proto4-7 的單檔 JSON 寫法是 `.tmp + os.replace`，沒有 fsync，也沒有跨檔 transaction。它與 proto5 文件中描述的 `think/act` 尾訊息自癒機制不能視為同一套保障。[原子寫 helper](/home/guanyu/projs/aos/proto4-7/common.py:15)、[收信先搬 read](/home/guanyu/projs/aos/proto4-7/mailbox.py:38)、[act 順序](/home/guanyu/projs/aos/proto4-7/state_machine.py:217)

**3.10 工具怎麼跑**

| 項目 | 實作 |
|---|---|
| 工具搜尋 | `tools/` 直屬子資料夾，按名稱排序；tools 不存在代表無工具 |
| 名稱 | 資料夾名，不從 tool.json 另取 name |
| tool.json | 要有 string description、object parameters |
| schema 補值 | 以 `{"type":"object", **parameters}` 合成，再 `setdefault("properties",{})` |
| 已有 type/properties | 原值保留，並非強制改成 object／dict |
| 送模型格式 | `{"type":"function","function":{"name", "description", "parameters"}}` |
| run 的存在／可執行性 | load_tools 不檢查；實際執行時才發現 |
| 正式 call 參數 | dict 先 dumps；其他值轉字串，再 json.loads／dumps 正規化 |
| schema 驗證 | 沒有按照 parameters schema 驗參數 |
| 呼叫 | `aos_py.call(run, stdin=args_text, capture=True, timeout_ms=60000)` |
| stdout | 整段收進記憶體，再做字數截斷 |
| 非零退出 | content=`[exit N] `＋stderr 前 500 字＋換行＋stdout |
| exception | content=`工具執行失敗：...` |
| 找不到 run | content=`沒有這個工具` |
| 截斷 | 前 `tool_output_limit` 個 Python 字元，加 `…（截斷）`；不是 bytes 上限 |
| timeout | 經 aos-exec 對子行程 group TERM，2 秒後必要時 KILL |

来源：[工具宣告與修復](/home/guanyu/projs/aos/proto4-7/agent_tools.py:14)、[run_tool](/home/guanyu/projs/aos/proto4-7/agent_tools.py:105)、[aos-exec timeout](/home/guanyu/projs/aos/proto4-3/aos_exec.py:32)。

**cwd 有一個重要細節**：通用工具是普通檔案目標，aos-exec 把 cwd 設為 run 所在的 `A/tools/<name>/`。內建 `sh/run` 自己算出 agent 根並 `cd`，所以它才是在 A 裡執行 shell。[普通檔案 cwd](/home/guanyu/projs/aos/proto4-3/aos_exec.py:88)、[內建 sh](/home/guanyu/projs/aos/proto4-7/aos_user_cli.py:35)

文字 tool call 修復：

| 輸入 | 修復方式 |
|---|---|
| 開頭 `<tool_call>`、`[TOOL_CALLS]`、`<function=` | 掃第一個括號平衡的 JSON object |
| 去空白後整段 `{...}` | 直接解析成 JSON object |
| candidate.name 不在已知工具 | 失敗，計一次模型錯誤 |
| 成功 | 只產生一個 call，ID=`call_<step>_1`；arguments 預設 `{}`，再 dumps |
| 一般文字包含 JSON 但不符合開頭形狀 | 不嘗試修復 |

它不是完整解析 XML／function 標籤，也不會從 `<function=foo>` 的標籤本身取工具名；仍要求 JSON object 裡有 `name`。[修復實作](/home/guanyu/projs/aos/proto4-7/agent_tools.py:43)

**3.11 aos-user、信件與退出碼**

| 功能 | 實際行為 |
|---|---|
| `new --name --system --K` | 只允許不存在或空資料夾；寫 K 絕對路徑；不自動 kernel add，只印下一步 |
| `say "文字"`／stdin | 寫 timestamp 微秒檔名，內容 `{from:"user",time,content}`；空內容拒絕 |
| idle 收信 | `sorted(inbox.glob("*.json"))[:1]`：按**檔名**取一個 |
| 信件內容 | 物件或非空物件陣列，每筆要有 content |
| 接進記憶 | `{"role":"user","content":"[user] "+內容}`；非字串 content 用 JSON 序列化 |
| from/time | 不保留在 messages；都轉成 user 訊息 |
| 已讀同名碰撞 | 在 read 目的檔名加 timestamp |
| outbox | `{time:UTC微秒字串,content:string}`，编号至少四位，不以四位為上限 |
| `listen --once` | 印大於 `.listen-seen` 的數字檔；沒有就明說後退出 |
| `listen --new --once` | 忽略啟動時已存在的檔，200ms 輪詢；有新批次就印出後退出 |
| `listen` | 先印現有 outbox，再追新檔；不是只印未看過的 |
| `talk` | 背景 thread listen --new；前景讀「你>」，送到 inbox |
| listen/talk | 都不推進 agent、不替 kernel tick |

來源：[mailbox](/home/guanyu/projs/aos/proto4-7/mailbox.py:38)、[listen](/home/guanyu/projs/aos/proto4-7/aos_user_cli.py:110)。

| agent 退出碼 | 意義 |
|---:|---|
| 0 | 有進展，或模型／submit 錯誤已記入 state |
| 101 | idle 等信／等待重試，或 wait 尚無 result |
| 100 | agent.json stop=true |
| 1 | 已捕捉的 AgentError、ToolConfigError、OSError |
| 2 | argparse 用法錯 |

aos-user：正常 0；已捕捉的 AgentError／OSError／ValueError 為 1；argparse 用法錯 2。[agent CLI](/home/guanyu/projs/aos/proto4-7/aos_agent_cli.py:18)、[user CLI](/home/guanyu/projs/aos/proto4-7/aos_user_cli.py:179)

---

**4．proto4-3 kernel：module／syscall／101**

**4.1 module 登記與介面**

| 項目 | 實作 |
|---|---|
| 登記位置 | `K/config.json` 的 `"modules":["/abs/module.py",...]` |
| init 旗標 | 可重複 `--module PATH`；存入時轉絕對路徑 |
| 既有家 | init 不覆寫；後加 module 需修改 config |
| 載入 | importlib 從檔案載入；名稱使用路徑 SHA-256 前 16 字元 |
| 相依 import | 載入期間暫把 module 所在目錄放 sys.path 前方 |
| `NAME` | 必須非空字串，作為 kernel 子命令名 |
| `OPS` | 必須 tuple，每項非空字串；空 tuple 可通過 |
| hooks | 可以缺；存在時必須 callable |
| 重複 NAME／OPS | 沒有拒絕重複登記；按配置順序選擇 |
| 載入／tick 例外 | 捕捉 BaseException，記 note；不因此停止其他 module |
| 執行位置 | hook 在 kernel／kernel CLI 行程內直接呼叫，不是獨立服務 |

來源：[init](/home/guanyu/projs/aos/proto4-3/aos_kernel_init.py:24)、[loader](/home/guanyu/projs/aos/proto4-3/aos_kernel_module.py:16)。

| hook | 回傳／用途 |
|---|---|
| `handle(h,cfg,st,ticket)` | syscall handler；解包成 `(ok,msg)`，再轉 bool／str |
| `tick(h,cfg,st)` | 每回合一次；回 list 才逐項加進 notes |
| `status(h,cfg)` | kernel ls 使用；不是 None 就印 |
| `cli(h,cfg,argv)` | kernel module 子命令；回退出碼 |

`h` 是 `KHome`，含 `.dir`、`.syscalls`、`.syscalls_done`、`.procs`、`.cpus` 等路徑；cfg 是讀出的設定；st 是當回合 kernel state。[KHome](/home/guanyu/projs/aos/proto4-3/aos_kernel.py:61)

CLI 的 K 判定實際掃 module argv 的**前兩個位置**，找「資料夾且含 config.json」的參數取出；所以可用：

```text
aos-kernel llm K req.json
aos-kernel llm ls K
aos-kernel llm rm K NAME
```

找不到則使用 cwd。[module CLI 分派](/home/guanyu/projs/aos/proto4-3/aos_kernel.py:171)

**4.2 kernel tick 與 module 的順序**

| 順序 | 操作 |
|---:|---|
| 1 | 讀 K/state，補 cpu state 格 |
| 2 | 讀 daemon state，檢查／補登記普通 cpu |
| 3 | 載入 modules，收載入 notes |
| 4 | 處理 syscalls |
| 5 | 跑各 module.tick |
| 6 | 驗普通 procs queue |
| 7 | 普通 cpu 排程 |
| 8 | 保存 state、append kernel.log，正常回 0 |

LLM request 可在第 4 步排入、第 5 步同回合派工。即使 daemon 上普通 cpu 尚未 ready，module hook 仍會被執行。[tick](/home/guanyu/projs/aos/proto4-3/aos_kernel_tick.py:41)

**4.3 syscall 請求／回音格式**

| 項目 | 實際格式／語意 |
|---|---|
| 投遞 | `K/syscalls/<自選名稱>.json` |
| 掃描 | 只收頂層 `.json` 普通檔，按檔名排序 |
| 請求頂層 | JSON object |
| 通用分派欄位 | `op` |
| 內建 rm | `{"op":"rm","pid":"行程名稱"}` |
| llm module | `{"op":"llm","id":"請求名稱","request":{...}}`；id 可 null，由 handler 產生 |
| 回音 | 同名 `K/syscalls/done/<名稱>.json` |
| 回音內容 | 固定 `{"ok":bool,"msg":string}` |
| 關聯方式 | 檔名相同；回音沒有另外帶 request／ticket ID 欄位 |
| 完成處理 | 先寫回音，再 unlink 原單 |
| 回音寫失敗 | 記 note；仍會嘗試刪原單，沒有 durable 重送回音機制 |
| 原單刪失敗 | 記 note；下一 tick 仍可能再讀同一張 |

分派規則：

1. `op=="rm"` 永遠走內建處理。
2. 其他 op 找第一個 `op in module.OPS` 的 module。
3. 找到且有 handle 才呼叫。
4. 第一個認領者若沒有 handle，**不繼續找後面的 module**，回不認得 op。
5. 無效 JSON／非物件／無 op／未知 op／handler 例外，都嘗試寫失敗回音。

來源：[handle_syscalls](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:72)、[回音／刪單](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:191)。

**4.4 一般 syscall 等待與 llm `--wait` 的關係**

| 路徑 | 等待行為 |
|---|---|
| `aos-kernel rm K NAME` | 寫 `<time_ns>-rm-<pid>.json`，每 50ms 等 done 回音 |
| rm 時限 | `max(3秒,3×interval)` |
| rm 收到回音 | 解析、刪回音、印 msg；ok 為真退 0，否則 1 |
| rm 逾時 | 退 1；**不撤掉原 syscall 單** |
| llm 收件階段 | 使用自己的 `_wait_reply()`，同一時限與輪詢頻率 |
| llm 收件逾時 | 另有刪原單的撤單分支 |
| llm `--wait` | 是 module 自己實作的第二段 result polling |
| kernel 通用介面 | 沒有一個通用 syscall `--wait result` 機制 |

來源：[rm CLI](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:18)、[llm 等回音](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:233)。

kernel 的普通 `rm` 與 `llm rm` 不同：

| 命令 | 動作 |
|---|---|
| `aos-kernel rm K agent` | 拿掉普通行程的下一次執行位置；cpu 上的 inst 換 idle；不殺正在執行的那一次 |
| `aos-kernel llm rm K request` | 直接查 LLM 家；running 時殺 worker process group，再刪單 |
| 拿掉 agent | 不會順帶取消它已送出的 LLM request |

**4.5 101 如何傳到 kernel**

| 階段 | 資料流 |
|---|---|
| agent | 無信／結果未到，退出 101 |
| aos-exec | 回 `(101,"child")` |
| aos-run | status-fd 發 `done #N exit=101 kind=child ...` |
| daemon | `Entry.feed()` 更新 runs、last_exit、last_kind；寫進 daemon state |
| kernel tick | 直接讀 daemon state，按 cpu inst 的 realpath 取得 entry |
| scheduler | 只有 `new_runs>0` 時觀察新的退出回報 |
| 判等待 | `last_kind=="child"` 且 `last_exit==cfg.wait_exit`；預設 wait_exit=101 |
| 記帳 | `waiting=true`，`wait_runs += new_runs` |
| 有人排隊 | 若目前行程至少跑過一次，立即換到隊尾，不必等滿 quantum |
| 沒人排隊 | 留在 cpu，aos-run 仍會繼續定期執行它 |
| 下一次非 wait 回報 | 清 waiting/wait_runs |
| bad streak | 101 不算一般非零錯誤，還會打斷 bad_runs 計數 |

來源：[aos-run 回報](/home/guanyu/projs/aos/proto4-3/aos_run.py:85)、[daemon 解析](/home/guanyu/projs/aos/proto4-3/aos_daemon_entry.py:94)、[kernel 讀狀態](/home/guanyu/projs/aos/proto4-3/aos_kernel_tick.py:62)、[scheduler](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:40)。

| 容易混淆的點 | 程式事實 |
|---|---|
| kernel 是否知道結果路徑 | 不知道；退出碼沒有附帶 path |
| 是否等待檔案事件喚醒 | 沒有；等待者仍在普通 FIFO／cpu 循環中重新執行 |
| waiting 是否表示 OS process 被 suspend | 不是；本次 agent 已退出 |
| `wait_runs` 是否等於 agent.checks | 不是；一個來自 daemon runs 差值，一個由 agent 每次查不到 result 自增 |
| kernel 是否看到每一次退出 | 不保證；它讀最新 snapshot，中間的退出碼可能看不到 |
| `new_runs>1` 時 | 以最新 last_exit 配合差值加計 wait_runs/bad_runs |
| 被換下時 | wait_runs 存到 kernel state 的 `waiting[pid]`；再次上 cpu 時還原 |

101 讓出的是**後續 cpu 執行機會**，不是將一個仍阻塞在模型呼叫中的 agent 行程移走。[換人／還原 waiting](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:94)

---

**5．文件與程式對不上的地方**

下表將明確落差與表述過度保證分開寫；時序推導不當作已跑過的故障測試。

| # | 文件／註解說法 | 程式事實 | 位置 |
|---:|---|---|---|
| 1 | proto5 aos-agent「程式還沒寫」 | 工作樹已有 lib/CLI；think 直接同步 call | [README:16](/home/guanyu/projs/aos/proto5/README.md:16)；[aos_agent:215](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:215) |
| 2 | proto5 lib 列「五支模組」，llm_ask 說 agent「之後」import | 已有第六支 aos_agent，且正在 import／使用 | [lib README:1](/home/guanyu/projs/aos/proto5/lib/README.md:1)、[244](/home/guanyu/projs/aos/proto5/lib/README.md:244)；[aos_agent:18](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:18) |
| 3 | proto4-5「沒有取消」 | 已有 `aos-kernel llm rm`，可殺 running worker 並刪單；另有收件逾時撤 syscall | [README:181](/home/guanyu/projs/aos/proto4-5/README.md:181)；[manage:85](/home/guanyu/projs/aos/proto4-5/llm_cpu_manage.py:85) |
| 4 | 「每一發另 append usage.jsonl」 | 只有 worker 寫 usage；scheduler 退件、spawn、worker_died、hard timeout 不寫 | [README:157](/home/guanyu/projs/aos/proto4-5/README.md:157)；[worker:55](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:55)、[tick:35](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:35) |
| 5 | result 說明把 notes 列為通用欄位 | scheduler 自產錯誤 result 沒有 notes | [README:66](/home/guanyu/projs/aos/proto4-5/README.md:66)；[tick:23](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:23) |
| 6 | 「連線及逾時會標 retryable:true」 | 第一層 HTTP timeout 是 true；scheduler hard timeout 使用預設 false | [README:177](/home/guanyu/projs/aos/proto4-5/README.md:177)；[tick:15](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:15)、[104](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:104) |
| 7 | syscall 還在就可說「沒送出去」 | 原單沒有先 rename claim；kernel 可能已讀入但未 unlink，CLI 刪單成功不能證明未送出 | [README:120](/home/guanyu/projs/aos/proto4-5/README.md:120)；[module:154](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:154)、[syscall:86](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:86) |
| 8 | kernel 沒活著就撤掉、不排隊 | CLI 沒有直接判 kernel 存活；它靠等回音逾時推斷。同名同內容分支甚至不投 syscall，也不撤已有單 | [README:118](/home/guanyu/projs/aos/proto4-5/README.md:118)；[module:137](/home/guanyu/projs/aos/protos4-5/llm_cpu_module.py:137) |
| 9 | `call()` docstring：「永遠以 v1 result 回報成敗」 | 畸形 usage detail 可拋 AttributeError；直接 CLI 未總括捕捉，worker 才包 internal | [aos_llm:89](/home/guanyu/projs/aos/proto4-5/aos_llm.py:89)、[11](/home/guanyu/projs/aos/proto4-5/aos_llm.py:11)；[worker:50](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:50) |
| 10 | 失敗 stderr「一行」 | msg 可直接包含 HTTP body 的換行，print 前沒有壓成單行 | [README:62](/home/guanyu/projs/aos/proto4-5/README.md:62)；[aos_llm:156](/home/guanyu/projs/aos/proto4-5/aos_llm.py:156)、[CLI:119](/home/guanyu/projs/aos/proto4-5/aos_llm_cli.py:119) |
| 11 | agent「連錯五次」stuck | errors 在成功模型／工具輪不清零；實際是同一題期間累計到 5，未要求連續失敗 | [README:27](/home/guanyu/projs/aos/proto4-7/README.md:27)；[state_machine:78](/home/guanyu/projs/aos/proto4-7/state_machine.py:78)、[195](/home/guanyu/projs/aos/proto4-7/state_machine.py:195) |
| 12 | 「每題格數」上限 | step 只在 ask 自增；idle/wait/act 不加，故是 ask 次數上限 | [README:8](/home/guanyu/projs/aos/proto4-7/README.md:8)、[26](/home/guanyu/projs/aos/proto4-7/README.md:26)；[state_machine:119](/home/guanyu/projs/aos/proto4-7/state_machine.py:119) |
| 13 | 收「最舊」的一封信 | 實際按檔名排序，不看 mtime／信件 time；aos-user 的 timestamp 檔名使一般情況看起來是時間序 | [README:25](/home/guanyu/projs/aos/proto4-7/README.md:25)；[mailbox:43](/home/guanyu/projs/aos/proto4-7/mailbox.py:43) |
| 14 | 工具名對不上就算模型錯誤 | 只適用文字修復；正式 tool_call 的未知工具變成 tool content「沒有這個工具」，不加 errors | [README:91](/home/guanyu/projs/aos/proto4-7/README.md:91)；[tools:86](/home/guanyu/projs/aos/proto4-7/agent_tools.py:86)、[110](/home/guanyu/projs/aos/proto4-7/agent_tools.py:110) |
| 15 | 所有改寫 JSON 都先 tmp/rename | agent 自己主要檔案如此；ask 呼叫的 helper `<name>.req.json` 是直接 write_text | [README:19](/home/guanyu/projs/aos/proto4-7/README.md:19)；[aos_py:155](/home/guanyu/projs/aos/proto4-6/aos_py.py:155) |
| 16 | 工具程式註解稱 parameters 一定 object、有 properties | 只補缺省；已有 `type:"array"` 或非 dict properties 不會被改掉 | [tools:29](/home/guanyu/projs/aos/proto4-7/agent_tools.py:29) |
| 17 | module CLI 第一個參數符合才當 K | 實作掃前兩個參數，支援 action 後接 K | [kernel 文件:84](/home/guanyu/projs/aos/proto4-3/docs/kernel.md:84)；[kernel:175](/home/guanyu/projs/aos/proto4-3/aos_kernel.py:175) |
| 18 | module 載入失敗會留 note | tick／ls 會處理 notes；module CLI 丟掉 loader.notes，可能只顯示「不認得子命令」 | [kernel 文件:65](/home/guanyu/projs/aos/proto4-3/docs/kernel.md:65)；[kernel:186](/home/guanyu/projs/aos/proto4-3/aos_kernel.py:186) |
| 19 | kernel tick 退出碼「一律 0；不是家=1」 | 帶參數明確退 2；主 tick 也沒有捕捉所有自身 I/O 例外的總括邊界 | [kernel 文件:57](/home/guanyu/projs/aos/proto4-3/docs/kernel.md:57)；[tick:140](/home/guanyu/projs/aos/proto4-3/aos_kernel_tick.py:140)、[41](/home/guanyu/projs/aos/proto4-3/aos_kernel_tick.py:41) |
| 20 | 排程段括號仍寫「v1 的行程不會自己結束」 | 已有 done_exit，預設 100，搬入 procs/done | [kernel 文件:127](/home/guanyu/projs/aos/proto4-3/docs/kernel.md:127)；[schedule:42](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:42) |

另有幾項屬於**文件未完整交代，而非直接相反**：

| 主題 | 程式中的補充事實 | 來源 |
|---|---|---|
| 第一／第二層 endpoint 不同要求 | 第一層可省 timeout/max_concurrent；第二層兩個都必填 | [第一層](/home/guanyu/projs/aos/proto4-5/aos_llm.py:58)、[第二層](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:135) |
| 第一層 params 的覆蓋能力 | 只強制保護 model/stream；messages 可被 params 覆蓋 | [body 組裝](/home/guanyu/projs/aos/proto4-5/aos_llm.py:140) |
| `--wait --json` stdout | 完整 JSON之外另有結果路徑文字行 | [wait_result](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:184) |
| module 衝突 | 不拒絕重名／重疊 OPS，分派取前者 | [CLI](/home/guanyu/projs/aos/proto4-3/aos_kernel.py:187)、[syscall](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:105) |
| syscall wire schema | 實作為同名檔案關聯、固定 `{ok,msg}`，不是包含完整結果的通用回覆 | [syscall](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:191) |
| agent 的 101 | kernel 不讀結果檔；只讓位、再輪到時重新跑 agent | [schedule](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:68) |

**6．測試證據與本次驗證範圍**

本次沒有執行會建立暫存家、啟動 server／worker、寫檔或殺行程的測試，也沒有跑 build/ctest。因此以下是**閱讀測試碼確認的涵蓋範圍**，不是本次宣告測試全綠。

| proto4-5 測試檔 | 方法數 | 涵蓋內容 |
|---|---:|---|
| [test_aos_llm.py](/home/guanyu/projs/aos/proto4-5/test/test_aos_llm.py:15) | 16 | endpoint 三種選法、result 全欄位、tools/tool_choice、HTTP500、禁止 model、stdin/stdout、missing key、timeout 覆寫、strict 預檢／fallback |
| [test_home.py](/home/guanyu/projs/aos/proto4-5/test/test_home.py:11) | 12 | 建家、submit、撞名、壞 request、process 拒絕、壞 endpoints tick 仍 0、ls、aos-exec 一次一 tick |
| [test_worker.py](/home/guanyu/projs/aos/proto4-5/test/test_worker.py:8) | 9 | success/usage、HTTP500、壞 JSON、model mismatch、alias、missing key、connection refused、固定 model |
| [test_schedule.py](/home/guanyu/projs/aos/proto4-5/test/test_schedule.py:10) | 7 | priority、mtime、容量、跨 endpoint、worker 死亡、HTTP timeout、hard timeout |
| [test_module.py](/home/guanyu/projs/aos/proto4-5/test/test_module.py:19) | 14 | 首 tick 建家、syscall 收件、wait/plain/json、两種收件逾時分支、結果逾時、同名同內容冪等／撞名 |
| [test_module_manage.py](/home/guanyu/projs/aos/proto4-5/test/test_module_manage.py:19) | 6 | init 提示、placeholder 警告、ls、rm、殺 running worker、無 PID 拒絕 |
| 合計 | **64** | 使用假 OpenAI server、CLI 與暫存家 |

`_fake_openai.py` 提供 `/models`、echo、延遲、500、壞 JSON、model mismatch 等情境；`_util.py` 管理 fake server、暫存家、CLI、結果輪詢與清理。[fake server](/home/guanyu/projs/aos/proto4-5/test/_fake_openai.py:9)、[共用 fixture](/home/guanyu/projs/aos/proto4-5/test/_util.py:19)

| proto4-7 測試檔 | 方法數 | 涵蓋內容 |
|---|---:|---|
| [test_agent.py](/home/guanyu/projs/aos/proto4-7/test/test_agent.py:18) | 16 | 四格、req 組裝、一信一題、陣列信、壞信、step 上限、精確 600 次、第五次錯誤、epoch、20 次重試、stuck 清除、退出碼、submit 失敗 |
| [test_tools.py](/home/guanyu/projs/aos/proto4-7/test/test_tools.py:17) | 9 | schema 補預設、正式／文字 call、普通文字、救回失敗、缺工具／壞參數、非零退出、截斷 |
| [test_user.py](/home/guanyu/projs/aos/proto4-7/test/test_user.py:18) | 6 | new、內建工具、say、listen、status、talk、reset |
| 合計 | **31** | 假 kernel、人工寫 result、本機 shell 工具 |

proto4-7 的 fake kernel 是把 helper request 複製到假 `K/llm/requests/`，測試再自行寫 result；這組測試**不是實際 kernel module→worker→HTTP 的整條端到端測試**。[fake kernel](/home/guanyu/projs/aos/proto4-7/test/test_agent.py:26)

kernel 的相關測試明確涵蓋「101 無競爭時留 cpu」「有人排隊時讓位」「waiting 在 ls 顯示」「101 不累計一般錯誤」。[退出碼政策測試](/home/guanyu/projs/aos/proto4-3/test/test_kernel_exit.py:18)

本次額外執行的唯讀驗證僅有：以 AST 統計上述測試方法，以及以純記憶體 HTTP 替身確認 `params.messages` 覆蓋與畸形 usage 的 `AttributeError`。崩潰窗口、撤單競態、首 tick 前提交等情況，均依原碼順序報告，未聲稱已做故障注入。