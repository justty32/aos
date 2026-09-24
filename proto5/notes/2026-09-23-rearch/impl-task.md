你可以開自己的 subagent 平行做事（multi_agent 已開，最多 8 條）。這是實作任務，可以寫檔、開子進程。用繁體中文。

# 任務：照三份新規範重寫 proto5 的 cpu／daemon／kernel（Python 3.12，只用標準庫）

repo `../../..`。先讀：
- 規範（**唯一的真理，照它寫；不要改 `proto5/spec/*.md`**）：`proto5/spec/cpu.md`、`proto5/spec/kernel.md`、`proto5/spec/daemon.md`。
  底層不變：`proto5/spec/aos-exec.md`、`inst-posix.md`、`directives.md`。
- 現有程式：`proto5/lib/`（12 支）、`proto5/cli/`（9 個薄入口）、`proto5/lib/test/`（13 個測試檔，`_util.py` 是共用工具；
  跑法 `cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test`，現在 802 條全綠）。
- 慣例：`wf/workflows/common/conventions.md`（碰原始碼前要看）。
- 設計背景（不用全讀，卡住再翻）：`proto5/notes/2026-09-23-rearch/`。

## 邊界

- **新寫**：`lib/aos_home.py`（範式共用）、`lib/aos_client.py`（交件者用）、`lib/aos_exec_cpu.py`＋`cli/aos-cpu`、
  `lib/aos_daemon.py`＋`cli/aos-daemon`、`lib/aos_kernel.py`＋`cli/aos-kernel`，各自的測試。
- **刪掉**（沒人依賴、規範已作廢）：`lib/aos_run.py`、`lib/test/test_run.py`、`cli/aos-run`、`cli/aos-daemon-ctl`，
  舊 `lib/aos_daemon.py`／`aos_kernel.py` 與 `test/test_daemon.py`／`test_kernel.py` 被新的取代（新測試檔可以沿用檔名）。
- **不要動**：`aos_cpu.py`、`aos_llm_cpu.py`、`aos_tool_cpu.py`、`aos_agent.py`、`aos_agent_info.py`、`aos_llm_ask.py`
  及它們的測試與 cli（agent 之後另外重寫，現在 `aos_agent` 還 import 老的 `aos_cpu`／`aos_tool_cpu`）。
  `aos_directives.py`、`aos_inst.py` 不動。
- **`aos_exec.py` 只能加、不能改行為**：規範要 `run_target()` 三種目標都回 `timed_out`（cpu.md §4.1 表）。
  現有 `run_target()` 回 `(code, kind)`，很多人在用——加一個 `run_target_full(...)` 回帶 `code`／`kind`／`timed_out`／`ms`
  的物件（`InstResult` 已有 `timed_out`，沿用它的做法），`run_target()` 照舊。舊測試一條都不能壞。
- 全部做完：`python3 -m unittest discover -s test` **全綠**（舊的 802 減掉被刪的 run／daemon／kernel 測試，加上你的新測試），
  跑完**不留任何殘留行程**（`pgrep -f aos-cpu`／`aos-daemon`／`aos-kernel` 要空）。
- 不 commit、不 push；我來。

## 分四段，每段測試綠才進下一段

### 第 1 段：範式共用＋exec cpu＋交件者函式庫

`aos_home.py`——三份規範共用的東西，都在 cpu.md：
- 信封：讀一份 request 檔並分三類（cpu.md §3 那張表）、錯誤碼表（§3.2）、組 response／error。
- 放單：`.tmp`＋`os.link`（§3.1），EEXIST 丟一個能辨認的例外。
- `state.json` 原子讀寫（沒有＝預設）。
- `ack-`／`stop-` 前綴掃描與處理（§3.3、§4.2）。
- 開機對帳那張五列表（§6.2）做成一個純函式：輸入 current＋兩個檔在不在，輸出要做的動作。

`aos_client.py`——交件者的五步包成一個呼叫：取名（`<名>-<epoch ns>-<pid>`）、放單、等回音（**先查原單、再查回音**，
cpu.md §6.3 最後一段）、讀、ack。kernel 的 CLI、daemon 的客戶、以後的 agent 都用它。

`aos_exec_cpu.py`＋`cli/aos-cpu`——cpu.md §4～§7 整份：`go` 握手、fd 搬高位＋CLOEXEC、SIGPIPE 忽略、
訊號旗標（第一次溫和、第二次強制＋`stopped:true`）、迴圈 (1)～(5) 的順序、開機對帳、`aos-exec` method
（params→`run_target_full`，`Usage` 對到 -32602、`kind=aos` 是 result）、退出碼。

測試（`test/test_exec_cpu.py`、`test/test_home.py`、`test/test_client.py`）至少要有：
- 三類信封各一、-32700／-32600／-32601／-32602 各一；notification 不回音。
- 放單 EEXIST；ack 兩步、ack 指到不存在的回音是 no-op。
- 開機對帳五列各一（純函式測）＋真的把 cpu 開起來、殺掉、再開起來看它補 `Interrupted`（整合測）。
- 真開 `aos-cpu` 子進程：用 pipe 送 `go`／`stop`、EOF、SIGTERM 一次／兩次；檔案 `stop-`；跑一個會 sleep 的工作被強制停 → `stopped:true`；
  timeout → `timed_out:true`；不存在的 `.json` → `kind:"aos"`；普通檔目標＋`args`；`stderr:"-"`。
