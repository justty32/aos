← [daemon／kernel 調查報告（astra）](../2026-09-22-daemon-kernel-report-astra.md)（分檔 4/6）｜所在：3. aos-kernel｜[上一份](03-aos-kernel-入口到退出碼.md)｜[下一份](05-aos-kernel-llm檔案到測試.md)

**3.11 換檔、執行中工作與崩潰**

| 情況 | 現況 |
|---|---|
| quantum／waiting swap | 只換 CPU 指令檔，不中斷已開始的子程式 |
| rm 正在 CPU 上的行程 | 換 idle，不等待或 kill 該次 invocation |
| done／bad park | 先寫 idle tmp，刪目的地舊同名檔，hard-link CPU 到歸檔處，再 replace idle |
| park 後有 queue | 本 CPU 該輪不補人，下輪才可能 take |
| 多 CPU | scheduler 不檢查 entry.running；剛換下的 pid 可被後面的 idle CPU 取走 |
| 同邏輯行程重疊 | 因上一 CPU 的 invocation 可尚未結束，另一 CPU 已開始相同 pid；**這是由程式流程可推導的情況，本輪未動態實跑** |
| state 消失／壞掉 | 讀成空表；不從 CPU inst 反推出原 pid |
| daemon 重啟 | 還要有人讓 kernel tick 再跑；kernel 自己不是由新 daemon 自動復原 |
| CPU daemon entry 消失 | 下一 tick 嘗試補 add；保留存在的 CPU 指令檔 |
| CPU 指令檔消失 | 補 idle，原 cur 清掉，不自動還原原行程 |
| 多個 tick 同時跑 | 沒有鎖 |
| 檔案與 state | hard-link／replace／save state 是不同步驟，沒有跨檔交易或通用 crash recovery |

來源：[aos_kernel_schedule.py:111](../../../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:158](../../../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_syscall.py:136](../../../../proto4-3/aos_kernel_syscall.py)。

**3.12 內建 syscall：rm**

請求：

```json
{"op":"rm","pid":"行程名稱"}
```

回應：

```json
{"ok":true,"msg":"rm 行程名稱（原本在佇列）"}
```

| 欄位／項目 | 型別／預設／行為 |
|---|---|
| `op` | 必須辨識為 `"rm"`；其餘交 module |
| `pid` | raw syscall 要非空字串；handler **不禁止 `/`** |
| CLI NAME | CLI 另外禁止空字串及 `/` |
| 其他請求欄位 | 忽略，不複製到回應 |
| 回應 `ok` | boolean |
| 回應 `msg` | string |
| 關聯方式 | request/done 同檔名，沒有額外 correlation id |
| CLI 票名 | `<time.time_ns()>-rm-<pid>.json` |
| CLI 等待 | 固定 `max(3秒, 3×config.interval_ms/1000)`；每 0.05 秒，用 monotonic |
| `--wait` | **rm 沒有這個旗標** |
| 等到回音 | 讀取、刪 done、印 msg；ok→0，否則1 |
| 超時 | 退出1，**不撤 request**；稍後仍可刪行程 |
| 回音寫失敗 | tick 記 note，仍嘗試刪 request |
| request 刪失敗 | 記 note；下次 tick 可能重複處理 |

rm 查找順序：

| 次序 | 找到時做什麼 |
|---|---|
| 1：CPU 0..N-1 | 第一個同 pid cur 換 idle、清 cur 與 waiting，立即回成功 |
| 2：procs | unlink 指令檔、清 waiting；queue 稍後由 schedule 清 |
| 3：done 與 bad | 清兩處同名普通檔案，成功訊息列出清了哪些 |
| 全部沒有 | `ok:false`，msg 說佇列、CPU、done、bad 都沒有 |

壞 JSON、非物件、缺 op、未知 op、rm 缺 pid，都會嘗試寫負回音再刪原單。**沒有把原單搬到 done；done 是另造的回應。**

來源：[aos_kernel_syscall.py:18](../../../../proto4-3/aos_kernel_syscall.py)、[aos_kernel_syscall.py:72](../../../../proto4-3/aos_kernel_syscall.py)、[aos_kernel_syscall.py:136](../../../../proto4-3/aos_kernel_syscall.py)。

