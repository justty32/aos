目前的事實是：**proto2、proto4-7，以及 proto5 目前工作樹裡的實作，普通工具都是在 `act` 一格內串行跑完全部 `tool_calls`。但這是執行方式的選擇，不是 tool 訊息契約迫使它同步阻塞。**

真正需要分開看的有三件事：

| 問題 | 可以怎麼選 |
|---|---|
| 工具在哪裡跑？ | agent 呼叫的子進程、另一顆 cpu、背景 worker、thread／process pool |
| agent 是否占住目前這顆 cpu 等待？ | 留在這次呼叫裡等；或存檔、退 101，下次再接結果 |
| 模型收到的是什麼？ | 真正的工具結果；或先收「已接單」收據，完成後另收一則輸入 |

**B 和 D 因此不是同一件事：B 讓出 cpu，但這輪對話仍等工具結果；D 先用收據完成 tool call，讓模型可以繼續。兩者可以共用同一套背景執行器。**

全程唯讀，沒有修改檔案、執行測試或啟動服務。以下「程式事實」來自靜態閱讀；崩潰窗口與排程競態另標為推論，沒有冒充實測結果。

另外，調查時工作樹已有未提交的 `proto5/lib/aos_agent.py`、`cli/aos-agent`，以及 `aos_exec.py`／`aos_inst.py` 修改；README 仍寫「程式還沒寫」。以下同時列出**規範**與**目前工作樹實作**，不把它們當成已發布的穩定版。

---

**1．歷代怎麼跑工具**

