# 人手打的操作 CLI：指令總表

← [CLI 入口](README.md)｜[規格入口](../README.md)

## H-004．指令總表〔工程預設〕

共 **53 條**，alias／旗標不另計。

### daemon：開關服務、查待辦

[daemon 協議](../protocol/daemon.md)定啟動與 IPC，[ops](../protocol/ops.md)定事項。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 1 | `aos daemon start --config F`：在前景開 daemon | `helper_pid=none`，sudo 模式為 `helper_pid=1234` | 同 `aos daemon --config F`；2 設定錯、125 初始化／收尾失敗（含版本自檢不過、拿不到 cgroup 子樹）。正常 Ctrl-C 清空程序、存 state.json 後回 0。 |
| 2 | `aos daemon info --socket S [--json]`：查本次啟動 ID | `boot_id=…` | IPC `daemon.info`；IPC。每次重開換 ID。 |
| 3 | `aos daemon attention ls --socket S [--source N] [--status open\|done] [--json]`：列 daemon 自己的事項 | 來源、ID、原因、說明；JSON 每頁 RpcResponse | IPC `daemon.attention.ls` 分頁；IPC。 |
| 4 | `aos daemon attention show N ID --socket S [--json]`：看 daemon 事項 | 內容、建議處理、open／done | IPC `daemon.attention.show`；IPC。 |
| 5 | `aos daemon attention done N ID --socket S [--json]`：人處理完後，把 daemon 自己的事項標成完成 | `done N ID` | IPC `daemon.attention.done`；IPC。只管 daemon 來源。 |

daemon stdout 印 helper_pid 與 node 問題警告；stderr 只印自身原因的錯誤。啟動另寫 state_dir/helper.pid（一行 PID 或 none）及 daemon.pid；正常退出刪兩檔，舊檔只供提示、不據此殺程序。

sudo 啟動後降為 common_user（預設 SUDO_UID）；helper 不重拉，隨 daemon 退出。state_dir/state.json 存登記／pause／pending；pause 每秒存，意外退出最多丟一秒。重開自動 tick 頂層，保留 pause。

### node：建資料夾、管開格、讀證據

[布局、設定與鎖](../protocol/node.md)／[登記與查詢](../protocol/daemon.md)。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 6 | `aos node new N [--user U] [--tasks F \| --template kernel\|agent] [--socket S] [--agent-config F]`：建立 git node | `created N; initial_commit=…; tasks=<項數>` | 建檔、git init／初始 commit，P-210／715／814；2 產物無效或目標已存在、125 前置、1 建立／提交失敗。kernel 必給 socket；agent 必給 agent-config。 |
| 7 | `aos node ls [--node T ...] --socket S [--json]`：列登記與 once 結果 | 路徑、registered、paused、running、pending、last_tick；JSON 每頁 RpcResponse | 裸命令用 IPC `node.ls` 分頁；指定目標逐筆 `node.show`。IPC；部分失敗 1，換 boot 重列。 |
| 8 | `aos node show T --socket S [--json]`：看登記及最近一格 | owner、父、開關、實際 cgroup、last_tick | IPC `node.show`；IPC。另看業務摘要用下一條。 |
| 9 | `aos node summary N [--json]`：看 node 自報進度 | status、ready、due、觀測時間；JSON msg-summary | 讀 `.aos/summary/summary.json`，僅摘要權讀同 commit 的 published.json；查詢。 |
| 10 | `aos node register T --parent N --identity-grant F [--interval-ms M \| --once] [--provision F] [--yes] --socket S [--json]`：登記 | `registered T (not woken)` | 身分 F 為陣列，provision F 為授權物件；IPC `node.register`；IPC。擴額須確認。 |
| 11 | `aos node unregister T [--yes] --socket S [--json]`：排空目標與登記子樹，再解除 | `unregistered T` | IPC `node.unregister`；IPC。未確認 125；持久停用用 members rm。 |
| 12 | `aos node wake T --socket S [--json]`：要求現在跑一格 | `wake accepted T` | IPC `node.wake`；IPC。running 合併一個 pending，paused 只記 pending。 |
| 13 | `aos node pause N --socket S [--json]`：停新格並等收尾 | `paused N; running=false`；JSON 最後 node.show 回應 | IPC `node.pause` 後輪詢 `node.show`；IPC。等待進度走 stderr；中斷仍保持 pause。只管本 node。 |
| 14 | `aos node resume N [--yes] --socket S [--json]`：驗證手改並開閘 | `resume accepted N`；採用 commit 印 stderr | P-210 持鎖驗 inst/tasks／領域設定，確認 diff、提交後 IPC `node.resume`；改檔＋IPC，未確認 125。驗證不過保持暫停。 |
| 15 | `aos node provision N --from F [--yes] --socket S [--json]`：佈建 | `provision completed N` | F 為 P-107 params 去掉 node_id；IPC `node.provision`；IPC，未確認 125。 |
| 16 | `aos node config add N --from F --to config/F`：安裝其他普通設定 | `config/F` | `aos-config-add --node N --from F --to config/F`；改檔；先驗 JSON，下格驗設定；工具用 agent tools。 |
| 17 | `aos node tick N`：用目前帳號跑一格 | 任務 stdout | `aos-tick --node N`；0 全組完成、1 組失敗／跳過、2 壞表、3 故障、75 鎖忙、125 前置。不從 inst 切 UID。 |
| 18 | `aos node log N [--all] [--limit M]`：看提交歷史 | OID、時間、主旨 | 唯讀 git log；查詢。預設 20 筆 aos-tick group，--all 含維護提交；一格可零筆或多筆。 |
| 19 | `aos node receipt R ID [--json]`：查已提交的 RPC 回應 | method、status／exit；JSON RpcResponse | 固定 commit 讀 `state/messages/responses/ID.json` 並核對原請求；查詢。待回、RPC error 或指令失敗回 1；僅在 responses/ 則說尚未消費。 |

