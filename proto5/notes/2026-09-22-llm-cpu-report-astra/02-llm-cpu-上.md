← [llm cpu 調查報告（astra）](../2026-09-22-llm-cpu-report-astra.md)（分檔 2/5）｜[上一份](01-術語與aos-llm.md)｜[下一份](03-llm-cpu-下.md)

**2．proto4-5 第二層：llm-cpu**

**2.1 程式分工**

| 檔案 | 職責 |
|---|---|
| [llm_cpu.py:11](../../../proto4-5/llm_cpu.py) | `init`／`tick`／`submit`／`ls`／內部 `worker` CLI |
| [llm_cpu_home.py:43](../../../proto4-5/llm_cpu_home.py) | 建家、原子 JSON、submit、endpoint 文件、獨立模式 ls |
| [llm_cpu_request.py:15](../../../proto4-5/llm_cpu_request.py) | ID 驗證、請求指紋、查同名單所在位置 |
| [llm_cpu_tick.py:231](../../../proto4-5/llm_cpu_tick.py) | 收尾、驗件、排序、容量、派工、snapshot／log |
| [llm_cpu_worker.py:37](../../../proto4-5/llm_cpu_worker.py) | 在背景同步問模型、寫結果與 usage |
| [llm_cpu_module.py:13](../../../proto4-5/llm_cpu_module.py) | 接 kernel 的四個 hook；syscall、兩段等待、module 摘要 |
| [llm_cpu_manage.py:31](../../../proto4-5/llm_cpu_manage.py) | `aos-kernel llm ls/rm`，直接查檔／殺 worker／刪單 |

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

其中 `endpoints` 的 value 是**各 endpoint 正在 running 的件數**，不是 endpoint 設定物件。真正佇列／執行狀態由各資料夾中的檔案決定。[建家:43](../../../proto4-5/llm_cpu_home.py)、[snapshot:242](../../../proto4-5/llm_cpu_tick.py)

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

排程 ID 來自 `--name`／module ticket 的 `id`／未指定時的 `time.time_ns()`。限制是 `[A-Za-z0-9._-]+`，但額外禁止 `"."`、`".."`、以及以 `.tmp` 結尾。[ID 驗證:7](../../../proto4-5/llm_cpu_request.py)、[request 驗證:110](../../../proto4-5/llm_cpu_tick.py)

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

獨立模式 CLI `submit` 是**複製原始 bytes**，此時不解析、不驗 JSON，因此可以成功投入壞 JSON；下一 tick 才退件。module 使用 `submit_object()`，先驗 request，才序列化投遞。[兩種 submit:74](../../../proto4-5/llm_cpu_home.py)

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

來源：[worker 寫結果:37](../../../proto4-5/llm_cpu_worker.py)、[scheduler 錯誤 result:15](../../../proto4-5/llm_cpu_tick.py)。

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

不是每個終局都會有 usage：**只有 worker 的 `_write_usage()` 會寫**；tick 自行退件、`worker_died`、spawn 失敗或 watchdog timeout 不會補 usage。[usage 實作:16](../../../proto4-5/llm_cpu_worker.py)

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

來源：[tick 主流程:231](../../../proto4-5/llm_cpu_tick.py)。

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

