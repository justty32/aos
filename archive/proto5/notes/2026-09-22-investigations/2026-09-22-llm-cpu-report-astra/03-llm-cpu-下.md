← [llm cpu 調查報告（astra）](../2026-09-22-llm-cpu-report-astra.md)（分檔 3/5）｜所在：2. proto4-5 第二層：llm-cpu｜[上一份](02-llm-cpu-上.md)｜[下一份](04-aos-agent交出與收回.md)

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

spawn 失敗會立即寫 `spawn` 錯誤 result、將 request 移入 done。worker 不負責把 request 移入 done。[dispatch:192](../../../../proto4-5/llm_cpu_tick.py)、[worker:37](../../../../proto4-5/llm_cpu_worker.py)

**2.7 收尾、逾時、重試與撤單**

| 機制 | 判定／動作 | 所在檔 |
|---|---|---|
| 已有 result | 只判 `result_path.exists()`，不解析 result；request 移 done | [tick:72](../../../../proto4-5/llm_cpu_tick.py) |
| running metadata 壞 | 寫 `worker_died`，移 done | 同上 |
| PID 不存在／無有效 PID | `os.kill(pid,0)` 判存活；沒有結果則 `worker_died`，移 done | [tick:51](../../../../proto4-5/llm_cpu_tick.py) |
| HTTP timeout | 第一層 urllib timeout；worker 寫 timeout result | [aos_llm:154](../../../../proto4-5/aos_llm.py) |
| scheduler hard timeout | `time.time()-started > timeout_ms+5000ms`；SIGTERM **單一 PID**，寫 timeout，移 done | [tick:98](../../../../proto4-5/llm_cpu_tick.py) |
| hard timeout 的等待／升級 | 不等待退出，不升 SIGKILL | 同上 |
| 自動重試 | 第一層、worker、scheduler 都沒有；不消費 `retryable` 來重送 | 上述呼叫鏈 |
| `llm rm` 刪 queued | 直接刪 request/result 等同名檔 | [manage:107](../../../../proto4-5/llm_cpu_manage.py) |
| `llm rm` 刪 running | 先讀 PID；對 process group SIGTERM 等 1 秒，再 SIGKILL 等 1 秒 | [manage:85](../../../../proto4-5/llm_cpu_manage.py) |
| `llm rm` 清除範圍 | queued、running、done request、result 四处 | [manage:112](../../../../proto4-5/llm_cpu_manage.py) |
| `llm rm` 保留項目 | worker log、usage、tick log、state snapshot 不同步清除 |
| 遠端取消 | 沒有呼叫供應商 cancellation API；本地殺 worker 不等於撤回已抵達供應商的請求 |

其他明確邊界：

- hard timeout 要等下一次 tick 才檢查；tick 停止時不會自行執行。
- HTTP 預檢和 chat 可以各耗一個 timeout，但 scheduler 的 hard timeout 從 worker 派工起算，只給一個 timeout 加 5 秒。
- tick 判活只用 `kill(pid,0)`；管理指令的 `_alive()` 另讀 `/proc/<pid>/stat` 排除 zombie，兩處不相同。
- 已有結果檔優先於 PID／timeout 檢查。
- `llm rm` 遇到 running 記錄沒有可殺 PID 時退 1，保留檔案；既有測試有覆蓋。[管理測試:115](../../../../proto4-5/test/test_module_manage.py)

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

它會忽略物件 key 順序與序列化空白，**沒有補入 default endpoint、priority 等預設值做語意正規化**；也不把 endpoint 設定內容納入 fingerprint。[fingerprint 與搜尋次序:21](../../../../proto4-5/llm_cpu_request.py)

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

來源：[CLI:35](../../../../proto4-5/llm_cpu.py)、[module hooks:37](../../../../proto4-5/llm_cpu_module.py)。

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

不是模型 response。[module CLI:98](../../../../proto4-5/llm_cpu_module.py)、[handle:37](../../../../proto4-5/llm_cpu_module.py)

| 等待階段 | 時限 | 逾時後 |
|---|---|---|
| 等 kernel 收件回音 | `max(3秒, 3×config.interval_ms/1000)`，每 50ms 查一次 | 嘗試刪尚存的 syscall 原檔；退 1 |
| 等模型 result | **收件成功後**另外起算 `--wait SECS`，每 50ms 查一次 | 不刪 queued／running request，不殺 worker；印「已送出」，退 1 |
| `--wait 0` | 仍先讀一次 result | 有現成結果可成功；沒有則立即回逾時 |
| 不帶 `--wait` | 仍然等 kernel 收件回音 | 不是寫完 syscall 就立刻退出 |

`--wait` 不會幫 kernel 跑 tick。`--json` 輸出完整 result 後仍會另外印一行「結果檔：…」，所以 stdout **不是只有一個 JSON 文件**。預設只印 `result.text`；tool-call-only result 的 text=null 時會印空行。[等待實作:174](../../../../proto4-5/llm_cpu_module.py)

兩個時序邊界，由程式順序推導、現有測試未覆蓋：

| 邊界 | 結果 |
|---|---|
| 第一個 kernel tick 之前投 LLM syscall | kernel 先 handle syscall、後跑 module.tick 建家；handle 讀不到 endpoints，先回失敗，同一 tick 稍後才建好 `K/llm` |
| 回音逾時撤單時，kernel 已讀入 ticket 但還沒刪原檔 | CLI 可能成功 unlink、印「沒送出去」；kernel 仍可用記憶體內的 ticket 完成排入 |

來源：[kernel 先 syscall 後 module tick:48](../../../../proto4-3/aos_kernel_tick.py)、[建家位置:21](../../../../proto4-5/llm_cpu_module.py)、[撤單:154](../../../../proto4-5/llm_cpu_module.py)、[syscall 未先 claim:86](../../../../proto4-3/aos_kernel_syscall.py)。

**2.11 第二層的崩潰窗口**

| 中斷位置 | 重開後可見行為／限制 |
|---|---|
| result 已寫，running 尚未移 done | 下次 tick 看見 result 即移 done；此段可自然收尾 |
| result 已寫，usage 尚未 append | result 可讀；下次 tick 不補 usage |
| request 已移 running、worker 尚未開 | `pid:null`；下次 tick 判 `worker_died`，不重送 |
| worker 已開、PID 尚未寫回 | 下次 tick 可能把仍在跑的工作判為 `worker_died`；原 worker 仍可能寫結果 |
| hard timeout 發 SIGTERM 後 | scheduler 立即寫 timeout／移 done，沒有等待 worker 終止；若 worker 未終止，仍存在後續寫 result 的窗口 |
| 兩個 tick 同時跑 | 沒有鎖，會競爭相同 request／temp／running 檔 |

以上是可由寫入順序直接辨識的窗口，不是本次故障注入測試的結果。[dispatch 與 PID 寫回:200](../../../../proto4-5/llm_cpu_tick.py)、[worker 寫入順序:54](../../../../proto4-5/llm_cpu_worker.py)

---

