# proto4-5 — 一次呼叫與 LLM 排程

這裡有兩層：第一層 `aos-llm` 像 cuda，替任何 inst 做一次同步 LLM 呼叫；第二層
收很多請求、排隊，再按 endpoint 容量派工。第二層可當獨立行程跑，也可掛成 kernel module
（推薦）。兩種掛法共用 `aos_llm.call`，HTTP
實作只有一份。

以下假設 `proto4-3` 與 `proto4-5` 都已用絕對路徑加進 `PATH`，所以指令直接寫
`aos-kernel`、`aos-llm`，不加 `./`。

## 第一層：`aos-llm`

### 呼叫一次

先建 endpoint 設定。單一 endpoint 檔 `endpoint.json` 可以直接抄這份：

```json
{
  "name": "local",
  "kind": "openai",
  "base_url": "http://localhost:1234/v1",
  "model": "google/gemma-4-e4b",
  "timeout_ms": 300000
}
```

要用 `endpoints.json#local` 或日後放多個 endpoint，就抄這份完整的 `endpoints.json`：

```json
{
  "default": "local",
  "endpoints": [{
    "name": "local", "kind": "openai",
    "base_url": "http://localhost:1234/v1",
    "model": "google/gemma-4-e4b", "timeout_ms": 300000
  }]
}
```

先跑 `aos-llm models endpoint.json` 確認 LM Studio 實際列出的 id；若不同，便把
`model` 換成它印出的那一行。接著才呼叫：

```sh
aos-llm call ENDPOINT REQ OUT [--timeout-ms N]
```

- `ENDPOINT` 有三種寫法：單一 endpoint JSON 檔；`endpoints.json#local` 挑具名項目；
  `endpoints.json` 不加 `#` 時挑 `default`。
- `REQ` 是 JSON 檔或 `-`（stdin），`messages` 必填；可有 `tools`／`tool_choice`（OpenAI 格式，原樣轉給模型；模型的 `tool_calls` 在結果的 `raw.choices[0].message` 裡）、`priority`（這層忽略）、
  `timeout_ms`、`params`、`id`，不准有 `model`。
- `OUT` 是結果檔或 `-`（stdout）；檔案先寫 `.tmp` 再以 rename 發佈。
- `--timeout-ms` 會蓋過請求與 endpoint 的 HTTP timeout。

例子：

```sh
aos-llm call endpoints.json#local request.json result.json
printf '%s' '{"messages":[{"role":"user","content":"hi"}]}' \
  | aos-llm call endpoint.json - -
```

退出碼：成功結果 `ok:true` 是 0；呼叫完成但結果 `ok:false` 是 1，仍會寫 OUT，並在
stderr 印一行 `aos-llm: <kind>: <msg>`；用法錯、輸入檔讀不到或 ENDPOINT 解不開是 2。
REQ 含 `model` 屬於可寫成結果的 `bad_request`，所以退出 1。

結果欄位分三組看：

- 日常：`ok`、`text`、`usage`、`ms`、`error`。`usage` 固定有 `prompt`、
  `completion`、`total`、`cached`、`reasoning`；失敗的 `error` 是
  `{kind,msg,status,retryable}`。
- 除錯：`id`、`endpoint`、`model`、`model_requested`、`finish_reason`、`notes`。
  `model` 永遠是供應商回應裡的 model；還沒收到合法回應就是 `null`。設定裡想送的值只看
  `model_requested`。`notes` 會記不阻擋呼叫的狀況。
- 原始供應商資料：`raw`。保留它是為了供應商多回欄位、格式有差異或需要對帳時仍有原證據；
  平常不用讀。

Python 也能直接用，不需要家、不碰檔案：

```python
import aos_llm
result = aos_llm.call(endpoint, request)
listing = aos_llm.models(endpoint)
```

endpoint 必須有非空的 `name`、`base_url`、`model`，且 `kind` 只能是 `openai`；
`timeout_ms` 預設 300000。`api_key_env` 填環境變數名字，沒設時回 `no_api_key`；
`strict_model` 預設 true：送 chat 前先查 `/models`，找不到設定的 id 就回
`model_not_found`，不送 chat、不花 token。若 `/models` 連不上或回非 200，則不阻擋
chat，原因記在 `notes`；`strict_model:false` 完全略過預檢。供應商實際回覆後仍會做原有的
`model_mismatch` 檢查。

### 看 endpoint 的模型

```sh
aos-llm models endpoints.json#local
```

它 GET `<base_url>/models`，把 id 一行一個印出。成功退出 0，endpoint 或 HTTP 失敗退出
1；ENDPOINT 檔解不開是 2。

## 第二層：排程（kernel module 推薦，獨立行程仍可用）

推薦讓 kernel 每回合順手跑排程 module；家固定在 `K/llm/`，第一次 kernel tick 會建好範例
`endpoints.json`，但不會建 `inst.json`：