- 沒有父行程（stdin 不是 pipe）直接跑，不等 `go`。
- `aos_client` 端到端：放單→等→ack，回音被刪。
- 測試用短的 `poll_ms`；每條測試結束 cpu 都要停乾淨。

### 第 2 段：daemon

`aos_daemon.py`＋`cli/aos-daemon`——daemon.md 整份：flock（獨占；外人共享探測）、spawn（fork→寫表→`go`→回音；
pipe 四端 CLOEXEC、`close_fds`、自己一個 pgid 同 session、stdin／stdout 接管、inst 寫了 stdin／stdout 拒 -32602）、
`NameTaken`／同名同目標冪等／`restart` 更新、重拉（非 0 且沒被主動叫停，固定延遲，每次重讀 target）、`kill`（含 `dead` 直接拿掉）、
`stop` 階梯（pipe stop → TERM 給孩子 → KILL 給整組，各自計時並行）、EPIPE 跳下一階、啟動時接手上一任孩子
（`kill(pid,0)` 輪詢、TERM、等兩段、KILL）、daemon 自己的 request／對帳／ack 照範式。
spawn 的孩子用 `aos_exec` 跑 target 但 fd 0／1 換成 pipe——看 `aos_exec._execute_inst` 能不能直接用，不能就在 `aos_exec` **加**一個入口。

測試（`test/test_daemon.py`）：真開 daemon 子進程，用 `aos_client` 放 `spawn`；孩子用真的 `aos-cpu`（或一個會照契約等 `go`、認 `stop` 的小腳本，
但至少一條用真 cpu）。要測：spawn 冪等、`NameTaken`、非 0 退出被重拉／退 0 不重拉、`kill` 不重拉、stop 階梯三階（用很短的 wait 設定）、
flock 拒第二支 daemon、外人探測活不活、daemon 被 KILL 後新 daemon 啟動接手舊孩子、崩在寫表前孩子等不到 `go` 自己退。

### 第 3 段：kernel

`aos_kernel.py`＋`cli/aos-kernel`——kernel.md 整份：`init`／`boot`／`tick`／`add`／`rm`／`ls`／`stop`；帳本（§1.2 那個形狀）
與四張出貨箱「先記後放」；tick 是普通檔 target（帳本的 `cli`）＋ `args`；§1.3 帶 chain 的檔名；§3 十步照順序、
**第 6 步先查原單再查回音**、第 7 步比對 target 的 `NameTaken`；§4 判定表；§2 的 syscall 一次帳本寫入＋`deletes` 去重、
`rm` 三種情況＋once 當下回 `Removed`；§6 boot 五步（flock 探測 daemon、`kill` 舊 kernel cpu 等它消失、`stops` 清空、
第一次沒帳本的初始化、既有家不改寫、`envs` 抄進新家的 inst）；CLI 的等待／代 ack／退出碼／`ls` 偷看三處；`kernel.log` 最低內容。

測試（`test/test_kernel.py`，可以拆檔）：
- 純函式：判定表每列、`rm` 三種、syscall 重掃靠 `deletes`、出貨箱重放冪等、開機沒帳本的初始化。
- 整合（真 daemon＋真 cpu）：init→boot→add 反覆行程（跑幾次看 `runs`）→add once（拿到回音、內容是 exec 回音）→rm→stop 到 `stopped`
  → cpu 都退出、daemon 表空；重複 boot 舊鏈殘格自滅；殺掉正在跑的 cpu 看 `Interrupted` 被收；`pool: llm` 只派到那顆；
  改 `tick_ms`／`interval_ms` 生效；`bad_after` 退件；`done_exit` 完成。
- 模擬崩潰：直接改帳本製造「記了沒放」「放了沒記」「出貨箱沒清」的狀態，跑一格看它補齊、不重派。

### 第 4 段：端到端＋文件

- 一條「像真的」的測試：daemon＋kernel＋cpu `k`／`0`／`llm`（`llm` 有 `envs` 把一個假的 `llm-http` 腳本目錄放進 PATH），
  agent 端用 `aos_client` 放一個 once 工作（inst 的 argv 是 `llm-http`、stdout 指到檔），拿回音、讀 stdout 檔、ack；
  再一個反覆行程跑到 `done_exit`；然後 `aos-kernel stop`、等 `stopped`、daemon `stop`，最後 `pgrep` 全空。
- 更新 `proto5/lib/README.md`（模組表、API、測試數）與 `proto5/README.md` 的「程式」那一段（規範表我來改）。
- 寫 `proto5/notes/2026-09-23-rearch/impl-findings.md`：規範哪裡寫不清楚你自己選了什麼、哪裡跟底層（aos-exec／inst）對不上、
  哪裡你認為規範有錯（**不要改規範，寫這裡**）。一條一個編號。

## 寫法要求

- 跟現有模組一樣的風格：模組頂端 docstring 說職責與規範對應、錯誤用帶 `code`／`msg` 的例外、命令列 stderr 一行 `aos-xxx: <代號>: <白話>`。
- 測試要穩：所有等待都用輪詢＋合理上限（不要固定 sleep 猜時間）、所有 daemon／cpu 子進程在 `addCleanup` 裡確保殺掉、用 tempdir。
- 效能不重要，可讀優先；不要為了 KISS 之外的理由加東西。
- 最後把整套測試跑一次，回報：新增／刪除了哪些檔、測試總數、跑多久、`pgrep` 結果、impl-findings 的條數。
