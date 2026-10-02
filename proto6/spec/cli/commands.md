# 人手打的操作 CLI：指令總表

← [CLI 入口](README.md)｜[規格入口](../README.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

## H-004．指令總表〔工程預設〕

共 **60 條**，alias／旗標不另計。〔第十八批〕第 54～57 條是這輪新加的（取消、追查、清掛載診斷、轉檔）；〔第十九批〕第 58～60 條（查標準配備、掛行程、砍掛載行程）接在最後、不插隊，免得舊列號（例如「第 17 列」）失效。熱重載沒有子命令，見下面 daemon 段。

### daemon：開關服務、查待辦

[daemon 協議](../settled/protocol/daemon/README.md)定啟動與 IPC，[ops](../protocol/ops.md)定事項。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 1 | `aos daemon start --config F [--create-cgroup]`：在前景開 daemon | `helper_pid=none`，sudo 模式為 `helper_pid=1234`；〔第十九批〕另印一行 `standard: cgroup=full` 或 `standard: cgroup=fallback` | 同 `aos daemon --config F`；2 設定錯、125 初始化／收尾失敗（含 Python 低於 3.9、明寫 `cgroup_root` 或 `--create-cgroup` 卻準備不好）。〔使用者方向 2026-09-30，第十九批，推翻「沒有 cgroup v2 就拒絕啟動」〕**拿不到 cgroup v2 子樹不再拒絕**：照常啟動、開格，印 `cgroup=fallback` 並在 stderr 警告，標準配備改走備援（[B-605](../settled/deferred/daemon/cgroup.md)、[B-631](../settled/deferred/cg.md)）；不問 y／n。想走完整路、又不能用 sudo，首推 `systemd-run --user --scope -p Delegate=yes aos daemon --config F`（檢查步驟見 B-605）。`--create-cgroup`：子樹不在時 daemon 自己建，見 B-605。Ctrl-C／SIGTERM 正常停機、存 state.json 後回 0；走排空還是立即停看設定 `stop_mode`（[B-604](../settled/deferred/daemon/lifecycle.md)）。 |
| 2 | `aos daemon info --socket S [--json]`：查本次啟動 ID | `boot_id=…` | IPC `daemon.info`；IPC。每次重開換 ID。 |
| 3 | `aos daemon attention ls --socket S [--source N] [--status open\|done] [--json]`：列 daemon 自己的事項 | 來源、ID、原因、說明；JSON 每頁 RpcResponse | IPC `daemon.attention.ls` 分頁；IPC。 |
| 4 | `aos daemon attention show N ID --socket S [--json]`：看 daemon 事項 | 內容、建議處理、open／done | IPC `daemon.attention.show`；IPC。 |
| 5 | `aos daemon attention done N ID --socket S [--json]`：人處理完後，把 daemon 自己的事項標成完成 | `done N ID` | IPC `daemon.attention.done`；IPC。只管 daemon 來源。 |

daemon stdout 印 helper_pid 與 node 問題警告；stderr 只印自身原因的錯誤。啟動另寫 state_dir/helper.pid（一行 PID 或 none）及 daemon.pid；正常退出刪兩檔，舊檔只供提示、不據此殺程序。

sudo 啟動後降為 common_user（預設 SUDO_UID）；helper 的角色與動作見 [B-303](../settled/deferred/helper.md)、[B-609](../settled/deferred/daemon/helper-actions.md)。state.json 存什麼、pause 多久批次存一次、重開怎麼恢復，見 [B-603](../settled/deferred/daemon/lifecycle.md)。

〔使用者方向 2026-09-30，第十八批〕**停機兩種，由設定決定，沒有另外的指令**：daemon 設定 `stop_mode` 是 `"immediate"`（預設）時，Ctrl-C／SIGTERM 照舊短寬限停；是 `"drain"` 時先排空：停收新工作、等在途的做完，最多等 `drain_timeout_ms`（預設 10 分鐘），到了再轉立即停。排空途中再按一次 Ctrl-C 就改立即停〔第十八批 Q16〕；再送一次 SIGTERM 也改立即停，這半是〔建議預設，工程補充〕，不是使用者原話。行為以 [B-604](../settled/deferred/daemon/lifecycle.md) 為準。

〔使用者方向 2026-09-30，第十八批〕**熱重載只收 SIGHUP，沒有 `aos` 子命令、沒有 IPC**：改好設定檔後，以 daemon 的帳號或 root 打 `kill -HUP "$(cat <state_dir>/daemon.pid)"`。daemon 重讀並驗整份設定，只套用能即時改的欄位；新設定讀不進來就繼續用舊的。哪些欄位能即時改、哪些（例如 `socket_path`、`state_dir`、`cgroup_root`、`common_user`、有沒有 helper、其他帳號的額度與佈建權）改了仍要重開，見 [B-608](../settled/deferred/daemon/reload.md)；每次重載 daemon 在 stdout 印一行，列出已套用與要重開的欄位。

### node：建資料夾、管開格、讀證據

[布局、設定與鎖](../settled/protocol/tick.md)／[登記與查詢](../settled/protocol/daemon/README.md)。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 6 | `aos node new N [--tasks F \| --template kernel\|agent] [--socket S] [--agent-config F]`：建立 git node | `created N; initial_commit=…; tasks=<項數>` | 建檔、git init／初始 commit，P-210／715／814；2 產物無效或目標已存在、125 前置、1 建立／提交失敗。建在哪就掛在哪一層下面：預設上層是資料夾往上最近一個有 tick 的資料夾（[B-628](../settled/tick.md)），所以建在別的 node 資料夾之下就是它的下層。kernel 的 `--socket` 可省，省略時 kernel 執行時讀環境變數 `AOS_DAEMON_SOCKET`（[P-801](../protocol/kernel-tasks.md)）；agent 必給 agent-config。沒有 git 時略過初始 commit（[B-632](../settled/deferred/git.md)）；〔使用者方向 2026-10-01〕`--user` 拿掉（inst 與任務都沒有 `user`，[B-620](../settled/tick.md)）。 |
| 7 | `aos node ls [--node T ...] --socket S [--json]`：列登記與掛載行程結果 | 路徑、registered、paused、running、pending、`registration_id`、`mount`、`parent_override`、last_tick（含 `tick_seq`）；JSON 每頁 RpcResponse | 裸命令用 IPC `node.ls` 分頁；指定目標逐筆 `node.show`。IPC；部分失敗 1。〔第十七批〕分頁中 daemon 重開（boot_id 變了）回 1、stderr 提示重查，不自動重列、不撤回已印的頁。 |
| 8 | `aos node show T --socket S [--json]`：看登記及最近一格 | owner、父、開關、實際 cgroup、`registration_id`、〔第十九批〕`mount`（是不是掛載行程，取代原 `once`）、`parent_override`（上層是不是登記覆蓋出來的）、last_tick（含 `tick_seq`） | IPC `node.show`；IPC。有幾個欄位的意思見 [P-106](../settled/deferred/protocol/daemon/registration.md)；掛載行程沒有 `identity_grant`、`tick_seq` 固定 1。另看業務摘要用下一條。 |
| 9 | `aos node summary N [--json]`：看 node 自報進度 | status、ready、due、觀測時間；JSON msg-summary | 讀 `.aos/summary/summary.json`，僅摘要權讀同 commit 的 published.json；查詢。 |
| 10 | `aos node register T [--parent N] --identity-grant F [--interval-ms M] [--provision F] [--yes] --socket S [--json]`：登記 | `registered T (not woken)` | 身分 F 為陣列，每項可寫確切帳號名、UID，或〔第十八批〕前綴 `{"prefix":"aos-"}`、範圍 `{"uid_min":N,"uid_max":M}`；provision F 為授權物件；IPC `node.register`；IPC。擴額須確認。〔使用者方向 2026-09-30，第十九批〕**`--parent` 可省**：省略就看資料夾推上層（[B-628](../settled/tick.md)），該上層也要已登記；帶了就是覆蓋，**新舊兩個上層都要同意**，只有一方同意被拒；覆蓋後管轄權仍跟著資料夾。**沒有 `--once`**：一次性行程改用第 58～60 列的掛行程。換上層有兩條路：搬資料夾（等於舊 id 解除、新 id 重登），或同一 T 帶不同 `--parent`／拿掉 `--parent` 改登記；都要被搬的那棵先停、程序全空。登記、覆蓋、換父、額度怎麼比，見 [B-606](../settled/deferred/daemon/registration.md)。 |
| 11 | `aos node unregister T [--yes] --socket S [--json]`：收尾目標與登記子樹（停新格→SIGTERM→寬限→`cgroup.kill`→確認全空），再解除 | `unregistered T` | IPC `node.unregister`；IPC。未確認 125；持久停用用 members rm。掛載行程不用解除，用第 60 列（對它送 `node.unregister` 回 `kind_mismatch`）。收尾看哪些框、node 自己開的子框預設不殺，見 [B-606](../settled/deferred/daemon/registration.md)、[B-605](../settled/deferred/daemon/cgroup.md)。 |
| 12 | `aos node wake T --socket S [--json]`：要求現在跑一格 | `wake accepted T` | IPC `node.wake`；IPC。running 合併一個 pending，paused 只記 pending。 |
| 13 | `aos node pause N --socket S [--json]`：停新格並等在跑的那格結束 | `paused N; running=false`；JSON 最後 node.show 回應 | IPC `node.pause` 後輪詢 `node.show`；IPC。等待進度走 stderr；中斷仍保持 pause。只管本 node。 |
| 14 | `aos node resume N [--yes] --socket S [--json]`：驗證手改並開閘 | `resume accepted N`；採用 commit 印 stderr | P-210 持鎖驗 inst/tasks／領域設定，確認 diff、提交後 IPC `node.resume`；改檔＋IPC，未確認 125。驗證不過保持暫停。 |
| 15 | `aos node provision N --from F [--yes] --socket S [--json]`：佈建 | `provision completed N` | F 為 P-107 params 去掉 node_id；IPC `node.provision`；IPC，未確認 125。有哪些固定動作（含這輪加的交出框、建群組等）見 [B-609](../settled/deferred/daemon/helper-actions.md)；cgroup 上限調高、調低都能隨時改。 |
| 16 | `aos node config add N --from F --to config/F`：安裝其他普通設定 | `config/F` | 〔暫緩（2026-10-01）：`aos-config-add` 搬到[暫緩區](../settled/deferred/tick.md#暫緩b-625-加入普通設定aos-config-add)，本列跟著暫緩，照留作紀錄〕`aos-config-add --node N --from F --to config/F`；改檔；先驗 JSON，下格驗設定；提交由標準配備的 git 做，沒有 git 只做原子替換、不提交（[A-102](../agent/configuration.md)）；工具用 agent tools。 |
| 17 | `aos node tick N --socket S [--wait 秒] [--json]`：請 daemon 立刻跑一格，等它跑完（不想經 daemon 也可以直接跑 `aos-tick`） | `tick completed N; tick_seq=…; exit_code=…`；JSON 最後的 node.show 回應 | 〔使用者方向 2026-09-30，第十八批〕IPC 送 `node.wake`，以 wake 回應裡的 `registration_id` 與 `tick_seq` 為起點，再輪詢 `node.show`，直到 `registration_id`（在回應最上層）相同、`last_tick.tick_seq` 比起點大且 `last_tick.outcome` 不是 `running`，判定以 [B-607](../settled/deferred/daemon/registration.md) 為準；IPC。`registration_id` 變了表示舊登記已結束（解除、換父或 daemon 重啟），不再等、回 1 並提示重查。wait 預設 300 秒，逾時回 101（那格可能還在跑，別重下）。新的一格 exit_code 非 0、launch_failed 或 unknown 回 1。paused 時 wake 只記 pending，CLI 不等、回 1 並提示先 resume。〔使用者方向 2026-09-30，第十九批，撤第十八批「不在框就拒跑」〕**人手也可以直接打 `aos-tick --node N` 跑一格，風險自負**（[B-627](../settled/tick.md)）：照常做完，不看自己在哪個 cgroup，只是沒有通道（用不到 once 與通道傳訊），stderr 印一行 `standard: cgroup=… git=…`；同一資料夾 daemon 正在跑時拿不到鎖、回 75。要經 daemon 跑並等格次，才用本列。 |
| 18 | `aos node log N [--all] [--limit M]`：看提交歷史 | OID、時間、主旨 | 唯讀 git log；查詢。預設 20 筆 tick 自己的提交（`aos-tick group …` 與回 -32601 的 `aos-tick unclaimed`），--all 另含維護提交（設定安裝、成員、resume 採用等）；一格可零筆或多筆。 |
| 19 | `aos node receipt R ID [--json]`：查已提交的 RPC 回應 | method、status／exit；JSON RpcResponse | 固定 commit 讀 `state/messages/responses/ID.json` 並核對原請求；查詢。待回、RPC error 或指令失敗回 1；僅在 responses/ 則說尚未消費。 |
| 58 | `aos node check [N] [--json]`：只查標準配備走哪條路，不取鎖、不跑任務 | 每塊一行 `<元件>=full\|fallback`，缺的另印 `missing=<項目>`；JSON 每塊一個物件 | `aos-tick --node N --check`（N 預設 cwd）；0 全掛（含走備援）、1 沒全掛、2 用法錯。〔使用者方向 2026-09-30，第十九批；指令名為建議預設〕檢查什麼見 [B-630](../settled/deferred/git.md)，不需要 socket。 |

目標是資料夾：找 `.aos/inst.json`，再找 inst.json；檔案直接讀。布局有 `.aos/{inst.json,tasks.json,jobs/,summary/,outbox/,attention/,alarms/,runner-stderr.log}`、requests/、responses/、work/、public/、config/、state/，完整清單以 [P-200](../settled/protocol/tick.md) 為準。任務表格式（`methods`、`user` 都當陌生鍵）見 [P-202](../settled/protocol/tick.md)，順序與任務種類見 [B-620](../settled/tick.md)。

pause/resume 是開關，wake 是現在跑一格；人手要跑一格，用第 17 列經 daemon 等格次，或直接跑 `aos-tick`（風險自負，沒有通道，[B-627](../settled/tick.md)）。last_tick.completed 不等於業務成功，launch_failed 未啟動、unknown 證據不足。哪些事寫進 node 的 `.aos/attention/`、哪些是 daemon 自己的事項、掛載行程單檔未啟動的 `<inst檔名>.err`，見 [S-405](../scheduling/operations.md)；出事時從哪裡查起見[除錯指南](debugging.md)。

### kernel：保存成員、安排工作與資源

[kernel 任務](../protocol/kernel-tasks.md)：底層加 --node K；直接跑持鎖提交，tick 內由繼承的鎖 fd 判斷、交 tick 提交。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 20 | `aos kernel members add K --from F`：保存成員 | 成員短名 ID | `aos-kernel-members add --from F`；F 是 P-801 單項，改檔；同 ID 同值不變、異值回 2。 |
| 21 | `aos kernel members rm K ID`：從清單移除 | ID | `aos-kernel-members rm ID`；改檔，不存在回 1。只改清單，不刪 node／帳號。 |
| 22 | `aos kernel members ls K`：讀成員表 | 短名、node_id、身分、週期、配額 | `aos-kernel-members ls`，讀已提交 config/members.json；查詢。 |
| 23 | `aos kernel members sync K`：同步清單差異 | 空 | `aos-kernel-members sync`；module。清單／boot 沒變就不重登；移除 busy 留待維護。 |
| 24 | `aos kernel schedule K`：核資源後選成員叫醒 | 空 | `aos-kernel-schedule`；module，寫 state/kernel/schedule.json，IPC node.wake。 |
| 25 | `aos kernel schedule recheck K --from-node R [--json]`：請 K 再看 R 的收件與摘要 | `submitted ID` | 檔案 `kernel.schedule.recheck`，無 stdin 業務資料；投件。回應 stdout accepted，不保證 wake。 |
| 26 | `aos kernel resources K`：核對並套用成員配額 | 空 | `aos-kernel-resources`；module，按需 IPC node.provision。 |
| 27 | `aos kernel quota set K --from-node R --file F [--yes] [--json]`：提交子 node 的期望配額 | `submitted ID` | F 是 res-quota，檔案 `kernel.quota.set`；投件，提高額度未確認 125。seq 由材料明給；accepted 不代表已套用。 |
| 28 | `aos kernel usage show N [--json]`：讀用量 | 用量、觀測時間；JSON res-usage | 讀 node summary 的 usage；查詢。 |
| 29 | `aos kernel usage measure N --from-node R [--json]`：要求 N 重測 | `submitted ID` | 檔案 `kernel.usage.measure`，無 stdin 資料；投件。結果 stdout 是 res-usage，不啟用缺席 module。 |
| 30 | `aos kernel usage collect K`：收直屬成員自記用量 | 空 | `aos-kernel-usage-collect`；module。依 node/request/attempt 替換觀測，不每格累加。 |
| 31 | `aos kernel config check K`：驗目前設定、更新問題狀態 | 空 | `aos-kernel-check`；module。〔第十七批〕跑完並寫好問題紀錄就回 0（設定有問題也是 0，看 config-state 的 issues）；只有檢查自己跑不起來才非 0（P-805）。提交設定檢查結果，不派工；別的任務不依賴它，失敗也照收已派結果（P-805）；事項另用 attend done。 |
| 32 | `aos kernel work K`：收工具請求／結果、安排 once | 空 | `aos-kernel-work`；module。先提交材料，後格經通道 `node.mount` 掛行程（替成員掛的，`parent_id` 填成員），後格收結果。 |
| 33 | `aos kernel work submit K --from-node R --file F [--json]`：送工具工作 | `submitted ID` | F 是 work-payload，檔案 `kernel.work.submit`；投件。命令完成後 stdout 才是內層 work-result。 |
| 34 | `aos kernel llm forward K`：核對路由／份額並轉交 LLM | 空 | `aos-kernel-llm-forward`；module；寫 forward-state，檔案 method 仍 llm.chat。 |

schedule 按 ready_seq 選成員，補查間隔預設 60 秒、可調（[P-801](../protocol/kernel-tasks.md)）；判斷「新的一格做完了」看 `tick_seq`，不看牆鐘。

開 agent 時 LLM 與工具各選「kernel 全部都管」或「不管派送」哪一條路、kernel 各要裝哪些 module，以 [S-301](../scheduling/llm.md) 的兩條路線表為準；掛載行程（once）歸憑證所屬的 tick，或它指定的成員（[B-613](../settled/deferred/daemon/channel.md)）。

### agent：說話、看回話、管理工具

[agent 任務](../protocol/agent-tasks.md)：talk 轉交參數；tools/check/step 加 --node N。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 35 | `aos agent say TEXT [--target N] [--from-node R] [--wait [秒]]`：投一句話，可等正式 final | 投件位置；--wait 再印本 input 的 final 文字 | `aos-agent-talk say …`，檔案 agent.say；投件。預設 N=cwd、R=N、wait=300 秒；逾時／確知卡住 101，提醒勿重說。 |
| 36 | `aos agent listen [--target N] (--last [M] \| --wait [秒] \| --follow) [--show-calls \| --show-calls-full] [--json]`：看本地 assistant 或收到的回話 | 文字；JSON 每筆 message 一行 | `aos-agent-talk listen …`；查詢；last 預設 1，wait 預設 300 秒，逾時 101；follow Ctrl-C 回 0。不開模型。 |
| 37 | `aos agent replies N [--input ID] [--json]`：查正式 progress／final | kind、outcome、text；JSON 每筆 agent-reply | `aos-agent-talk replies N …`，讀 state/agent/replies；查詢。 |
| 38 | `aos agent context show N --request ID [--json]`：看當次 context | 來源、估算、messages、tools | `aos-agent-talk context show N …`；查詢。JSON 印 agent-context 及引用 llm-payload，缺引用回 1。 |
| 39 | `aos agent tools add N --from F`：合併工具清單 | `config/tools.json` | `aos-agent-tools add --from F`；F 是 agent-tools JSON，改檔；同名同值不變、異值回 2。 |
| 40 | `aos agent tools rm N NAME`：移除一個工具 | `config/tools.json` | `aos-agent-tools rm NAME`；改檔，不存在回 1。已派工具沿舊定義收結果。 |
| 41 | `aos agent tools ls N [--json]`：列工具 | 名稱、用途；JSON 完整 agent-tools | `aos-agent-tools ls …`；查詢。 |
| 42 | `aos agent config check N [--draft F]`：驗目前或候選 agent 設定 | `valid` 或 `invalid 檔案:欄位` | `aos-agent-check [--draft F]`；0 有效、1 無效、2 用法、125 前置。驗引用／權限，不試 HTTP。和 kernel 設定檢查的結束碼不一致，要不要統一延後（[P-008](../protocol/README.md#p-008)）。 |
| 43 | `aos agent config recheck N`：修好後驗證設定 | `valid` | `aos-agent-check --recheck`；改檔，仍無效回 1；更新設定狀態，不 resume；事項另用 attend done。 |
| 44 | `aos agent task run N`：跑 agent module 一步，供任務表使用 | 空 | `aos-agent-step`；必須繼承 tick 鎖；0 本步完成、1 處理失敗、2 用法、125 前置。人手完整一格用 node tick。 |

say 持 R 鎖提交原件／outbox 後投 N，不 wake；accepted 只是接件。回話用新 ID 的 agent.say，payload 多帶可省的 in_reply_to 指原 ID，一律收進 history；帶 in_reply_to 的只記錄、不觸發 LLM（[A-201](../agent/input.md)）。say --wait 讀 target 本地已提交 replies，以 input_id/final 判完成；只有投件權仍可 say，不能保證能等 final。failed final 也回 0，表示已收到。

listen 看本地 assistant／工具及帶 in_reply_to 的回話：本地依 input_id、收到的回話依 in_reply_to 分組；有 git 時每 200 ms 看新 commit；〔第十九批，[B-632](../settled/deferred/git.md)〕沒有 git 時改每 200 ms 看目前檔案與完成紀錄有沒有新增，不保證一致快照，follow flush，工具顯示沿 [proto5](../../../proto5/spec/aos-agent/cli-listen.md)。讀哪一份 history 看同一份（有 git 時同一 commit）的任務表由哪項任務宣告 `agent.say`：agent 任務讀 `state/agent/history/`，kernel 任務（例如 top 沒裝 agent 任務，收話只存 history）讀 `state/kernel/history/`（[P-713](../protocol/agent-tasks.md)）。

### llm、attend、clean、inst

[LLM](../protocol/work.md)／[池窗口](../protocol/kernel-tasks.md)／[待辦與清理](../protocol/ops.md)／[runner](../settled/protocol/daemon/README.md)。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 45 | `aos llm chat K --from-node R --file F [--json]`：送一份 LLM 材料 | `submitted ID` | F 是 llm-payload，檔案 llm.chat；投件，K 不存在回 1（投遞失敗）。F 帶 stream_path 時呼叫途中邊寫該檔。完成命令 stdout 是 llm-result，各 HTTP attempt 的 usage 獨立保存。 |
| 46 | `aos llm pool ls K [--config config/F] [--json]`：看池設定 | id、endpoint、model、quota_scope、schedule；JSON llm-config | 讀同 commit，預設 config/llm-pools.json；查詢，不讀 key。 |
| 47 | `aos llm pool usage K`：看池窗口／占用 | 一行 kernel-pool-status JSON | `aos-kernel-pool-usage --node K`；0 成功、2 用法、1 缺檔／不可讀；年齡及過時診斷走 stderr。 |
| 48 | `aos llm pool step K [--config F]`：推進池 module 一步 | 空 | `aos-llm --node K --config F`，F 預設 K/config/llm-pools.json；依 P-408，0 本步、2 設定、125 前置、1 執行失敗；供持鎖 tick 使用。 |
| 49 | `aos attend ls --socket S [--source N] [--json]`：沿登記樹彙整 open 待辦 | store、來源、ID、原因；JSON 每筆事項含 status | IPC node.ls＋daemon.attention.ls、各 node 的 .aos/attention/；IPC／查詢。 |
| 50 | `aos attend show N ID --socket S [--store daemon\|node] [--json]`：只看一件待辦 | 事項內容；JSON 事項含 status | daemon 走 attention.show；node 讀本地事項；IPC／查詢。 |
| 51 | `aos attend done N ID --socket S [--store daemon\|node] [--json]`：處理完標完成 | `done N ID`；JSON `{source_node,issue_id}` | `aos-attend done`；node 搬 open 檔到 done，daemon 走 `daemon.attention.done`；IPC／查詢。 |
| 52 | `aos clean run N --config F [--yes] [--json]`：清一批已可清的資料 | outcome、封存／刪除數；JSON ops-clean-report | `aos-clean --node N --config F`；0 成功／無變動、2 設定、125 前置／未確認、1 開始後失敗。delete 先確認。 |
| 53 | `aos inst run [T] [--timeout-ms M] [--stderr F] [--json]`：直接跑 inst | 串流依 inst；JSON daemon-runner-report | 固定 bytes／status fd 交 aos-runner，P-109／110；2 用法、125 前置／收尾、126/127 exec 失敗，其餘子程式碼。T 預設 .、只用目前 UID；--json 會和繼承 stdout 混流則執行前回 2。 |

同 node 同 scope 共算限制；同 UID 不隔離 key。

--store 預設 node，daemon 事項明給 daemon；JSON 沿 ops。`aos-attend` 三個動作各做什麼以 [S-405](../scheduling/operations.md) 為準，argv 與輸出見 [P-603](../protocol/ops.md)。`aos attend try-solve` 以後再做：照建議試著處理，成功自動 done。

預設 agent／kernel 任務表都有 aos-clean，未到設定間隔直接回 0（預設一天）；什麼可以清、保留期多久以 [B-404](../base/storage.md) 為準，設定與報告格式見 [P-605／P-606](../protocol/ops.md)。

### work：取消與追查一件工作

〔使用者方向 2026-09-30，第十八批〕取消的行為見 [B-203](../base/execution.md)，請求形狀見 [work P-411](../protocol/work.md)；追查是只讀的，除錯時先看[除錯指南](debugging.md)。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 54 | `aos work cancel K --from-node R --request-id ID [--json]`：請持有那件工作的 K 取消原請求 ID | `submitted ID` | 目前範本只有 kernel 的 work 任務宣告 `work.cancel`，所以只有 kernel 代跑的工具工作能這樣取消。檔案 `work.cancel`，stdin 是 [msg-cancel-payload](../protocol/schemas/msg-cancel-payload.schema.json) `{request_id}`，ID 是原請求（例如 `kernel.work.submit`）的 RPC id；投件。回應 accepted 只表示收下，終局看原請求的回應；在跑的由 K 用 `node.kill` 收尾殺掉（[B-613](../settled/deferred/daemon/channel.md)）。K 的任務表沒宣告 `work.cancel` 就回 -32601。 |
| 55 | `aos work trace ID [--node N] [--socket S] [--json]`：沿路串起同一件工作留下的紀錄 | 每站一行：站名、路徑或 commit、狀態；讀不到的站印「看不到」；JSON 每站一行 | 本機唯讀，不改任何檔、不發請求；查詢。ID 可以是請求 ID 或 attempt ID；N 省略用 cwd。從 N 的已提交紀錄出發，照紀錄裡的目標與回址往下一個 node 追，看的站：`.aos/outbox/`、`state/messages/`、收件區原件、`state/work/<前綴>-<attempt_id>/`、`.aos/jobs/<attempt_id>/` 與 `<inst>.err`、`.aos/alarms/`、`.aos/attention/`、git 裡主旨或內容含此 ID 的提交；給 S 時另查 daemon 的掛載診斷與 daemon 事項。沒權限讀的站只標「看不到」，不算錯。0 至少找到一站、1 什麼都沒找到、2 用法錯、125 前置。 |

### mount、migrate：掛行程與砍掉、清掛載診斷、批次轉檔

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 56 | `aos mount clear N --socket S [--json]`：手動清掉 N 與它整棵子樹底下已結束的掛載行程的診斷紀錄 | `cleared N <筆數>`；JSON 是 RpcResponse，result 為 `{node_id, cleared}` | IPC `mount.clear`（〔第十九批改名〕原 `aos once clear`／`once.clear`）；IPC。〔使用者方向 2026-09-30，第十八批〕只清已解除（`registered:false`）且呼叫者是 owner 或祖先 owner 的紀錄，在跑的、別人的不動、不回報。平常 daemon 會自動淘汰（`mount_diag_max` 預設 1024 筆、`mount_diag_ttl_ms` 預設 24 小時），規則以 [B-610](../settled/deferred/daemon/channel.md) 為準。 |
| 57 | `aos migrate N [--dry-run] [--json]`／`aos migrate --daemon-config F [--dry-run] [--json]`：把舊版格式的檔一次轉成目前版 | 每個轉了的檔一行：路徑、舊版→新版；沒東西可轉不印 | 本機改檔；改檔。〔使用者方向 2026-09-30，第十八批；argv 為建議預設，未拍板〕規則以 [C-07](../contracts.md) 為準：node 裡的持久檔在 node 鎖內轉、以一個 group 提交；daemon 的設定檔與 `state.json` 只在 daemon 停著時轉，daemon 在跑回 125。--dry-run 只列會轉哪些、不寫。檔的版本比程式新就拒絕、回 1，不猜讀。目前各格式都是第 1 版，跑了回 0、不印。 |
| 59 | `aos mount run T --parent N [--json] --socket S`：把 T（資料夾或單檔 inst）掛到 daemon 上立刻跑一次 | `mounted T registration_id=…` | IPC `node.mount`（[B-613](../settled/deferred/daemon/channel.md)、[P-118](../settled/deferred/protocol/daemon/channel.md)）；IPC。〔第十九批；指令名為建議預設〕人手沒有憑證，所以 `--parent` 必填，呼叫者要是 N 的 owner 或祖先 owner；不接受週期與身分額度；T 跑的帳號要在 N 的額度內（inst 頂層沒有 `user`，2026-10-01）。同一個 id 還在跑或已是登記回 1（`registration_conflict`）。結果用 `aos node show T` 看。 |
| 60 | `aos mount kill T --socket S [--json]`：砍掉一個掛載行程並收尾 | `killed T` | IPC `node.kill`；IPC。〔第十九批；指令名為建議預設〕對登記的 node 回 1（`kind_mismatch`），已結束回 1（`not_registered`）。取消在跑的工作就用它（[B-203](../base/execution.md)）。 |