```sh
setsid -f aos-daemon
aos-kernel-init K --ncpu 2 --module /abs/proto4-5/llm_cpu_module.py
aos-kernel-boot K
sleep 2                       # 等至少一回合，讓 module 生出設定檔
$EDITOR K/llm/endpoints.json  # 把 local 的 model 換成 aos-llm models 看到的 id
aos-kernel llm K request.json --name hello --wait 60
```

成功等到時預設只印回答文字與結果檔路徑；加 `--json` 才會印完整結果。不想等就省略
`--wait`，命令會印路徑並說明由下一回合處理，之後看 `K/llm/results/hello.json`。
`--wait` 只輪詢結果，**不會替 kernel 跑 tick**。
kernel 沒活著時，不管有沒有 `--wait`，單子都會撤掉、不排隊。

等 kernel 回單逾時時，CLI 會先看 syscall：還在 `K/syscalls/` 就撤掉並明說「沒送出去」；
已被撿走則明說「已送出，還沒做完」，並指出稍後會出現的結果檔。後一種仍可能花資源、
產生回覆；不需要時等它完成後刪掉那個結果檔。

同一個 `--name` 已在 requests／running／results 時，會比較正規化請求的 SHA-256。內容相同
視為同一張：不重送、不重複花 token，印結果路徑並成功退出，`--wait` 仍照常等；內容不同
才回「id 已經存在」，並指出撞到哪一處。這讓逐步程式 `--reset` 後重跑 `llm_submit` 不會
卡在已經投過的同一張。排程結果裡的 `request_sha256` 就是這個對帳指紋。

查單與刪單直接讀 `K/llm/`，daemon 沒活著也能用：

```sh
aos-kernel llm ls K          # queued／running／done，各筆含 endpoint 與送出時間
aos-kernel llm rm K hello    # running 會先砍 worker，再清 request／result
```

`rm` 找不到名字會退 1；撞名時也可換一個 `--name`。`aos-kernel ls K` 的 module 摘要看的是
上一回合寫下的帳，最多落後一回合；要看當下每張單的位置就用 `aos-kernel llm ls K`。

`llm-cpu` CLI 仍保留獨立行程的掛法：

```sh
llm-cpu init /tmp/my-llm
llm-cpu submit /tmp/my-llm request.json --name hello
llm-cpu tick /tmp/my-llm
llm-cpu ls /tmp/my-llm
cat /tmp/my-llm/results/hello.json
```

請求除了第一層欄位，還可用 `endpoint` 選 endpoints.json 裡的名字；省略就用 default。
`priority` 越大越先。`submit --name` 只接受英數、點、底線、減號；省略時用
`time.time_ns()`。

一格依序：收尾 running、退掉壞請求、按 priority／mtime／名字排序、按容量派工、原子寫
`state.json` 並 append `llm-cpu.log`。worker 在背景等幾十秒，後續 tick 再收尾；若 worker
消失而沒有結果，就回 `worker_died`，不偷偷重送，避免重複扣款或雙回覆。

家的真源是 `requests/`、`requests/running/`、`requests/done/`、`results/`；
`state.json` 只是最近一格的儀表。每一發另 append `usage.jsonl`，不記 API key。

`init` 與 module 自動建立的 endpoints.json **只含本機 local**，不會偷偷帶入任何可能
花錢的 endpoint。第一次建立時也會提醒你換掉 model。這版排程只派 `kind:openai`；
`enabled:false` 會退件。若日後要自己加遠端或 process 設定，格式例如：

```json
[
  {"name":"deepseek","kind":"openai","base_url":"https://api.deepseek.com/v1",
   "model":"deepseek-chat","max_concurrent":2,"timeout_ms":300000,
   "api_key_env":"DEEPSEEK_API_KEY","strict_model":false},
  {"name":"pi","kind":"process","argv":["pi","-p"],"enabled":false}
]
```

上面只是格式範例，不會自動寫進設定；目前排程仍不支援 process endpoint。

## 錯誤與尚未做的事

常見 `error.kind`：`bad_request`、`no_api_key`、`http`、`connect`、`timeout`、
`bad_json`、`bad_response`、`model_not_found`、`model_mismatch`；排程層另有 `worker_died`、`spawn`、
`internal`。HTTP 429 與 5xx、連線及逾時會標 `retryable:true`。

沒有串流、取消、自動重試／退避、批次、費用計算、公平分數、LM Studio load／unload、
process 型 endpoint、agent／工具與 MCP；也沒有多個 tick 同時跑的鎖。

## 測試與出處

測試檔在 `test/`，只打 `127.0.0.1` 的臨時假 server；從 repo 根目錄跑：

```sh
cd proto4-5
python -m unittest discover -s test
```

兩層裁決與第一層規格見 [`proto4/notes/22-llm-cpu.md`](../proto4/notes/22-llm-cpu.md)
§22.6、§22.7；舊版採捨見
[`proto4/notes/llm-cpu/legacy-harvest.md`](../proto4/notes/llm-cpu/legacy-harvest.md)。
