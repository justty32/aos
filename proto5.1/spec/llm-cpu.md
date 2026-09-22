# llm cpu 資料夾規範（第 1 版）

← [proto5.1 README](../README.md)｜程式：[aos-llm-cpu.md](aos-llm-cpu.md)｜交件者：[aos-agent.md](aos-agent.md)

一個 cpu 是一個資料夾。agent 把已組好的請求交進來，cpu 問一次模型，結果寫到請求指定的絕對路徑。

## 1. 資料夾

```
cpu/
  info.json              {"_metainfo": {"_type": "llm_cpu", "_version": 1}}
  requests/<name>.json    排隊
  running/<name>.json     已認領、正在問
  done/<name>.json        已完成（原始請求；成功與失敗都放這裡）
  .queue.lock            檔案轉移共用的短鎖；不是 pid／工作狀態
```

只有 `info.json` 必填；程式執行或 agent 交件時建立缺少的三個子資料夾。只掃描子資料夾第一層、
檔名以 `.json` 結尾的檔；`.tmp` 不算工作。`name` 由交件者取，agent 用 `<agent 資料夾名>-<epoch ns>`。
同名已在三處任一處＝拒收，不能覆蓋。agent 在共用短鎖內檢查三處，再先寫 `.tmp`、rename 到 requests。
手動留下的跨資料夾同名檔不刪不覆蓋，cpu 跳過它，繼續找下一份。

## 2. info.json

`_metainfo` 必填物件，`_type` 必須是 `llm_cpu`、`_version` 必須是整數 `1`（布林不算整數）。
指示詞規則同 [agent.md §2](agent.md)：info 的已知欄位解指示詞，中心路徑＝cpu 資料夾；
頂層、`_metainfo`、`_type`、`_version` 都能用 `$ref`／`$env` 等；不認任何 `$opt`，未知欄位忽略。

共用 `AgentError` 與 [agent.md §5](agent.md) 代號：

| 代號 | cpu 的情境 |
|---|---|
| `NotAnAgent` | 沒有 info、沒有 metainfo/type，或 type 不是 llm_cpu（沿用共用代號，白話明說 cpu） |
| `MetainfoInvalid` | metainfo 不是物件，或缺 version |
| `UnsupportedVersion` | version 不是整數 1 |
| `ReadFailed`／`JsonSyntax`／`NotAnObject` | 讀不到、JSON 壞、頂層不是物件；佇列或結果檔 I/O 失敗也沿用 ReadFailed |
| 指示詞代號 | 同 directives.md；請求與結果不解指示詞 |

## 3. 請求檔

```json
{
  "engine": {"endpoint": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3-1.7b",
             "params": {}, "api_key": null, "timeout_ms": 120000, "cpu": "/absolute/cpu"},
  "body": {"model": "qwen/qwen3-1.7b", "messages": [{"role": "user", "content": "你好"}]},
  "result": "/absolute/agent/ask-result.json"
}
```

- `engine`：agent **已解好**的那包（含 api_key）；cpu 不讀 agent 設定、不解指示詞。
  endpoint／model 必須是非空字串；params 若有必須是物件；api_key 允許字串或 null（load 的缺值）；
  timeout_ms 若有必須是正整數、沒寫預設 120000。型別不合＝`EngineInvalid`。
  `cpu` 與其他額外 engine 欄位不參與 HTTP body；HTTP 只送下面的 body。
- `body`：已組好的 chat/completions JSON 物件；cpu 原樣交給 `aos_llm_ask.call`，不重組、不解指示詞。
  非物件＝`FieldTypeMismatch`。訊息與工具內容由 agent 負責，cpu 不重驗它們。
- `result`：非空絕對路徑字串，不得含 NUL；不合＝`FieldTypeMismatch`。父目錄要已存在。
- 三格必填；未知欄位忽略。壞檔保留在原位、退出 1，供人修正；不猜測結果路徑或自行刪檔。

請求連同 api_key 留在 done；本階段不遮罩、不加密、不清理。

## 4. 結果檔

```json
{"ok": true, "message": {"role": "assistant", "content": "你好"}}
```

或：

```json
{"ok": false, "error": "白話失敗原因"}
```

先寫結果檔**同目錄的唯一 `.tmp`**，再 rename 到指定路徑；讀者看不到半份 JSON。成功 message 是
`choices[0].message` 原樣；失敗包含 HTTP／網路／模型錯誤與 cpu 收屍。結果發布後才把請求搬到 done。

固定 `ask-result.json` 沒有 request id，不能分辨不同請求共用結果路徑；交件者要避免對同一結果路徑
同時送多份。收屍若看到既有結果就保留（處理「已發布結果但還沒搬 done 就崩」）；既有結果若其實是
別份或壞檔，cpu 無法判斷，留給 agent 收回時驗。