**3.13 module 機制**

登記方式只有 `config.modules`；init 的 `--module` 幫忙填入它，沒有動態 module 登記 syscall。

| 項目 | 契約／實作 |
|---|---|
| 檔案 | 一支 Python 檔 |
| `NAME` | 必須非空字串；作 CLI 子命令名 |
| `OPS` | 必須 tuple，每項為非空字串；允許空 tuple |
| `handle(h,cfg,st,ticket)` | 可省；回二元組 `(ok,msg)`；kernel 強制 `bool(ok),str(msg)` |
| `tick(h,cfg,st)` | 可省；回 list 才把各項轉字串、一行化加到 notes；其他回值忽略 |
| `status(h,cfg)` | 可省；非 None 的回值直接 print |
| `cli(h,cfg,argv)` | 可省；回值直接當 CLI 回碼 |
| hook 型別 | 若非 None，必須 callable；不預驗函式參數或回值型別 |
| 載入時機 | tick、ls、module CLI 各自載入 |
| import 名稱 | `aos_kernel_module_`＋絕對路徑 SHA-256 前16字元 |
| import 路徑 | 暫時把 module 所在資料夾放到 sys.path[0] |
| 隔離 | 同一個 Python process；只有例外捕捉，**不是 subprocess 或 sandbox** |
| 例外 | 載入及 hooks 捕捉 `BaseException`，包括 SystemExit |
| 重複 NAME／OPS | 不拒絕；依 config 順序選第一個符合者 |
| 內建 rm | 優先於任何 module 的同名 op |
| CLI 找 K | 在 module 後面的**前兩個參數**中找含 config.json 的資料夾，找到後抽掉；否則用 cwd |
| 載入失敗顯示 | tick 記 log note，ls 印 note；module CLI 不會統一印所有 load notes |

module 可以改動傳入的 state；核心不對 module 的副作用做回滾。

來源：[aos_kernel_module.py:16](../../../../proto4-3/aos_kernel_module.py)、[aos_kernel.py:171](../../../../proto4-3/aos_kernel.py)、[aos_kernel_status.py:92](../../../../proto4-3/aos_kernel_status.py)。

**3.14 `ls` 的輸出來源**

| 顯示 | 計算／來源 |
|---|---|
| daemon 家 | **只讀環境變數 `AOS_DAEMON_HOME`**；沒有使用 `~/.aos-daemon` fallback |
| 找不到家 | env 沒設／空，或該路徑不是資料夾 |
| daemon 沒在跑 | 找得到家，但 state 沒有整數 pid |
| daemon alive/dead | 用 daemon state 的 pid 檢查 `/proc`；不是讀 daemon.pid |
| CPU | 0..ncpu-1 |
| PROC | cur.pid；null 顯示 idle |
| ON | `time.time()-since`，一位小數秒 |
| RUNS | daemon.runs−cur.runs_at；無資料顯示 `-`；不保證是行程歷來總次數 |
| LAST_EXIT | 有 cur、差值非零才顯示；kind=aos 顯示 `125(aos)`；剛換上 runs=0 顯示 `-` |
| CPU_STATE | daemon entry.state；沒 entry 顯示「沒插上」；cur waiting 時覆蓋成 waiting |
| WAIT | cur.wait_runs，文字「等了 N 回合」 |
| 佇列 | state.queue；waiting map 有紀錄則附等待次數 |
| bad | bad 目錄普通檔案數；原因從 kernel.log 倒找最近含「退件」的行，不是逐檔 error |
| done | done 下 `.json` stem，按 pid 規則排序 |
| module | 各 module status hook 輸出 |

`ls` 不推 tick、不修 queue、不補 CPU；daemon dead 或 module status 出錯，正常仍可退出 0。

來源：[aos_kernel_status.py:9](../../../../proto4-3/aos_kernel_status.py)。

**3.15 LLM module：kernel 實際接到的介面**

`proto4-5/llm_cpu_module.py`：

```python
NAME = "llm"
OPS = ("llm",)
```