| 版本 | 工具長什麼樣、誰跑 | 同步／非同步與等待 | 逾時、失敗、輸出 | 已知限制／踩坑與來源 |
|---|---|---|---|---|
| **proto2** | `tools.json` 選工具包；包的 `run()` 是 Python 函式。自訂 `tools[]` 則是一句 shell command，參數 JSON 走 stdin。 | **一個 `act` 串行跑完全部 calls**，最後一次把整批 tool 訊息寫入 history。普通工具同步；`jobs`／`think`／`branch` 另有收據與背景工作機制。 | 包內例外包成 `{error:…}` 回模型。自訂 shell 同步 `subprocess.run`，合併 stdout／stderr，**沒有統一 timeout，也沒有把 returncode 統一編進結果**。`fs.sh` 自己有期限，見下表。 | 不是通用 thread／process pool。工具已做完、整批 history 尚未寫入時崩潰，可能重做。來源：[aos-agent:302](../../proto2/aos-agent)、[aos-agent:324](../../proto2/aos-agent)、[aos_agent.py:234](../../proto2/aos_agent.py)。 |
| **proto3** | 記憶體中的世界、agent、LLM queue；尚未接 proto2 工具包。 | LLM `ask` 先回 request id，clock 判 `wait-for`、結果透過信箱送回。Janet kernel 可每世界一個協作式 fiber。**agent 的 `act` 只是輸出回話，沒有模型工具執行器。** | LLM engine 是同步函式／假引擎；捕錯成結果，agent 記錯後回 idle。等待有 timeout，但不是 POSIX 工具 timeout。 | 不可拿這版證明真實工具已經非同步化。CL variant 雖每鐘有 thread，tick 求值受全域 mutex 串行保護。來源：[agent.janet:29](../../proto3/src/agent.janet)、[llm.janet:7](../../proto3/src/llm.janet)、[kernel.janet:38](../../proto3/src/kernel.janet)、[CL kernel:59](../../proto3/variant-cl/src/kernel.lisp)。 |
| **proto3-1** | 同樣是記憶體原型；世界改成可求值的 form。 | 等待變成純資料描述，例如 `[:llm-result id]`，搭配下一步 continuation。**仍未有真正的工具執行器。** | LLM queue、假引擎、結果信；timeout 回 idle。 | 演進重點是把等待／續跑表示成資料，不是新增背景工具能力。來源：[agent.janet:15](../../proto3-1/src/agent.janet)、[llm.janet:8](../../proto3-1/src/llm.janet)、[README:52](../../proto3-1/README.md)。 |
| **proto3-2** | `tools` 是「名字 → Janet 函式」的 table；模型回覆是簡化的 `{:tool 名 :args …}`。 | `think` 直接呼叫 engine；`act` **直接同步呼叫一支工具函式**。 | 找不到工具回文字；沒有工具 timeout、worker 或持久化收據。 | 檔頭明說之後接 LLM 世界才改非同步；clock／kernel／main 尚是空殼或偽碼。来源：[agent.janet:11](../../proto3-2/src/agent.janet)、[agent.janet:27](../../proto3-2/src/agent.janet)、[README:1](../../proto3-2/README.md)。 |
| **proto4-2** | 尚非 agent 工具層；`aos-cpu` 反覆執行 inst 描述的 POSIX 程式。 | 一顆 cpu 是一支常駐 Linux process；每次 `Popen` 後 `communicate()`，**等 child 結束才下一回合**。 | inst 的 `timeout_ms` 與整顆 cpu 的總期限取較早者；TERM group → 等 2 秒 → KILL。結果存 `last.json`／`runs.jsonl`，不是 tool 訊息。 | CPU 的最早形狀就容許格內阻塞；沒有自動切成可續跑步驟。來源：[aos_cpu.py:102](../../proto4-2/aos_cpu.py)、[aos_cpu.py:128](../../proto4-2/aos_cpu.py)、[aos_cpu.py:210](../../proto4-2/aos_cpu.py)。 |
| **proto4-3** | `aos-exec` 跑一次；`aos-run` 反覆跑；kernel 把行程 inst 排上 cpu。不是模型工具 adapter。 | `run_target()` 同步等 child。kernel 透過換 cpu 的 inst 檔决定**下一次**執行誰。 | 每次 timeout 預設 0＝不限；另可設整體硬期限。退出碼／kind 交給上層，沒有自動轉成 tool 訊息。 | quantum 是完成次數，不是格內搶佔期限；換檔不殺當次。來源：[aos_run.py:41](../../proto4-3/aos_run.py)、[kernel.md:114](../../proto4-3/docs/kernel.md)、[kernel.md:188](../../proto4-3/docs/kernel.md)。 |
| **proto4-4** | `aos-step` 每次跑一個 Janet 頂層 form；`aos/call` 包 POSIX 執行，Janet image 保存環境。 | form 裡的 `call`／直接 `aos/llm` 是同步。另可 `llm-submit` → 宣告 `wait-for` → 退出，下一次到檔才執行下一個 form。 | 格內失敗不推進；等待檔本身沒有 timeout。做完回 100、未到檔回 101。沒有自動產生模型 tool 訊息。 | 一個 form 仍可能做很久。「一格一個 form」不等於「一格很短」。image／pc／state 各自原子寫，但整組不是交易。來源：[step.janet:99](../../proto4-4/src/step.janet)、[step.janet:140](../../proto4-4/src/step.janet)、[aos.janet:195](../../proto4-4/src/aos.janet)。 |
| **proto4-5** | LLM 分兩層：同步 `aos-llm call`；排程器 `llm-cpu`，可獨立掛 cpu，也可作 kernel module。 | dispatcher tick 收件／排隊／派**背景 worker 子進程**，不等 HTTP；worker 同步問模型、寫結果檔。 | HTTP timeout；scheduler 另在期限＋5 秒後判 worker timeout。worker 死且無結果 → `worker_died`，**不自動重送**。失敗也產生 result。 | 有 request id＋內容 hash 冪等；但不是 exactly-once 執行協議，仍有 spawn／記 pid 交界。来源：[llm_cpu_tick.py:72](../../proto4-5/llm_cpu_tick.py)、[llm_cpu_tick.py:192](../../proto4-5/llm_cpu_tick.py)、[llm_cpu_worker.py:37](../../proto4-5/llm_cpu_worker.py)。 |
| **proto4-6** | JSON：每元素一份 inst；Python：每個公開 step 函式；Lua：return 表中的每個函式。 | 格內執行同步。`llm_submit` 回結果檔路徑，`wait_for` 宣告等待；後續未到檔就退 101，不跑下一格。 | JSON child 非零停原 pc；Python 函式成功且 state 能序列化才落盤。等待檔無 timeout；一般 call 可傳 timeout。沒有模型 tool 訊息 adapter。 | 最初等檔回 0，kernel 看不出在等；後來改 101 才能提早讓 cpu。来源：[step_common.py:74](../../proto4-6/step_common.py)、[aos_step_json.py:90](../../proto4-6/aos_step_json.py)、[aos_step_py.py:137](../../proto4-6/aos_step_py.py)、[演化 §23.8:72](../../proto4/notes/23-step-json-python.md)。 |
| **proto4-7** | `tools/<名>/tool.json` 宣告 schema；`tools/<名>/run` 真正執行。agent 經 `aos_py.call` → `aos-exec` 跑它。 | **`act` 一格串行跑完全部 calls**。LLM 才有 ask／wait 分格，工具沒有背景等待。 | 每工具 **60 秒**；成功 stdout；非零 `[exit N]`＋stderr 前 500 字＋stdout；整段預設截到 **8000 字元**。每 call 都回 tool 訊息。 | 壞 arguments JSON 不執行、回錯誤；不存在／啟動失敗也回 tool。全部跑完才保存，崩潰可重跑整批。來源：[agent_tools.py:105](../../proto4-7/agent_tools.py)、[state_machine.py:200](../../proto4-7/state_machine.py)。 |
| **proto5 規範＋目前工作樹** | 工具檔為 OpenAI tools 陣列，每元素 `_meta` 是 posix inst；import `aos_inst`／`aos_exec` 執行。 | **`act` 一格串行跑完全部 calls**。目前 `think` 也直接同步問模型；改 llm cpu 仍是規劃事項。 | arguments 字串原樣進 stdin；stdout 整段回來；目前 **工具不限時、沒有輸出截斷**。不存在／inst 壞／非零均變 tool 訊息，agent 正常回 0。 | 新增記憶尾巴自癒，能處理「history 已寫、state 未寫」，不能防止「工具做了、history 未寫」的重複副作用。來源：[規範:41](../spec/aos-agent.md:41)、[實作:159](../lib/aos_agent.py)、[實作:230](../lib/aos_agent.py)、[llm cpu 任務書:3](2026-09-22-llm-cpu-plan-task.md)。 |

proto2 的兩條工具路徑值得獨立看，因為它已實際做過接近 D 的行為：

