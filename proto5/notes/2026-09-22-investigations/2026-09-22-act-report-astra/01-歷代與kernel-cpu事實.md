← [act 怎麼跑工具調查報告（astra）](../2026-09-22-act-report-astra.md)（分檔 1/2）｜[下一份](02-五個選項與拍板.md)

**1．歷代怎麼跑工具**

| 版本 | 工具長什麼樣、誰跑 | 同步／非同步與等待 | 逾時、失敗、輸出 | 已知限制／踩坑與來源 |
|---|---|---|---|---|
| **proto2** | `tools.json` 選工具包；包的 `run()` 是 Python 函式。自訂 `tools[]` 則是一句 shell command，參數 JSON 走 stdin。 | **一個 `act` 串行跑完全部 calls**，最後一次把整批 tool 訊息寫入 history。普通工具同步；`jobs`／`think`／`branch` 另有收據與背景工作機制。 | 包內例外包成 `{error:…}` 回模型。自訂 shell 同步 `subprocess.run`，合併 stdout／stderr，**沒有統一 timeout，也沒有把 returncode 統一編進結果**。`fs.sh` 自己有期限，見下表。 | 不是通用 thread／process pool。工具已做完、整批 history 尚未寫入時崩潰，可能重做。來源：[aos-agent:302](../../../../proto2/aos-agent)、[aos-agent:324](../../../../proto2/aos-agent)、[aos_agent.py:234](../../../../proto2/aos_agent.py)。 |
| **proto3** | 記憶體中的世界、agent、LLM queue；尚未接 proto2 工具包。 | LLM `ask` 先回 request id，clock 判 `wait-for`、結果透過信箱送回。Janet kernel 可每世界一個協作式 fiber。**agent 的 `act` 只是輸出回話，沒有模型工具執行器。** | LLM engine 是同步函式／假引擎；捕錯成結果，agent 記錯後回 idle。等待有 timeout，但不是 POSIX 工具 timeout。 | 不可拿這版證明真實工具已經非同步化。CL variant 雖每鐘有 thread，tick 求值受全域 mutex 串行保護。來源：[agent.janet:29](../../../../proto3/src/agent.janet)、[llm.janet:7](../../../../proto3/src/llm.janet)、[kernel.janet:38](../../../../proto3/src/kernel.janet)、[CL kernel:59](../../../../proto3/variant-cl/src/kernel.lisp)。 |
| **proto3-1** | 同樣是記憶體原型；世界改成可求值的 form。 | 等待變成純資料描述，例如 `[:llm-result id]`，搭配下一步 continuation。**仍未有真正的工具執行器。** | LLM queue、假引擎、結果信；timeout 回 idle。 | 演進重點是把等待／續跑表示成資料，不是新增背景工具能力。來源：[agent.janet:15](../../../../proto3-1/src/agent.janet)、[llm.janet:8](../../../../proto3-1/src/llm.janet)、[README:52](../../../../proto3-1/README.md)。 |
| **proto3-2** | `tools` 是「名字 → Janet 函式」的 table；模型回覆是簡化的 `{:tool 名 :args …}`。 | `think` 直接呼叫 engine；`act` **直接同步呼叫一支工具函式**。 | 找不到工具回文字；沒有工具 timeout、worker 或持久化收據。 | 檔頭明說之後接 LLM 世界才改非同步；clock／kernel／main 尚是空殼或偽碼。来源：[agent.janet:11](../../../../proto3-2/src/agent.janet)、[agent.janet:27](../../../../proto3-2/src/agent.janet)、[README:1](../../../../proto3-2/README.md)。 |
| **proto4-2** | 尚非 agent 工具層；`aos-cpu` 反覆執行 inst 描述的 POSIX 程式。 | 一顆 cpu 是一支常駐 Linux process；每次 `Popen` 後 `communicate()`，**等 child 結束才下一回合**。 | inst 的 `timeout_ms` 與整顆 cpu 的總期限取較早者；TERM group → 等 2 秒 → KILL。結果存 `last.json`／`runs.jsonl`，不是 tool 訊息。 | CPU 的最早形狀就容許格內阻塞；沒有自動切成可續跑步驟。來源：[aos_cpu.py:102](../../../../proto4-2/aos_cpu.py)、[aos_cpu.py:128](../../../../proto4-2/aos_cpu.py)、[aos_cpu.py:210](../../../../proto4-2/aos_cpu.py)。 |
| **proto4-3** | `aos-exec` 跑一次；`aos-run` 反覆跑；kernel 把行程 inst 排上 cpu。不是模型工具 adapter。 | `run_target()` 同步等 child。kernel 透過換 cpu 的 inst 檔决定**下一次**執行誰。 | 每次 timeout 預設 0＝不限；另可設整體硬期限。退出碼／kind 交給上層，沒有自動轉成 tool 訊息。 | quantum 是完成次數，不是格內搶佔期限；換檔不殺當次。來源：[aos_run.py:41](../../../../proto4-3/aos_run.py)、[kernel.md:114](../../../../proto4-3/docs/kernel.md)、[kernel.md:188](../../../../proto4-3/docs/kernel.md)。 |
| **proto4-4** | `aos-step` 每次跑一個 Janet 頂層 form；`aos/call` 包 POSIX 執行，Janet image 保存環境。 | form 裡的 `call`／直接 `aos/llm` 是同步。另可 `llm-submit` → 宣告 `wait-for` → 退出，下一次到檔才執行下一個 form。 | 格內失敗不推進；等待檔本身沒有 timeout。做完回 100、未到檔回 101。沒有自動產生模型 tool 訊息。 | 一個 form 仍可能做很久。「一格一個 form」不等於「一格很短」。image／pc／state 各自原子寫，但整組不是交易。來源：[step.janet:99](../../../../proto4-4/src/step.janet)、[step.janet:140](../../../../proto4-4/src/step.janet)、[aos.janet:195](../../../../proto4-4/src/aos.janet)。 |
| **proto4-5** | LLM 分兩層：同步 `aos-llm call`；排程器 `llm-cpu`，可獨立掛 cpu，也可作 kernel module。 | dispatcher tick 收件／排隊／派**背景 worker 子進程**，不等 HTTP；worker 同步問模型、寫結果檔。 | HTTP timeout；scheduler 另在期限＋5 秒後判 worker timeout。worker 死且無結果 → `worker_died`，**不自動重送**。失敗也產生 result。 | 有 request id＋內容 hash 冪等；但不是 exactly-once 執行協議，仍有 spawn／記 pid 交界。来源：[llm_cpu_tick.py:72](../../../../proto4-5/llm_cpu_tick.py)、[llm_cpu_tick.py:192](../../../../proto4-5/llm_cpu_tick.py)、[llm_cpu_worker.py:37](../../../../proto4-5/llm_cpu_worker.py)。 |
| **proto4-6** | JSON：每元素一份 inst；Python：每個公開 step 函式；Lua：return 表中的每個函式。 | 格內執行同步。`llm_submit` 回結果檔路徑，`wait_for` 宣告等待；後續未到檔就退 101，不跑下一格。 | JSON child 非零停原 pc；Python 函式成功且 state 能序列化才落盤。等待檔無 timeout；一般 call 可傳 timeout。沒有模型 tool 訊息 adapter。 | 最初等檔回 0，kernel 看不出在等；後來改 101 才能提早讓 cpu。来源：[step_common.py:74](../../../../proto4-6/step_common.py)、[aos_step_json.py:90](../../../../proto4-6/aos_step_json.py)、[aos_step_py.py:137](../../../../proto4-6/aos_step_py.py)、[演化 §23.8:72](../../../../proto4/notes/23-step-json-python.md)。 |
| **proto4-7** | `tools/<名>/tool.json` 宣告 schema；`tools/<名>/run` 真正執行。agent 經 `aos_py.call` → `aos-exec` 跑它。 | **`act` 一格串行跑完全部 calls**。LLM 才有 ask／wait 分格，工具沒有背景等待。 | 每工具 **60 秒**；成功 stdout；非零 `[exit N]`＋stderr 前 500 字＋stdout；整段預設截到 **8000 字元**。每 call 都回 tool 訊息。 | 壞 arguments JSON 不執行、回錯誤；不存在／啟動失敗也回 tool。全部跑完才保存，崩潰可重跑整批。來源：[agent_tools.py:105](../../../../proto4-7/agent_tools.py)、[state_machine.py:200](../../../../proto4-7/state_machine.py)。 |
| **proto5 規範＋目前工作樹** | 工具檔為 OpenAI tools 陣列，每元素 `_meta` 是 posix inst；import `aos_inst`／`aos_exec` 執行。 | **`act` 一格串行跑完全部 calls**。目前 `think` 也直接同步問模型；改 llm cpu 仍是規劃事項。 | arguments 字串原樣進 stdin；stdout 整段回來；目前 **工具不限時、沒有輸出截斷**。不存在／inst 壞／非零均變 tool 訊息，agent 正常回 0。 | 新增記憶尾巴自癒，能處理「history 已寫、state 未寫」，不能防止「工具做了、history 未寫」的重複副作用。來源：[規範:41](../../../spec/aos-agent/README.md)、[實作:159](../../../lib/aos_agent.py)、[實作:230](../../../lib/aos_agent.py)、[llm cpu 任務書:3](../2026-09-22-llm-cpu-plan-task.md)。 |

