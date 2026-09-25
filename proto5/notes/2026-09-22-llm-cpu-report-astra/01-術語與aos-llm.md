← [llm cpu 調查報告（astra）](../2026-09-22-llm-cpu-report-astra.md)（分檔 1/5）｜[下一份](02-llm-cpu-上.md)

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

來源：[proto5 agent 格式](../../spec/agent/README.md)、[三格規範](../../spec/aos-agent/README.md)、[engine 與請求規範](../../../proto5.1/spec/aos-llm-ask.md)、[函式庫說明:243](../../lib/README.md)、[現有同步 think:215](../../lib/aos_agent.py)。

---

**1．proto4-5 第一層：`aos-llm`**

**1.1 檔案分工**

| 檔案 | 實際職責 |
|---|---|
| [aos-llm:1](../../../proto4-5/aos-llm) | 薄入口，呼叫 `aos_llm.main()` |
| [aos_llm.py:89](../../../proto4-5/aos_llm.py) | endpoint／request 驗證、HTTP、模型預檢、result 正規化 |
| [aos_llm_cli.py:15](../../../proto4-5/aos_llm_cli.py) | endpoint 檔選取、REQ／OUT 檔案與 stdin/stdout、CLI 退出碼 |
| [llm_cpu_worker.py:37](../../../proto4-5/llm_cpu_worker.py) | 第二層的使用者：直接 import `aos_llm.call()`，沒有再啟動 `aos-llm` CLI |

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

來源：[第一層驗證:45](../../../proto4-5/aos_llm.py)、[CLI 選 endpoint:20](../../../proto4-5/aos_llm_cli.py)、[第二層載設定:149](../../../proto4-5/llm_cpu_home.py)、[第二層 endpoint 驗證:127](../../../proto4-5/llm_cpu_tick.py)。

API key 細節：

| 情況 | 行為 |
|---|---|
| 沒寫 `api_key_env` | 不送 Authorization |
| 有寫，環境變數不存在 | `no_api_key`，不打 HTTP |
| 環境變數存在但值為空字串 | 仍組 `Authorization: Bearer `，沒有把空值視為缺 key |
| module／worker 模式 | worker 繼承排程行程的環境；沒有從 agent 的請求 JSON 傳遞 API key |

來源：[headers:73](../../../proto4-5/aos_llm.py)、[worker 啟動:209](../../../proto4-5/llm_cpu_tick.py)。

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

單一 endpoint 檔加 `#name` 會被拒絕。OUT 不會自動建立父目錄。第一層沒有 `--wait`、排隊、`--dry-run` 或重試旗標。[CLI 實作:20](../../../proto4-5/aos_llm_cli.py)

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

來源：[請求驗證及 body 組裝:95](../../../proto4-5/aos_llm.py)。`params.messages` 覆蓋行為另以純記憶體 `_open` 替身確認，未連網。

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

`models()` 要求回應物件含 `data` 陣列；只收其中為物件且 `id` 是字串的項目，其他項目略過。[預檢與 POST:125](../../../proto4-5/aos_llm.py)、[models:204](../../../proto4-5/aos_llm.py)

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

`tool_calls` **不提升到 result 頂層**，保留在 `raw.choices[0].message.tool_calls`。回覆有 `content:null` 與 tool calls 可以成功；若完全缺 `content`，第一層會回 `bad_response`。[usage／錯誤 envelope:11](../../../proto4-5/aos_llm.py)、[成功回覆擷取:174](../../../proto4-5/aos_llm.py)

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

第一層不因 `retryable:true` 自動重試。另外，函式不是對任意畸形回覆都保證回 result：例如非空非物件的 `prompt_tokens_details` 會讓 `_usage()` 拋 `AttributeError`；直接 CLI 沒有總括捕捉，第二層 worker 才會把這類例外包成 `internal`。此例外路徑已用純記憶體替身確認。[CLI 邊界:93](../../../proto4-5/aos_llm_cli.py)、[worker 例外封裝:37](../../../proto4-5/llm_cpu_worker.py)

---