| proto2 路徑 | 啟動時 | 完成時 | 期限／限制 |
|---|---|---|---|
| **普通 `fs.sh`** | 同步 `Popen`＋`communicate`，占住當次 `act`。 | 真實 exit、stdout、stderr 組成正常 tool 結果。 | 預設 60 秒，最多 120 秒；逾時 KILL process group。工具描述明說超過一分鐘改 `run_long`。[fs.py:204](../../proto2/packs/fs.py) |
| **`jobs.run_long`** | 建獨立 job 資料夾、登記 daemon clock；立即回 `{ok,name,id,path}`，成為這次 call 的 tool 訊息，並設定 sleeping。 | job 寫結果；agent 後續 tick 收割，成功 hook 回一句「長工作完成」，包成新的 **user 訊息**。 | shell `timeout 3600`＋pending 牆鐘 3600 秒；開鐘失敗則撤掉 pending、回失敗。[jobs.py:69](../../proto2/packs/jobs.py)、[jobs.py:166](../../proto2/packs/jobs.py) |
| **`think`** | 丟旁線 LLM request，當格回收據；agent 可睡。 | `on_result` 累積步驟；未結束可再送下一請求，結束才回喚醒文字。 | 包自己有步數／token／時間等限制；不是 thread 裡維持整條思考鏈。[think.py:296](../../proto2/packs/think.py) |
| **`branch`** | 一次送多筆旁線 LLM request，立即回收據。 | 各自收結果，全齊後提示 join；實際並行度由 LLM engine 容量控制。 | 每筆 pending 有期限；不是 agent 內部 pool。[branch.py:195](../../proto2/packs/branch.py) |
| **一般測試工具** | `studio`／`pyshop` 仍可同步跑測試。 | 結果直接作 tool 回覆。 | 例如 studio 測試期限 60 秒。**歷史上並沒有把所有「可能很久」的工具都改成 async。**[studio.py:239](../../proto2/packs/studio.py) |

proto2 的 async 完成不是無條件追加 user 訊息：共用層先存 side result，再呼叫所屬 pack 的 `on_result`；**hook 有回文字才注入 user 訊息**。失敗通常清 sleeping、對外回錯，但不一定把錯誤再餵回主模型。這是已有實作的邊界。[aos_agent.py:1257](../../proto2/aos_agent.py)

實際 notes 留下的教訓：

| 記錄 | 與本題的關係 |
|---|---|
| proto2 前幾局死在「回 idle 後沒人叫醒」、睡眠互等、模型錯誤後停住；等待格又誤算動作上限。 | 把工作丟出去之後，還要有完整的**結果抵達 → 喚醒 → 繼續工作**路徑；背景執行本身只解一半。[lessons:7](../../proto2/notes/2026-09-07-lessons.md) |
| proto2 多進程共用檔，8 進程預期 160 筆；無鎖只剩 23 筆且 JSON 壞掉。 | 增加 pool／worker 會把共用狀態的寫入所有權變成實際問題。[lessons:37](../../proto2/notes/2026-09-07-lessons.md) |
| proto4-6 等待最初回 0，後改 101。 | 「不執行下一格」與「通知 kernel 讓位」原本是兩個不同步驟。[§23.7–23.8:59](../../proto4/notes/23-step-json-python.md) |
| `llm_submit` 即使不帶 `--wait`，仍須等 kernel 的 syscall 接單回音。 | submit 並不是完全零等待；它只是不等模型完成。[§23.7 落地記錄:70](../../proto4/notes/23-step-json-python.md) |
| proto4-7 真跑先遇到 LLM 層漏傳 `tools`，再遇 schema 不合而 HTTP 400、連錯進 stuck。 | 執行器正常也不代表模型工具鏈完整。記錄中的約 20 秒是整條對話，不是 `ls` 工具本身耗時。[§24.5:56](../../proto4/notes/24-agent.md) |
| 舊筆記已指出 `act` 藏著同步等待，並提出沿用 `llm_submit`＋`wait_for` 的想法。 | **那段標的是作者分析，不是使用者已拍板。**[§25.3:83](../../proto4/notes/24-agent.md) |

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

依據：[kernel 文件:6](../../proto4-3/docs/kernel.md)、[run_loop:41](../../proto4-3/aos_run.py)、[tick:41](../../proto4-3/aos_kernel_tick.py)、[schedule:26](../../proto4-3/aos_kernel_schedule.py)、[module:53](../../proto4-3/aos_kernel_module.py)。

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

LLM module 能保持 kernel 短，是因為它派出 worker 後返回，並非「module」這個機制自動保證非阻塞。[llm_cpu_tick.py:192](../../proto4-5/llm_cpu_tick.py)

`wait_for` 與 101 的順序也要分清：

| 時點 | step 執行器做什麼 |
|---|---|
| 本格宣告 `wait_for(path)` | **本格算成功、pc 已前進**，把 waiting 存下來，回 0。 |
| 下一次執行，檔還沒到 | 增加 checks，回 101，不執行下一格。 |
| 檔到了 | 清 waiting，**同一次呼叫繼續下一格**；那一格自行讀結果。 |

這套沒有等待 timeout、沒有主動檔案事件喚醒，仍靠輪詢。[step_common.py:74](../../proto4-6/step_common.py)、[step_common.py:102](../../proto4-6/step_common.py)

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