proto2 的兩條工具路徑值得獨立看，因為它已實際做過接近 D 的行為：

| proto2 路徑 | 啟動時 | 完成時 | 期限／限制 |
|---|---|---|---|
| **普通 `fs.sh`** | 同步 `Popen`＋`communicate`，占住當次 `act`。 | 真實 exit、stdout、stderr 組成正常 tool 結果。 | 預設 60 秒，最多 120 秒；逾時 KILL process group。工具描述明說超過一分鐘改 `run_long`。[fs.py:204](../../../../proto2/packs/fs.py) |
| **`jobs.run_long`** | 建獨立 job 資料夾、登記 daemon clock；立即回 `{ok,name,id,path}`，成為這次 call 的 tool 訊息，並設定 sleeping。 | job 寫結果；agent 後續 tick 收割，成功 hook 回一句「長工作完成」，包成新的 **user 訊息**。 | shell `timeout 3600`＋pending 牆鐘 3600 秒；開鐘失敗則撤掉 pending、回失敗。[jobs.py:69](../../../../proto2/packs/jobs.py)、[jobs.py:166](../../../../proto2/packs/jobs.py) |
| **`think`** | 丟旁線 LLM request，當格回收據；agent 可睡。 | `on_result` 累積步驟；未結束可再送下一請求，結束才回喚醒文字。 | 包自己有步數／token／時間等限制；不是 thread 裡維持整條思考鏈。[think.py:296](../../../../proto2/packs/think.py) |
| **`branch`** | 一次送多筆旁線 LLM request，立即回收據。 | 各自收結果，全齊後提示 join；實際並行度由 LLM engine 容量控制。 | 每筆 pending 有期限；不是 agent 內部 pool。[branch.py:195](../../../../proto2/packs/branch.py) |
| **一般測試工具** | `studio`／`pyshop` 仍可同步跑測試。 | 結果直接作 tool 回覆。 | 例如 studio 測試期限 60 秒。**歷史上並沒有把所有「可能很久」的工具都改成 async。**[studio.py:239](../../../../proto2/packs/studio.py) |

