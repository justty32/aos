# proto4-5 — llm-cpu 第一版

## 一句話這是什麼

`llm-cpu` 是普通 cpu 上跑的一支程式：它收很多份 LLM 請求，按優先級排序，再分發給不同 endpoint。它不是 agent，不跑「推論→工具→執行」迴圈。

## 怎麼跑

先建一個家：

```sh
./llm-cpu init /tmp/my-llm
```

打開 `/tmp/my-llm/endpoints.json`，把 local 的 `base_url` 指到 LM Studio，`model` 填目前載入的那顆模型：

```json
{"name":"local","kind":"openai","base_url":"http://localhost:1234/v1","model":"你載入的模型 id","max_concurrent":1,"timeout_ms":300000}
```

寫一份 `/tmp/request.json`，投入佇列：

```sh
./llm-cpu submit /tmp/my-llm /tmp/request.json --name hello
./llm-cpu tick /tmp/my-llm
./llm-cpu ls /tmp/my-llm
cat /tmp/my-llm/results/hello.json
```

worker 在背景跑，所以推論沒回來時再過一會兒跑一次 `tick`，它才會把完成的原件收進 `requests/done/`。也可以把它放上 kernel，讓 kernel 每秒替它跑一格：

```sh
../proto4-3/aos-kernel add K /tmp/my-llm/inst.json
```

`inst.json` 的 cwd 已是這個家；每次 `aos-exec` 執行它，就是一格 `llm-cpu tick .`。錯誤看 `tick.err`，每格摘要看 `llm-cpu.log`，worker 自己的 stderr 看 `log/<id>.log`。

## 請求長什麼樣

最小請求：

```json
{"messages":[{"role":"user","content":"你好"}]}
```

| 欄位 | 必填 | 意思 |
|---|---:|---|
| `messages` | 是 | 非空陣列，原樣送進 chat completions |
| `endpoint` | 否 | endpoint 名字；沒給就用 `endpoints.json` 的 default |
| `priority` | 否 | 整數，越大越先；預設 0 |
| `timeout_ms` | 否 | 這一發的逾時；沒給就用 endpoint 設定 |
| `params` | 否 | 併進 HTTP body，例如 `max_tokens`、`temperature` |

頂層不准給 `model`。模型固定在 endpoint 設定，尤其本機一次只能載一顆。`--name` 只接受英數、點、底線與減號；不給就用 `time.time_ns()` 當 id。也可用 stdin：

```sh
printf '%s' '{"messages":[{"role":"user","content":"你好"}]}' | ./llm-cpu submit /tmp/my-llm - --name hello
```

## 結果長什麼樣

結果固定在 `results/<id>.json`，成功與失敗同一種外形：

| 欄位 | 意思 |
|---|---|
| `ok` | 成功是 true，失敗是 false |
| `id`／`endpoint`／`model` | 這一發的身分與實際回應模型 |
| `model_requested` | endpoint 設定裡要求的模型；成功失敗都有，方便跟實際回應模型對帳 |
| `text`／`finish_reason` | `choices[0]` 的文字與停止原因；失敗時為 null |
| `usage` | `prompt`、`completion`、`total`、`cached`、`reasoning`；沒有就 null |
| `ms` | worker 花的毫秒 |
| `raw` | endpoint 的整包 JSON 回應 |
| `error` | 成功為 null；失敗為 `{kind,msg,status,retryable}` |

常見 `error.kind`：

| kind | 意思 |
|---|---|
| `bad_request` | 請求格式、endpoint 名字或種類不合規 |
| `no_api_key` | endpoint 指定的環境變數沒有設定 |
| `http` | endpoint 回 HTTP 錯誤；500、429 等會標 retryable |
| `connect`／`timeout` | 連不上或逾時 |
| `bad_json`／`bad_response` | 回應不是 JSON，或少了必要欄位 |
| `model_mismatch` | 回應模型跟設定不同，可能是 LM Studio 換了模型；`strict_model:false` 可放行 |
| `worker_died` | worker 消失且沒留下結果；不自動重送 |
| `spawn`／`internal` | worker 起不來或內部未預期錯誤 |

每一發另 append 一行到 `usage.jsonl`，只有 endpoint 與模型名字，不會記 API key。

## endpoint 設定

`init` 會寫三筆範例：

```json
{
  "default": "local",
  "endpoints": [
    {"name":"local","kind":"openai","base_url":"http://localhost:1234/v1","model":"loaded-model-id","max_concurrent":1,"timeout_ms":300000},
    {"name":"deepseek","kind":"openai","base_url":"https://api.deepseek.com/v1","model":"deepseek-chat","max_concurrent":2,"timeout_ms":300000,"api_key_env":"DEEPSEEK_API_KEY","strict_model":false},
    {"name":"pi","kind":"process","argv":["pi","-p"],"enabled":false}
  ]
}
```

`enabled` 沒寫就是 true。`api_key_env` 放的是環境變數名字，不是 key；worker 需要時才從自己的環境讀。`strict_model` 沒寫就是 true，會要求回應模型與設定完全相同；DeepSeek 的 `deepseek-chat` 是別名、回應會寫真名，所以該 endpoint 設為 false。`kind: process` 這版只有設定槽，請求指到它會退件。

## 一格做什麼

1. 收尾 `requests/running/`：有結果就歸檔；worker 死了或超過硬上限就寫終局結果，不重送。
2. 驗新請求；壞件寫 `bad_request`，原件搬進 `requests/done/`。
3. 依 priority 大者、mtime 早者、名字排序。
4. 按每台 `max_concurrent` 分發；一台滿了會繼續看別台。
5. 原子寫 `state.json`，再 append 一行 `llm-cpu.log`；tick 永遠退出 0。

`state.json` 只是最近一格的儀表，不是請求真源。真源是 `requests/`、`requests/running/`、`requests/done/` 與 `results/`。

## 為什麼是背景 worker

普通 cpu 的一格應該很短，但一次推論常要幾十秒。tick 若自己等網路，整顆 cpu 會被佔住；所以它先把原件搬到 running、開一支脫離的 worker，立刻返回。後續 tick 再看 pid 與結果收尾。

這也代表「送出後 worker 消失」無法證明 endpoint 到底有沒有做過。第一版選擇回 `worker_died`、絕不偷偷重送，避免重複扣款或雙回覆；要重試由呼叫者用新 id 再投。

## 沒做什麼

沒有串流、取消、重試／退避、批次、費用計算、公平分數、LM Studio load／unload、process 型 endpoint、agent／工具與 MCP。也沒有多個 tick 同時跑的鎖。

## 測試

測試只打 `127.0.0.1` 上臨時開的假 server，不連 LM Studio、DeepSeek 或網路：

```sh
cd proto4-5
python3 -m unittest discover -s test
```

## 出處

邊界來自 [`proto4/notes/20-21-step-lisp-and-next.md`](../proto4/notes/20-21-step-lisp-and-next.md) §21／§21.1；舊版本採捨見 [`proto4/notes/llm-cpu/legacy-harvest.md`](../proto4/notes/llm-cpu/legacy-harvest.md)。OpenAI 回應與 usage 形狀參考 `reference/llmkit/llms/`，沒有 import 它。