daemon 有 `running` 欄位，但 kernel 的 `poll_cpus`／排程沒有用它阻止換檔。若 cpu0 已完成足夠 runs、又開始舊行程下一格，kernel 此時依先前 runs 換人，會立刻把舊行程排回 queue；cpu1 可能接走它，而 cpu0 的舊 child 尚未結束。這會碰到 agent「同一資料夾不要同時跑兩份、沒有鎖」的前提。[daemon 狀態:75](../../proto4-3/aos_daemon_entry.py)、[poll_cpus:81](../../proto4-3/aos_kernel_tick.py)、[換人與回佇列:111](../../proto4-3/aos_kernel_schedule.py)

這是沿用舊 kernel 時需要看見的限制，不能用「排程器已有」帶過。

使用者方向草稿的原話：

| 來源 | 原話 | 能確認的意思 |
|---|---|---|
| [thinking/aos-agent.md:13](../../thinking/aos-agent.md) | 「跟aos kernel說，unregister這個資料夾。」「跟pause不一樣，pause那個，是仍registering，但狀態機不動。」 | stop 與 pause 不同。 |
| [thinking/aos-agent.md:17](../../thinking/aos-agent.md) | 「daemon的cpu仍然會持續執行，但是agent的狀態機不會前進。」 | agent 暫停不等於停掉 cpu。 |
| 同上，19 行 | 「交給外部cpu跑的東西，回來的結果也是會存，但agent不會反應」 | 外部工作與 agent 反應可以有不同生命週期。 |
| 同上，20 行 | 「shell跑的東西，會跑完，但agent不會反應」 | pause 的方向是暫停狀態機反應，並未要求砍掉手上 shell。 |
| [thinking/aos-user.md:14](../../thinking/aos-user.md) | 「持續監看(每秒poll一次)本地agent資料夾的回覆檔，那個檔案有新東西，就顯示到畫面上。」 | 人端 listen 採輪詢；不是工具執行方式的決定。 |

`thinking/` 四份檔已掃過；沒有找到直接選定 thread、async 工具或阻塞期限的文字。`aos-tools.md` 只有標題。

另外兩段歷史原話提供背景，但不能擴張成此次決定：

- daemon 實作時，你曾確認：「**就是子進程，這樣省事。反正 import 之後還是得開 thread 跑，那樣反而失去了讓 linux 管理進程的方便性。**」這是在選 daemon 如何承載 `aos-run`，不是對所有工具一律禁用 thread。[原文:131](../../proto4/notes/11-15-exec-run-daemon.md)
- LLM cpu 的定義：「**收到很多個 llm 呼叫請求，然後做排序，分發給不同 endpoint 那樣，整圈推論工具執行那是 agent 的事情。**」這支持排程層與 agent 層分工，但尚未決定 tool cpu。[原文:5](../../proto4/notes/22-llm-cpu.md)

---

**3．proto5 `act` 的五個選項**

先把目前能接的零件列清楚：

| 零件 | 目前契約 | 對方案的約束 |
|---|---|---|
| `state` | `idle`／`think`／`act`；沒有 wait 狀態。 | B 不一定要新增第四態，可以讓 `act` 具有送出／收回兩階段，但要另存 pending 資訊。 |
| `input` | 字串→user；訊息物件／陣列原樣接。**目前只在 idle 收。** | 結果檔放進 input 不代表 act／think 會立即接到它。 |
| `waits` | 走格前的門；未到退 101。agent 目前**只劃不加**。 | B 若由 agent 自己登記結果等待，就要修改「只劃不加」這條契約。 |
| `.done` | input／consume 已處理檔的 rename。 | 表示「已被消費」，不表示工具執行成功，也不自帶去重保證。 |
| 寫檔 | 個別檔 `.tmp`→rename；history 先、state 後。 | 防半份 JSON，不保證跨檔交易或外部副作用只做一次。 |
| 工具 `_meta` | 完整 posix inst；stdin／stdout 不准自訂，由 agent 接管。 | 執行位置／async 標籤還沒有正式欄位。 |
| `run_target` | 同步執行；`on_spawn(Popen)`／結束後 `on_spawn(None)`；可 timeout。 | `on_spawn` 是持有 child、供控制用的鉤子，**不是非同步 API**。 |
| 新 `run_inst` | 記憶體 inst＋stdin 字串→`code,kind,stdout`；也是同步。 | 目前沒有公開 `on_spawn` 參數，agent 呼叫沒有傳 timeout。 |

來源：[agent.md:75](../spec/agent.md:75)、[aos-agent.md:22](../spec/aos-agent.md:22)、[工具格式:82](../../proto5.1/spec/aos-llm-ask.md)、[run_target:45](../lib/aos_exec.py)、[run_inst:87](../lib/aos_exec.py)。

`waits` 的五個選項各自只做這些事：

| 選項 | 判斷／動作 |
|---|---|
| `exists` | 預設；檔存在，或資料夾內有 `*.json`。 |
| `mtime` | 修改時間大於 `since`；與 exists 互斥。 |
| `consume` | 到了後 rename `.done`；不改變到達判斷。 |
| `any` | **同一條**裡任一個路徑到達即可。 |
| `all` | 預設；同一條裡全部路徑到達。 |