proto2 的 async 完成不是無條件追加 user 訊息：共用層先存 side result，再呼叫所屬 pack 的 `on_result`；**hook 有回文字才注入 user 訊息**。失敗通常清 sleeping、對外回錯，但不一定把錯誤再餵回主模型。這是已有實作的邊界。[aos_agent.py:1257](../../../../proto2/aos_agent.py)

實際 notes 留下的教訓：

| 記錄 | 與本題的關係 |
|---|---|
| proto2 前幾局死在「回 idle 後沒人叫醒」、睡眠互等、模型錯誤後停住；等待格又誤算動作上限。 | 把工作丟出去之後，還要有完整的**結果抵達 → 喚醒 → 繼續工作**路徑；背景執行本身只解一半。[lessons:7](../../../../proto2/notes/2026-09-07-lessons.md) |
| proto2 多進程共用檔，8 進程預期 160 筆；無鎖只剩 23 筆且 JSON 壞掉。 | 增加 pool／worker 會把共用狀態的寫入所有權變成實際問題。[lessons:37](../../../../proto2/notes/2026-09-07-lessons.md) |
| proto4-6 等待最初回 0，後改 101。 | 「不執行下一格」與「通知 kernel 讓位」原本是兩個不同步驟。[§23.7–23.8:59](../../../../proto4/notes/23-step-json-python.md) |
| `llm_submit` 即使不帶 `--wait`，仍須等 kernel 的 syscall 接單回音。 | submit 並不是完全零等待；它只是不等模型完成。[§23.7 落地記錄:70](../../../../proto4/notes/23-step-json-python.md) |
| proto4-7 真跑先遇到 LLM 層漏傳 `tools`，再遇 schema 不合而 HTTP 400、連錯進 stuck。 | 執行器正常也不代表模型工具鏈完整。記錄中的約 20 秒是整條對話，不是 `ls` 工具本身耗時。[§24.5:56](../../../../proto4/notes/24-agent.md) |
| 舊筆記已指出 `act` 藏著同步等待，並提出沿用 `llm_submit`＋`wait_for` 的想法。 | **那段標的是作者分析，不是使用者已拍板。**[§25.3:83](../../../../proto4/notes/24-agent.md) |