它使用全部四個 hook。家固定 `K/llm/`，由 module tick 第一次建立；**不建 `K/llm/inst.json`**，因為排程由 kernel tick 直接呼叫。

核心只傳遞 ticket 和呼叫 hook；以下 LLM 格式由 proto4-5 實作，不是 kernel 核心驗證。

LLM syscall：

```json
{
  "op": "llm",
  "id": "hello",
  "request": {
    "messages": [{"role":"user","content":"hi"}]
  }
}
```

| 欄位 | 型別／預設 | 行為 |
|---|---|---|
| `op` | `"llm"` | module dispatch |
| `id` | 字串或 null，可省 | null／未提供由 submit 產生 time_ns 名称；空字串也走自動產名 |
| `request` | 物件，實際必填 | 內嵌完整 LLM 請求，不是檔案路徑 |
| syscall 回應 | `{"ok":bool,"msg":str}` | 只代表排單結果，**不是模型結果** |

ID 通過 submit 時須符合 `[A-Za-z0-9._-]+`，不能為 `.`、`..` 或 `.tmp` 結尾。

module handle 先讀 endpoints、驗請求，再做同名檢查與 submit。**handle 不先 ensure LLM 家；kernel 順序又是 syscall 在 module.tick 前，因此首個 tick 尚未建家時，預先放入的 llm syscall 可先失敗，之後才建家。**

來源：[llm_cpu_module.py:13](../../../../proto4-5/llm_cpu_module.py)、[llm_cpu_module.py:37](../../../../proto4-5/llm_cpu_module.py)、[llm_cpu_request.py:15](../../../../proto4-5/llm_cpu_request.py)。

**LLM CLI 與 `--wait`**

```text
aos-kernel llm [K] REQ.json|- [--name NAME] [--wait SECS] [--json]
aos-kernel llm ls K
aos-kernel llm rm K NAME
```

| 項目 | 行為 |
|---|---|
| `REQ.json|-` | CLI 讀 JSON 檔或 stdin，嵌入 ticket |
| `--name` | 預設 `str(time.time_ns())` |
| `--wait SECS` | float 秒數；預設無；只拒絕 `<0`，沒有有限數檢查 |
| `--json` | 等結果後印完整結果 JSON；無 wait 時不改成印結果 |
| 第一期等待 | 新單無論有無 `--wait`，都等 syscall 回音；上限 `max(3秒,3×interval_ms/1000)` |
| 第二期等待 | `--wait` 才進入，從收到成功回音後另算 SECS，輪詢 result 檔 |
| 輪詢頻率 | 每 0.05 秒，monotonic |
| 是否推 tick | 不會 |
| 是否先檢 daemon/kernel PID | 不會；判斷依據是回音、檔案是否出現 |
| syscall 回音讀完 | unlink done 回音 |
| 第一期逾時 | 若原 syscall 還可 unlink，印「沒送出去，已撤單」；若已不存在，印「已送出，還沒做完」；退出 1 |
| 第二期逾時 | 不撤已送出的請求，印未完成與 result 路徑，退出 1 |
| 無 wait 成功 | 印結果路徑，退出 0 |
| 有 wait 成功結果 | 預設印 text＋路徑；`--json` 印 JSON＋路徑；退出 0 |
| 有 wait 失敗結果 | 印 error 或完整 JSON＋路徑；退出 1 |
| CLI 用法／讀輸入錯 | 2；`--help` 也被 SystemExit catch 轉成 2 |
| `llm ls` | 直接讀 LLM 家，可在 daemon 不活時使用 |
| `llm rm` | 直接刪 LLM 家資料；running 先 TERM worker group、等1秒，再 KILL、等1秒；不經 syscall |

第一期撤單不是交易式取消：kernel 可能已讀 request 但尚未刪原檔；CLI 判斷只是檔案是否還存在。

來源：[llm_cpu_module.py:98](../../../../proto4-5/llm_cpu_module.py)、[llm_cpu_module.py:174](../../../../proto4-5/llm_cpu_module.py)、[llm_cpu_module.py:233](../../../../proto4-5/llm_cpu_module.py)、[llm_cpu_manage.py:85](../../../../proto4-5/llm_cpu_manage.py)。