多條 waits 要全部清空，整道門才開。**如果結果還要讀，該條不能先 consume，否則門先把它 rename 掉，收結果的程式便找不到原路徑。**[agent.md:110](../spec/agent.md:110)

OpenAI 的 function-calling 文件示例是：保存 assistant 的 calls，逐 call 用相同 `tool_call_id` 回 tool 訊息，再送下一次請求。它描述的是訊息配對，沒有要求本機必須用同一個 thread 同步執行。[官方 Function calling](https://developers.openai.com/api/docs/guides/function-calling)

本 repo 又明確選定 **tool 訊息按原 `tool_calls` 順序接回**。以下方案都保留這條。

| 選項 | 跟 state／waits／input／101 的接法 | 模型看到的訊息 | 好處 | 代價與適用條件 |
|---|---|---|---|---|
| **A．現狀：一格同步跑完** | `act` 呼叫所有工具；完成後整批寫 history，state→think，回 0。工具執行期間沒有 101。 | 每 call 一則真正結果／錯誤，順序天然一致。 | 最少狀態、最容易追讀；有先後副作用的工具自然串行。 | 整批時間相加，占住 cpu；中途不能處理新 input；任何一支不返回，整批不完成。適合能接受格內等待的工作。 |
| **B．交 tool cpu，結果仍作 tool 訊息** | `act` 保存批次及 call 對應、寫請求、登記結果 waits；保留 act。未齊退 101；門開後讀結果、按順序整批接 history，再 think。input 可先留著。 | 每 call 最終仍是真正 tool 結果；本輪模型在結果齊前不再推進。 | agent 的 cpu 可讓給其他行程；長工具可由獨立容量／排隊策略管理；模型語意接近 A。 | 要請求生命週期、pending、收結果與失聯處理；多一段排隊／輪詢延遲。適合需要真結果才能繼續，但不想占住 agent cpu 的工具。 |
| **C．agent 內 thread／process pool** | 若池內並行、最後仍 join，state 流程同 A，**沒有讓出 aos cpu**。若想啟動後就退出，必須另做持久化 worker／結果檔，開始接近 B 或 D。 | join 後按 call index 重排結果，再整批接 tool 訊息。 | 對互相獨立的多工具，可縮短整批牆鐘時間；不用先建中央 tool 排程器。 | 有競爭、取消、pool 壽命問題；不解決單一長工具占住本格。必須另判哪些工具可同時執行。 |
| **D．§5 async：收據＋後續 input** | `act` 提交工作，立即把收據作 tool 結果；整批 calls 都補齊後→think。背景工作完成後寫 input，日後 idle 收進來。通常不用 waits 擋住整個 agent。 | 這次 tool 結果是「已接單／啟動失敗」；真正完成是後來新的 user 訊息。 | 模型可以先回話、安排其他工作；長背景任務不把當前 tool-call 鏈一直懸著。proto2 有先例。 | 改變對話語意；必須分清接單與成功、追蹤 job id、通知失敗；目前 input 只在 idle 收，可能延後很久。 |
| **E．依工具標籤混合** | 每 call 依策略走 A／B／D，C 可作局部執行方式；批次需要統一協調。 | sync／cpu call 收真結果；async call 收收據；仍須把本批所有 tool 回覆補齊，才能繼續問模型。 | 各工具可選合適行為，短操作不必全部經排程器。 | 規則與恢復狀態最多；同批有一支 B，就仍要等它，其他 async 收據不會自動讓整輪模型提前繼續。 |

其中 **C 要拆成兩種完全不同的承諾**：

| C 的含義 | 能不能讓出 cpu？ | 原因 |
|---|---|---|
| 工具並行跑，但這次 `aos-agent` 等它們全完 | **不能** | `aos-run` 仍在等這次 agent child 退出；只是可能把總耗時由相加縮成接近最慢者。 |
| 開 thread，main 返回，期待 thread 繼續送結果 | 不能直接這樣成立 | 非 daemon thread 會延長 process 壽命；daemon thread 不保證在 interpreter 結束後繼續工作。 |
| 開獨立 worker 子進程，agent 退出 | **可以** | 但 worker 必須獨立持有工作、結果與錯誤回報；這已是 B／D 所需的跨呼叫協議。 |
| 把 `aos-agent` 改成常駐、有固定 pool | 可以另設事件迴圈 | 但改的是目前「叫一次、走一格、退出」的生命週期，範圍比增加一個工具選項大。 |

此外，**目前工具本來就是子進程**：import `aos_exec` 只是省掉一層 `aos-exec` CLI，不是把 shell 工具搬進 Python 主進程。再說「開子進程」本身並沒有回答要不要同步等待。

目前新實作的 `_tool_result` 使用 `contextlib.redirect_stderr` 捕捉執行器錯誤；它改的是 process 內共用的 `sys.stderr`。若把這個函式原封不動丟進多個 thread，錯誤擷取就有互相干擾的風險，不能只在外面包一個 pool。[aos_agent.py:173](../lib/aos_agent.py)

五個方案如何處理中途崩潰、逾時：

| 選項 | 中途崩潰／自癒 | 逾時放哪層 | 複雜度 |
|---|---|---|---|
| **A** | history 已寫、state 未寫：目前看尾巴可跳過重做。**工具已執行、history 未寫：重跑整批，可能重複副作用。**要再加保障，就需逐 call 執行記錄／可重用結果／工具冪等。 | 單工具期限可交 `run_inst(timeout_ms)`；整格外層 timeout 只能作額外界線，不能取代逐工具失敗回覆。 | 最低；提高恢復保障後會增加。 |
| **B** | 需保存穩定 request id、batch／call 對應與提交狀態；重進 act 先對帳，避免重送。worker 死且結果不明，可像舊 LLM 回 `worker_died`，或只重試明確可重入工具。 | tool worker 管執行期限；dispatcher 管 worker 失聯；排隊期限與 agent 等待期限另分開。**失敗也要寫終局結果，讓門能開。** | 中高；主要成本是持久化生命週期。 |
| **C** | 若仍整批 join，崩潰問題與 A 一樣，且可能已有多支工具同時產生副作用。若 worker 留在背景，還需 B 的對帳。 | 每工具 child 期限；pool 等待超時並不等於工具 child 已被終止。要能定位並收掉對應 group。 | 並行 join 是中等；要跨格存活则接近 B。 |
| **D** | 「工作已接單、收據未存 history」會重送；「完成訊息已接 history、input 未 rename」會重複通知。需要 job id、提交去重、完成訊息去重。 | 執行期限在 worker；失聯／取消／逾時都要有後續完成通知。收據不能冒充成功結果。 | 中高；另有對話與喚醒語意。 |
| **E** | 同批混合實際結果與收據，需逐 call 記狀態；重進後分辨哪些已提交、完成、已接 history。 | 依執行 backend 分層，再統一成可預期的結果／通知。 | 最高，測試組合也最多。 |

幾個共同的恢復缺口，不能把它們算成某個方案天然解決：

| 邊界 | 現況／後果 | 若要補，需要什麼 |
|---|---|---|
| **部分 tool 結果已接 history** | 目前自癒只看「尾巴是不是帶 calls 的 assistant」。若 B 改成逐筆追加，尾巴成了 tool，舊判斷可能以為整批已做完。 | 結果先存 history 外，齊了再整批接；或改成檢查整批 call id 的完整性。 |
| **結果檔存在** | `exists` 只說檔在，不代表成功、格式合法、屬於本輪。 | 每筆唯一 id、原子發布完整結果；讀取時驗身份與內容。 |
| **`consume` 後尚未存 waits 就崩** | 檔已變 `.done`，原 waits 還在；下次可能等一個已被自己搬走的檔。 | 需可對帳的消費記錄／恢復流程；單次 rename 不是整批交易。 |
| **history 存了，input 尚未 `.done`** | 重啟可再次收同一輸入。 | 訊息 id／已接收記錄，或其他可恢復的消費協議。 |
| **多個 worker 寫同一 `input.json`** | 原子 replace 只防半檔，仍可互相覆蓋。 | 例如一工作一訊息檔；即使如此，跨檔接收去重仍需處理。 |
| **工具副作用完成，結果未落盤** | A～E 都可能不知道到底做成沒有。 | 工具端冪等鍵、查詢已完成狀態，或回報「結果不明」；不能只憑重試宣稱 exactly-once。 |

這些推論直接來自目前 `act` 最後才寫 history，以及 input／consume／state 的寫入順序。[aos_agent.py:144](../lib/aos_agent.py)、[aos_agent.py:191](../lib/aos_agent.py)

逾時還有一個 process group 邊界：`run_target`／`run_inst` 開工具時使用 `start_new_session=True`，其 timeout 砍的是**那個工具自己的 group**。若外層 kernel timeout 只砍 agent 那一組，不能假設已另開 session 的工具也一定跟著消失。這正是「工具 timeout」與「整格 timeout」不能混為一談的理由。[aos_exec.py:218](../lib/aos_exec.py)

實作會牽動哪些檔案：

| 選項 | 主要改動位置 |
|---|---|
| **A 保持原樣** | 不需為執行模型改檔。若補 timeout／輸出限制：`proto5/lib/aos_agent.py`、`aos_exec.py`、`spec/aos-agent.md`；若變可配置，再改工具設定驗證與規範。 |
| **B tool cpu** | `lib/aos_agent.py` 加送出／收回與對帳；`spec/aos-agent.md` 改 act 和 waits 所有權；`spec/agent.md` 說明 pending 或外部紀錄。新增請求／結果協議、dispatcher／worker 模組及入口，實際檔名尚未定。只有選 kernel module 形狀才需 kernel 接線。 |
| **C pool** | `lib/aos_agent.py` 拆執行、收集、唯一 history writer；`aos_exec.py` 補可安全追蹤／取消 child 的介面、結構化錯誤，避免共用 stderr 擷取。跨格 pool 還需額外生命週期設計。 |
| **D async** | `spec/aos-agent.md` §5 正式化；`spec/aos-llm-ask.md` §2.3／`lib/aos_agent_info.py` 定义與驗證執行 metadata；`lib/aos_agent.py` 產生收據、处理完成輸入；新增或共用背景 worker／結果轉 input 程式。 |
| **E 混合** | B／C／D 所需部分，加工具策略驗證與混合批次協調；同時測順序、副作用並行、崩潰重入與晚到結果。 |

metadata 有一個現成邊界：

- 工具元素送模型前，只會移除 **`_` 開頭的頂層 key**。直接加裸的 `"async"`，目前會原樣送 API。
- `_meta` 現在是一份 inst，未知 inst 頂層 key 會忽略。把 `"timeout_ms"` 或 `"cpu"` 塞進去，**不代表現有執行器會採用它**。

所以 E 不是只加標籤，還要正式定义誰讀、誰驗、是否送模型。[strip_private:84](../lib/aos_agent_info.py)、[inst 未知欄位規則:56](../spec/inst-posix.md:56)

與 llm cpu 能共用多少：

| 層次 | 共用可能性 | 差異 |
|---|---|---|
| 請求 id、原子落檔、queued／running／terminal、結果路徑 | **可以共用** | 都是提交工作、稍後拿結果。 |
| 同 id／同內容的去重、worker 失聯、取消、期限記錄 | **可以共用機制** | 不同工具對「允許重試」的答案不同。 |
| 容量、優先級、排隊 | **可以共用骨架** | LLM 按 endpoint 容量；工具可能按 CPU、磁碟、網路或同一工作目錄互斥。 |
| payload | 應區分種類 | LLM 是 engine＋body；工具是 inst＋arguments＋agent base／執行環境。 |
| result payload | 可共用外層狀態 | LLM 回 assistant／usage；工具回 code／kind／stdout／錯誤資訊。 |
| 結果如何進對話 | **屬 agent，不能交 transport 決定** | think 接 assistant；B 接 tool；D 接後續 user。 |

proto4-5 已提供可參考的 request→running→done、results、hash 與 `worker_died` 做法，但不是 proto5 已定的共用協議。舊版也有 spawn 成功、pid 尚未寫入時的窗口，不能整份搬過來就算完成恢復設計。[request hash:21](../../proto4-5/llm_cpu_request.py)、[dispatch:200](../../proto4-5/llm_cpu_tick.py)

還有一項搬到 tool cpu 後會變的語意：目前 `$env` 讀 agent 執行環境，inst 路徑以 agent base／解析後 cwd 為中心。若改由 worker 才解 inst，不能無意間改讀 worker 的環境或 cpu 家目錄；要決定送的是**原始 inst＋解析上下文**，還是**已解析的執行內容**。[inst 路徑:89](../spec/inst-posix.md:89)、[load_obj:91](../lib/aos_inst.py)

---

**4．阻塞是不是常態**

**歷代普通工具的同步等待確實是常態；但「長時間占住負責排程的那一格」不是所有層都接受的常態。** proto2 的長工作與 proto4-5 的 LLM dispatcher，已明確把耗時工作移到外面；proto4-7 的工具層則仍同步。

| 工具／工作 | 一般耗時形狀，非本次量測 | 歷代做法 | 真正在乎什麼 |
|---|---|---|---|
| 算數、小 JSON 處理、小範圍 `ls`／`cat` | 常很短，啟動程式／排程開銷可能比工作大。 | 普通同步工具。 | 是否值得為每次短操作多做提交與輪詢。 |
| 大檔、遞迴搜尋、大目錄、遠端檔案系統 | 名字雖是 `cat`／`ls`，仍可能很慢或輸出很大。 | shell 同步；部分版本有 timeout／截字。 | 不能只靠工具名稱判斷短長；還有輸出量。 |
| 跑測試／build | 秒到分鐘皆可能。 | proto2 有同步測試，也有 `run_long`；4-7 用普通工具且每支 60 秒。 | 同顆 cpu 的其他 agent 能否接受延遲；逾時是否代表合理取消。 |
| 爬網／下載／外部 API | 延遲變動大，可能卡網路。 | 普通 shell 會同步；專門 queue／worker 才跨格。 | 執行期限、重試、副作用、是否需要先回收據。 |
| 再問一個模型 | 排隊＋推論，常遠長於本地小操作。 | proto2／4-5 用 queue＋worker；4-4／4-6 也保留直接同步呼叫。 | endpoint 容量、重複扣款、呼叫 agent 是否仍需做其他事。 |
| 長期監看／服務 | 可能本來就不應自行結束。 | 不適合期待普通 act 收到最終 stdout 才返回。 | 這個 call 的「完成」究竟是啟動成功，還是服務停止。 |

幾個容易混淆的說法：

| 說法 | 核對結果 |
|---|---|
| 「有 subprocess 就非同步」 | **不是。** A 本来就開 subprocess，但父層隨即 wait／communicate。 |
| 「有 thread 就不阻塞 cpu」 | **不是。** agent 若仍等 thread 完，aos-run 就仍等 agent。 |
| 「工具放另一個 cpu，就沒有阻塞」 | 阻塞可能只是移到那顆專用 cpu；這可以是有效隔離，但沒有消失。 |
| 「回 101 就是睡到事件來」 | 舊 kernel 仍把它放回 queue，之後輪到再檢查。 |
| 「interval 1 秒，所以每格最多 1 秒」 | **不是。** 預設從上次完成後再隔 1 秒；長格直接拉長週期。 |
| 「tool 訊息完整，所以工具不能背景跑」 | 完整性要求可以在收回結果後滿足；不要求等待期間占住原 cpu。 |

沒有從 repo 找到「agent 的每格最多可阻塞 X 毫秒」的既定標準。已存在的數字是：

| 既有數字 | 真正含義 |
|---|---|
| proto4-3 interval＝1000 ms | 兩次執行間隔，預設從完成後算。 |
| quantum＝5 | 5 次完成的 run，不是 5 秒。 |
| cpu timeout＝0 | 預設沒有格內時限。 |
| proto4-7 每工具 60 秒 | 防單工具拖太久；一批多工具仍可逐一等很久。 |
| proto5 工具 timeout＝0 | 目前規範和實作都是跑多久等多久。 |
| proto5 engine timeout＝120000 ms | HTTP 呼叫期限，與工具期限是不同設定。 |

串行時可用這個關係看：

```text
T_act ≈ 各工具耗時相加 ＋ 啟動／收輸出／存檔成本
```

C 若工具獨立且有足夠並行容量，可能接近最慢那支的時間；B 主要縮短 **agent 占住 cpu 的時間**，不保證工具更快完成；D 則連模型等待真結果的語意也改了。

下面只是供拍板的**示例門檻**，不是測得的規律或推薦值：

| 若你對共享 cpu 定的格內阻塞預算是… | 後果 |
|---|---|
| **100 ms** | 多數網路與測試工作要拆出去；部分本地工具連啟動成本都要量。 |
| **1 秒** | 很多本地短操作可以同步；不穩定的外部請求需另外處理。 |
| **5 秒** | 可接受更多小測試／短下載，但其他行程可能承受數秒延遲。 |
| **60 秒或不限** | 接近既有工具作法；若共享 cpu，就接受一支工具拉長其他 agent 等待。 |
| **每 agent 專用 cpu** | 其他 agent 的直接排程影響小一些；這個 agent 自己仍不能在該格處理新输入。 |

真正需要定的是誰的延遲預算：**kernel tick、共享 cpu 的其他行程、同一 agent 的新訊息，還是眼前這個任務的完成時間。**它們不是同一個數字。

---

**5．要你拍板的問題**

以下保留選項，不替你選：

| 問題 | 選項與各自一句話利弊 |
|---|---|
| **① 慢工具未完成時，模型要不要繼續？** | **等真結果（A／B／C）**：對話語意直接，但這輪模型停在工具邊界。**先收據（D）**：模型能先處理其他事，但要管理後续通知與未完成工作。 |
| **② 要解決的是占住 cpu，還是整批工具太慢？** | **B**：釋放 agent cpu，但增加提交／輪詢。**C 並行 join**：可能縮短整批時間，但仍占住本次 agent 呼叫。**兩者合併**：兩種都處理，狀態更多。 |
| **③ 所有工具統一，還是依工具選？** | **統一 A／B／D**：規則與測試較少，但部分工具承受不必要開銷或不合適語意。**E 混合**：各自合適，但同批結果、收據與恢復更複雜。 |
| **④ `sync／async／cpu` 要表示一個維度，還是拆開？** | **單一模式標籤**：容易看，但把執行地點與回覆語意混在一起。**分成執行 backend＋回覆方式**：能表達「tool cpu 跑、回真結果／回收據」，設定多一些。 |
| **⑤ tool 執行器放哪？** | **獨立 cpu／服務**：生命週期與 kernel 分離，需管理它是否活著。**kernel module 只派工**：可沿用 LLM 接線，但 module hook 必須保持短。**agent 自管 worker**：入口較少，恢復與清理責任集中在 agent。 |
| **⑥ 同一則 assistant 的工具可不可以並行？** | **全部串行**：副作用順序穩定，耗時相加。**只讓明確獨立的工具並行**：較快，但要有可並行判準。**全部並行**：簡單擴大吞吐，卻可能改變讀寫結果。 |
| **⑦ 每格、每工具、排隊各能等多久？** | **只設工具期限**：能把逾時回模型，但整批仍可能很久。**另設整格／排隊期限**：延遲有界，須定义尚未完成工作的收尾。**不限**：最簡單，接受永久等待可能性。 |
| **⑧ 執行結果不明時怎麼辦？** | **自動重試**：容易續跑，可能重複副作用。**回「結果不明」由模型／人處理**：避免盲目重送，但需要後續判斷。**只重試可冪等工具**：折衷，工具端要提供保證。 |
| **⑨ async 結果何時進記憶？** | **維持只在 idle 收 input**：改動少，結果可能延後。**在安全的格邊界也收**：反應快，但要保證不插入未補齊的 tool-call 區段。 |
| **⑩ agent pause／stop 對背景工作做什麼？** | **依草稿讓工作跑完、結果照存**：恢復後能接續，但工作仍消耗資源。**另提供取消**：可停止耗資源工作，但要分清已取消、已完成與結果不明。 |
| **⑪ tool cpu 與 llm cpu 共用到哪一層？** | **只共用檔案生命週期／錯誤外框**：保留各自語意，會有兩種 payload。**共用整個排程服務**：少一套服務，但容量、取消、重試與結果型別都要通用化。 |
| **⑫ 是否要保證同一 agent 絕不並跑？** | **維持操作前提**：機制少，但沿用舊多 cpu 排程時有上述重疊窗口。**加執行所有權／鎖或排程交接確認**：保障更明確，需定义崩潰後誰接手。 |