---

**2．kernel／cpu 模型的事實**

| 名詞 | proto4-3～4-7 的實際意思 | 對工具執行的影響 |
|---|---|---|
| **cpu** | daemon 管的一支常駐 `aos-run` Linux process，綁一個 inst.json 路徑；不是硬體核心。 | 一顆 cpu 可以被同步工具占住，即使實體 CPU 使用率很低。 |
| **行程／proc** | kernel 排程的 inst 檔＋外部狀態；每次被執行可能產生新的 Linux child。kernel 的 pid 是行程名稱，不等於當次 OS PID。 | `aos-agent` 每次退出後，要靠檔案保存下一格所需資訊。 |
| **cpu 的一次 run** | 讀當時的 inst、開 child、等 child 結束、回報 done。 | 一顆 cpu 的執行迴圈一次只等一個直接 child；child 自己仍可生更多子進程。 |
| **agent 的一格** | 一次 `aos-agent` 呼叫裡的一個狀態動作。 | 格內可以跑很多工具，也可以阻塞很久；「一格」沒有自帶時間上限。 |
| **kernel tick** | kernel 自己的一次呼叫：點 cpu → 處理 syscall → 跑 modules → 驗佇列 → 排程 → 存檔。 | kernel tick 與 agent tick 是不同呼叫，沒有保證一對一同步。 |
| **quantum** | `runs_now - runs_at`，預設 5；計算已完成的 cpu run 次數。 | **不是每 5 秒切走，也不是工具跑 5 秒就讓位。** |
| **0** | 這次有正常做事／一步成功；服務也可一直回 0。 | 不代表整個邏輯行程做完。 |
| **100** | kernel 預設 `done_exit`，表示邏輯行程完成；step 執行器做完後用它收工。 | kernel 收進 `procs/done/`；不是模型 tool 成功碼。 |
| **101** | kernel 預設 `wait_exit`；這次 child 已退出，告知「我在等」。 | 有其他行程排隊就換到隊尾；沒人排隊仍可留在 cpu 上反覆輪詢。 |
| **`wait_for`** | step 執行器自己的「等待某檔存在」記錄。 | kernel 不知道它在等哪個檔；kernel 只看到 101。 |
| **module** | kernel 載入的 Python 檔，直接呼叫其 hook。 | module 不是自動隔離的另一顆 cpu；hook 若阻塞，會拖住 kernel tick。 |

依據：[kernel 文件:6](../../../../proto4-3/docs/kernel.md)、[run_loop:41](../../../../proto4-3/aos_run.py)、[tick:41](../../../../proto4-3/aos_kernel_tick.py)、[schedule:26](../../../../proto4-3/aos_kernel_schedule.py)、[module:53](../../../../proto4-3/aos_kernel_module.py)。

具體接法如下：

```text
daemon
  ├─ kernel 自己的 aos-run → 每次執行 aos-kernel-tick
  │                           ├─ 處理 syscall
  │                           ├─ 呼叫 llm module 的短 tick
  │                           └─ 修改 cpus/N.json，決定下一次跑誰
  │
  ├─ cpu 0：aos-run → 讀 cpus/0.json → 執行 agent／step → 等退出
  └─ cpu 1：aos-run → 讀 cpus/1.json → 執行另一個行程 → 等退出

llm module 的 tick
  └─ 開背景 worker → worker 同步問模型 → 寫 results/<id>.json

agent／step
  └─ 下次被執行時看結果檔；沒到就退 101
```

因此，「像 llm cpu」還有兩種具體形狀：

| 形狀 | 事實 |
|---|---|
| **獨立 llm-cpu 行程掛普通 cpu** | 有一顆 cpu 反覆叫 dispatcher tick。 |
| **llm 排程器作 kernel module** | dispatcher tick 直接在 kernel tick 內跑；**真正耗時的是另外開的 worker**，不是一定額外占一顆 aos cpu。 |

LLM module 能保持 kernel 短，是因為它派出 worker 後返回，並非「module」這個機制自動保證非阻塞。[llm_cpu_tick.py:192](../../../../proto4-5/llm_cpu_tick.py)

`wait_for` 與 101 的順序也要分清：

