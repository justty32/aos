# proto4-5 — 一次呼叫與 LLM 排程

這裡有兩層：第一層 `aos-llm` 像 cuda，替任何 inst 做一次同步 LLM 呼叫；第二層
收很多請求、排隊，再按 endpoint 容量派工。第二層可當獨立行程跑，也可掛成 kernel module
（推薦）。兩種掛法共用 `aos_llm.call`，HTTP
實作只有一份。

## 第一層：`aos-llm`

### 呼叫一次

```sh
./aos-llm call ENDPOINT REQ OUT [--timeout-ms N]
```

- `ENDPOINT` 有三種寫法：單一 endpoint JSON 檔；`endpoints.json#local` 挑具名項目；
  `endpoints.json` 不加 `#` 時挑 `default`。
- `REQ` 是 JSON 檔或 `-`（stdin），`messages` 必填；可有 `priority`（這層忽略）、
  `timeout_ms`、`params`、`id`，不准有 `model`。
- `OUT` 是結果檔或 `-`（stdout）；檔案先寫 `.tmp` 再以 rename 發佈。
- `--timeout-ms` 會蓋過請求與 endpoint 的 HTTP timeout。

例子：

```sh
./aos-llm call endpoints.json#local request.json result.json
printf '%s' '{"messages":[{"role":"user","content":"hi"}]}' \
  | ./aos-llm call endpoint.json - -
```

退出碼：成功結果 `ok:true` 是 0；呼叫完成但結果 `ok:false` 是 1，仍會寫 OUT，並在
stderr 印一行 `aos-llm: <kind>: <msg>`；用法錯、輸入檔讀不到或 ENDPOINT 解不開是 2。
REQ 含 `model` 屬於可寫成結果的 `bad_request`，所以退出 1。

結果固定有：`ok`、`id`、`endpoint`、`model`、`model_requested`、`text`、
`finish_reason`、`usage`、`ms`、`raw`、`error`。`usage` 固定有 `prompt`、
`completion`、`total`、`cached`、`reasoning`；失敗的 `error` 是
`{kind,msg,status,retryable}`。

Python 也能直接用，不需要家、不碰檔案：

```python
import aos_llm
result = aos_llm.call(endpoint, request)
listing = aos_llm.models(endpoint)
```

endpoint 必須有非空的 `name`、`base_url`、`model`，且 `kind` 只能是 `openai`；
`timeout_ms` 預設 300000。`api_key_env` 填環境變數名字，沒設時回 `no_api_key`；
`strict_model` 預設 true，實際模型不同時回 `model_mismatch`。

### 看 endpoint 的模型

```sh
./aos-llm models endpoints.json#local
```

它 GET `<base_url>/models`，把 id 一行一個印出。成功退出 0，endpoint 或 HTTP 失敗退出
1；ENDPOINT 檔解不開是 2。

## 第二層：排程（kernel module 推薦，獨立行程仍可用）

推薦讓 kernel 每回合順手跑排程 module；家固定在 `K/llm/`，第一次 kernel tick 會建好範例
`endpoints.json`，但不會建 `inst.json`：

```sh
../proto4-3/aos-kernel-init K --ncpu 2 --module /abs/proto4-5/llm_cpu_module.py
(cd K && aos-kernel-tick)
$EDITOR K/llm/endpoints.json
aos-kernel llm K request.json --name hello --wait 60
```

不想等就省略 `--wait`，之後看 `K/llm/results/hello.json`。`--wait` 只輪詢結果，**不會替
kernel 跑 tick**；daemon／kernel 必須真的在跑，否則 syscall 沒人收、結果也不會前進。

`llm-cpu` CLI 仍保留獨立行程的掛法：

```sh
./llm-cpu init /tmp/my-llm
./llm-cpu submit /tmp/my-llm request.json --name hello
./llm-cpu tick /tmp/my-llm
./llm-cpu ls /tmp/my-llm
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

`init` 的 endpoints.json 範例含 local、DeepSeek 與停用的 process 槽。這版排程只派
`kind:openai`；`enabled:false` 會退件。DeepSeek 的模型名是別名時可設
`strict_model:false`。

## 錯誤與尚未做的事

常見 `error.kind`：`bad_request`、`no_api_key`、`http`、`connect`、`timeout`、
`bad_json`、`bad_response`、`model_mismatch`；排程層另有 `worker_died`、`spawn`、
`internal`。HTTP 429 與 5xx、連線及逾時會標 `retryable:true`。

沒有串流、取消、自動重試／退避、批次、費用計算、公平分數、LM Studio load／unload、
process 型 endpoint、agent／工具與 MCP；也沒有多個 tick 同時跑的鎖。

## 測試與出處

測試只打 `127.0.0.1` 的臨時假 server：

```sh
cd proto4-5
python3 -m unittest discover -s test
```

兩層裁決與第一層規格見 [`proto4/notes/22-llm-cpu.md`](../proto4/notes/22-llm-cpu.md)
§22.6、§22.7；舊版採捨見
[`proto4/notes/llm-cpu/legacy-harvest.md`](../proto4/notes/llm-cpu/legacy-harvest.md)。