目標是資料夾：找 `.aos/inst.json`，再找 inst.json；檔案直接讀。布局有 `.aos/{inst.json,tasks.json,jobs/,summary/,outbox/,attention/}`、requests/、responses/、work/、public/、config/、state/。tasks 外層 _metainfo，每項 inst 加 id/kind/group/needs、無 user。

pause/resume 是開關，wake 是現在跑一格；直接 tick 仍可跑。last_tick.completed 不等於業務成功，launch_failed 未啟動、unknown 證據不足。once 單檔未啟動寫 `<inst檔名>.err`。runner 未啟動、tick 故障、程序清不乾淨，由 daemon 寫 node 的 `.aos/attention/`（ignore、不隨 group 還原）；建 node 時給寫權，寫不進就不管、stdout 印一行警告。helper 不見、state 存不下才是 daemon 事項。

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
| 31 | `aos kernel config check K`：驗目前設定、更新問題狀態 | 空 | `aos-kernel-check`；module，不合法回 2。提交設定檢查結果，不派工；事項另用 attend done。 |
| 32 | `aos kernel work K`：收工具請求／結果、安排 once | 空 | `aos-kernel-work`；module。先提交材料，後格 register/wake，後格收結果。 |
| 33 | `aos kernel work submit K --from-node R --file F [--json]`：送工具工作 | `submitted ID` | F 是 work-payload，檔案 `kernel.work.submit`；投件。命令完成後 stdout 才是內層 work-result。 |
| 34 | `aos kernel llm forward K`：核對路由／份額並轉交 LLM | 空 | `aos-kernel-llm-forward`；module；寫 forward-state，檔案 method 仍 llm.chat。 |

schedule 按 ready_seq，60 秒補查。

| 開 agent 時選哪條路 | LLM | 工具 | kernel 怎麼記量 |
|---|---|---|---|
| 全部都管 | agent 的 llm.target_node=本 K；裝 forward，路由到本池／上層／別隊 | tools.target_node=本 K；裝 work，代登 once | 代辦 module 記；agent 記錄只供核對 |
| 不管派送 | llm.target_node=管池的 node，直接開雙向投件權 | tools.target_node=null；agent 自登 parent_id=自己的 once | 裝 usage-collect，讀 agent 已提交用量；另授 repo 讀權 |

兩類可各選路，once 歸可信 parent_id。LLM 三檔與池 node 的定義以 [S-301](../scheduling/llm.md) 為準。

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
| 42 | `aos agent config check N [--draft F]`：驗目前或候選 agent 設定 | `valid` 或 `invalid 檔案:欄位` | `aos-agent-check [--draft F]`；0 有效、1 無效、2 用法、125 前置。驗引用／權限，不試 HTTP。 |
| 43 | `aos agent config recheck N`：修好後驗證設定 | `valid` | `aos-agent-check --recheck`；改檔，仍無效回 1；更新設定狀態，不 resume；事項另用 attend done。 |
| 44 | `aos agent task run N`：跑 agent module 一步，供任務表使用 | 空 | `aos-agent-step`；必須繼承 tick 鎖；0 本步完成、1 處理失敗、2 用法、125 前置。人手完整一格用 node tick。 |

say 持 R 鎖提交原件／outbox 後投 N，不 wake；accepted 只是接件。回話用新 ID 的 agent.say，payload 多帶可省的 in_reply_to 指原 ID，一律收進 history。say --wait 讀 target 本地已提交 replies，以 input_id/final 判完成；只有投件權仍可 say，不能保證能等 final。failed final 也回 0，表示已收到。

listen 看本地 assistant／工具及帶 in_reply_to 的回話：本地依 input_id、收到的回話依 in_reply_to 分組；每 200 ms 看新 commit，follow flush，工具顯示沿 [proto5](../../../proto5/spec/aos-agent/cli-listen.md)。top 沒裝 agent 任務，收話只存 history。

### llm、attend、clean、inst

[LLM](../protocol/work.md)／[池窗口](../protocol/kernel-tasks.md)／[待辦與清理](../protocol/ops.md)／[runner](../protocol/daemon.md)。

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

--store 預設 node，daemon 事項明給 daemon；JSON 沿 ops。`aos-attend` 只做 ls、show、done：show 顯示 message 與可選 suggestion（建議文字，不執行），done 將 node 的 `.aos/attention/open/` 檔搬到 `done/`，daemon 事項走 IPC done。

`aos attend try-solve` 以後再做：照建議試著處理，成功自動 done。

預設 agent／kernel 任務表都有 aos-clean；它記上次清理時間，未到設定間隔直接回 0（預設一天）。保留期 30 日、每批 64 件、預設封存；unknown 到期可清，其他未結／有引用保留。不認得的資料不碰、不回報，自訂任務自己清。