| 時點 | step 執行器做什麼 |
|---|---|
| 本格宣告 `wait_for(path)` | **本格算成功、pc 已前進**，把 waiting 存下來，回 0。 |
| 下一次執行，檔還沒到 | 增加 checks，回 101，不執行下一格。 |
| 檔到了 | 清 waiting，**同一次呼叫繼續下一格**；那一格自行讀結果。 |

這套沒有等待 timeout、沒有主動檔案事件喚醒，仍靠輪詢。[step_common.py:74](../../../../proto4-6/step_common.py)、[step_common.py:102](../../../../proto4-6/step_common.py)

「一個行程阻塞」的影響：

| 阻塞位置 | 直接影響 | 不會自動發生的事 |
|---|---|---|
| agent 格內同步工具 | 這次 agent 不退出；承載它的 cpu 不能开始下一次 run。 | quantum 不會在格內把工具暫停並保存 continuation。 |
| 同一顆 cpu 的其他排隊行程 | 要等當次 child 結束，才有機會真正開始。 | rename 成新 inst 不會立刻執行新人。 |
| 其他 cpu 上的行程 | 沒有上述直接等待關係，可以繼續。 | 不代表完全不受實體 CPU、記憶體、磁碟或共用鎖競爭影響。 |
| kernel module 的 hook | 該 kernel tick 後面的 module／排程都被延後。 | catch exception 不能解決「一直不返回」。 |
| LLM 背景 worker | 占 endpoint 容量；呼叫者等 result。 | 正常不會占住 kernel tick。 |

還有一個與長 `act` 直接相關的**靜態推論，未實測**：

> 單顆 cpu 一次只執行一個 child，**不等於同一個邏輯行程絕不會跨 cpu 重疊執行**。

daemon 有 `running` 欄位，但 kernel 的 `poll_cpus`／排程沒有用它阻止換檔。若 cpu0 已完成足夠 runs、又開始舊行程下一格，kernel 此時依先前 runs 換人，會立刻把舊行程排回 queue；cpu1 可能接走它，而 cpu0 的舊 child 尚未結束。這會碰到 agent「同一資料夾不要同時跑兩份、沒有鎖」的前提。[daemon 狀態:75](../../../../proto4-3/aos_daemon_entry.py)、[poll_cpus:81](../../../../proto4-3/aos_kernel_tick.py)、[換人與回佇列:111](../../../../proto4-3/aos_kernel_schedule.py)

這是沿用舊 kernel 時需要看見的限制，不能用「排程器已有」帶過。

使用者方向草稿的原話：

| 來源 | 原話 | 能確認的意思 |
|---|---|---|
| [thinking/aos-agent.md:13](../../../../thinking/aos-agent.md) | 「跟aos kernel說，unregister這個資料夾。」「跟pause不一樣，pause那個，是仍registering，但狀態機不動。」 | stop 與 pause 不同。 |
| [thinking/aos-agent.md:17](../../../../thinking/aos-agent.md) | 「daemon的cpu仍然會持續執行，但是agent的狀態機不會前進。」 | agent 暫停不等於停掉 cpu。 |
| 同上，19 行 | 「交給外部cpu跑的東西，回來的結果也是會存，但agent不會反應」 | 外部工作與 agent 反應可以有不同生命週期。 |
| 同上，20 行 | 「shell跑的東西，會跑完，但agent不會反應」 | pause 的方向是暫停狀態機反應，並未要求砍掉手上 shell。 |
| [thinking/aos-user.md:14](../../../../thinking/aos-user.md) | 「持續監看(每秒poll一次)本地agent資料夾的回覆檔，那個檔案有新東西，就顯示到畫面上。」 | 人端 listen 採輪詢；不是工具執行方式的決定。 |

`thinking/` 四份檔已掃過；沒有找到直接選定 thread、async 工具或阻塞期限的文字。`aos-tools.md` 只有標題。

另外兩段歷史原話提供背景，但不能擴張成此次決定：

- daemon 實作時，你曾確認：「**就是子進程，這樣省事。反正 import 之後還是得開 thread 跑，那樣反而失去了讓 linux 管理進程的方便性。**」這是在選 daemon 如何承載 `aos-run`，不是對所有工具一律禁用 thread。[原文:131](../../../../proto4/notes/11-15-exec-run-daemon.md)
- LLM cpu 的定義：「**收到很多個 llm 呼叫請求，然後做排序，分發給不同 endpoint 那樣，整圈推論工具執行那是 agent 的事情。**」這支持排程層與 agent 層分工，但尚未決定 tool cpu。[原文:5](../../../../proto4/notes/22-llm-cpu.md)

---

