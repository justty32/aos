# 人手打的操作 CLI

← [規格入口](README.md)｜[協議](protocol/README.md)｜[全部裁定，後批優先](../notes/2026-09-29-verdicts.md)

**待實作規格**；指令／畫面為驗收預期，七步使用本地測試 LLM。

## H-001．共用讀法〔使用者方向；工程預設〕

形狀 `aos <用途> <動作> [更深]`，第一層 daemon/node/kernel/agent/llm/attend/clean/inst；短形見 alias。N 是 node、K 是 kernel、R 是發件／回件 node、T 是 inst 目標、F 是檔案、S 是 socket；[] 可省，| 擇一。

路徑按 cwd，--to 相對 N。IPC 用 --socket S 或 --daemon-config F。通常 stdout 放結果，stderr 放診斷／確認；daemon 例外見下。表中 --json：IPC 印原 RpcResponse，投件印 FileRpcRequest，其餘依該列；每筆加換行。沒列 --json 的命令傳它回 2。

設定指令持 tick 鎖提交，下格採用；草稿放樹外，work/ 放暫存。手改先 pause、排空、持鎖改，resume 驗證提交。unregister、特權佈建、提高額度、採用手改、delete 清理先問 y/n；有 --yes 的列可明示略過，未確認回 125。attend 危險動作逐件問；Ctrl-C 本身就是停機指令。

### H-002．失敗代稱

成功回 0；空清單合法，缺用量不補零。

| 代稱 | 結束碼與處理 |
|---|---|
| IPC | 2 參數錯；125 前置失敗；1 拒絕／斷線／結果未確認。保留原 error，stderr 印代號與白話。 |
| 查詢 | 2 用法；125 前置；1 無資料／損壞／讀取失敗。 |
| 改檔 | 2 格式／路徑錯；75 鎖忙；125 前置；1 寫入失敗已還原；3 提交／還原故障並擋新格。 |
| 投件 | 2 輸入錯；75 鎖忙；125 前置；1 讀取／投遞失敗或未確認；3 提交／還原故障。保留原件與 ID。 |
| module | 2 用法／設定；75 鎖忙；125 前置；1 處理／保存失敗；3 提交／還原故障。0 可以是等待結果。 |

75 未動手，可稍後重下；斷線先查、unknown 不重做。訊號看 wait，125 不證明未啟動。

## H-004．指令總表〔工程預設〕

共 **53 條**，alias／旗標不另計。

### daemon：開關服務、查待辦

[daemon 協議](protocol/daemon.md)定啟動與 IPC，[ops](protocol/ops.md)定事項。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 1 | `aos daemon start --config F`：在前景開 daemon | `helper_pid=none`，sudo 模式為 `helper_pid=1234` | 同 `aos daemon --config F`；2 設定錯、125 初始化／收尾失敗。正常 Ctrl-C 清空程序、存 state.json 後回 0。 |
| 2 | `aos daemon info --socket S [--json]`：查本次啟動 ID | `boot_id=…` | IPC `daemon.info`；IPC。每次重開換 ID。 |
| 3 | `aos daemon attention ls --socket S [--source N] [--status open\|done] [--json]`：列 daemon 自己的事項 | 來源、ID、原因、說明；JSON 每頁 RpcResponse | IPC `daemon.attention.ls` 分頁；IPC。 |
| 4 | `aos daemon attention show N ID --socket S [--json]`：看 daemon 事項 | 內容、actions、open／done | IPC `daemon.attention.show`；IPC。 |
| 5 | `aos daemon attention resolve N ID --socket S [--json]`：解除 daemon 自己的事項 | `resolved N ID` | IPC `daemon.attention.resolve`；IPC。只管 daemon 來源。 |

啟動另寫 state_dir/helper.pid（PID 或 none）及 daemon.pid；正常退出刪兩檔，舊檔只供提示、不據此殺程序。

sudo 啟動後降為 common_user（預設 SUDO_UID）；helper 不重拉，隨 daemon 退出。state_dir/state.json 存登記／pause／pending；pause 每秒存，意外退出最多丟一秒。重開自動 tick 頂層，保留 pause。

### node：建資料夾、管開格、讀證據

[布局、設定與鎖](protocol/node.md)／[登記與查詢](protocol/daemon.md)。

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

目標是資料夾：找 `.aos/inst.json`，再找 inst.json；檔案直接讀。布局有 `.aos/{inst.json,tasks.json,jobs/,summary/,outbox/}`、requests/、responses/、work/、public/、config/、state/。tasks 外層 _metainfo，每項 inst 加 id/kind/group/needs、無 user。

pause/resume 是開關，wake 是現在跑一格；直接 tick 仍可跑。last_tick.completed 不等於業務成功，launch_failed 未啟動、unknown 證據不足。once 未啟動寫 `<inst檔名>.err`。runner 未啟動、tick 故障、程序清不乾淨，由 daemon 寫 node 的 `.aos/attention/`（ignore、不隨 group 還原）；建 node 時給寫權，寫不進就不管，daemon stdout 印警告。daemon 的 stderr 只報自身錯誤，如 helper 不見、state 存不下。

### kernel：保存成員、安排工作與資源

[kernel 任務](protocol/kernel-tasks.md)：底層加 --node K；直接跑持鎖提交，tick 用 --in-tick。

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
| 31 | `aos kernel config check K`：驗目前設定、更新問題狀態 | 空 | `aos-kernel-check`；module，不合法回 2。提交修復後解除本地 config_invalid，不派工。 |
| 32 | `aos kernel work K`：收工具請求／結果、安排 once | 空 | `aos-kernel-work`；module。先提交材料，後格 register/wake，後格收結果。 |
| 33 | `aos kernel work submit K --from-node R --file F [--json]`：送工具工作 | `submitted ID` | F 是 work-payload，檔案 `kernel.work.submit`；投件。命令完成後 stdout 才是內層 work-result。 |
| 34 | `aos kernel llm forward K`：核對路由／份額並轉交 LLM | 空 | `aos-kernel-llm-forward`；module；寫 forward-state，檔案 method 仍 llm.chat。 |

schedule 按 ready_seq，60 秒補查。

| 開 agent 時選哪條路 | LLM | 工具 | kernel 怎麼記量 |
|---|---|---|---|
| 全部都管 | agent 的 llm.target_node=本 K；裝 forward，路由到本池／上層／別隊 | tools.target_node=本 K；裝 work，代登 once | 代辦 module 記；agent 記錄只供核對 |
| 不管派送 | llm.target_node=管池的 node，直接開雙向投件權 | tools.target_node=null；agent 自登 parent_id=自己的 once | 裝 usage-collect，讀 agent 已提交用量；另授 repo 讀權 |

兩類可各選路，once 歸可信 parent_id。

### agent：說話、看回話、管理工具

[agent 任務](protocol/agent-tasks.md)：talk 轉交參數；tools/check/step 加 --node N。

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
| 43 | `aos agent config recheck N`：修好後驗證並解除設定事項 | `valid` | `aos-agent-check --recheck`；改檔，仍無效回 1；解除本地事項，不解 unknown、不 resume。 |
| 44 | `aos agent task run N`：跑 agent module 一步，供任務表使用 | 空 | `aos-agent-step`；必須繼承 tick 鎖；0 本步完成、1 處理失敗、2 用法、125 前置。人手完整一格用 node tick。 |

say 持 R 鎖提交原件／outbox 後投 N，不 wake；accepted 只是接件。**最新裁定：回話用新 ID 的 agent.say，payload.in_reply_to 指原 ID，收進 history；listen 依此分回話。**say --wait 須讀 target 本地已提交 replies，以 input_id/final 判完成；只有投件權仍可 say，不能保證能等 final。failed final 也回 0，表示已收到。

listen 看本地 assistant／工具及 in_reply_to 回話；每 200 ms 看新 commit，follow flush，工具顯示沿 [proto5](../../proto5/spec/aos-agent/cli-listen.md)。top 收回話不叫 LLM；wire 待同步見文末。

### llm、attend、clean、inst

[LLM](protocol/work.md)／[池窗口](protocol/kernel-tasks.md)／[待辦與清理](protocol/ops.md)／[runner](protocol/daemon.md)。

| # | argv／做什麼 | 成功時 stdout | 底層與失敗 |
|---|---|---|---|
| 45 | `aos llm chat K --from-node R --file F [--json]`：送一份 LLM 材料 | `submitted ID` | F 是 llm-payload，檔案 llm.chat；投件。完成命令 stdout 是 llm-result，各 HTTP attempt 的 usage 獨立保存。 |
| 46 | `aos llm pool ls K [--config config/F] [--json]`：看池設定 | id、endpoint、model、quota_scope；JSON llm-config | 讀同 commit，預設 config/llm-pools.json；查詢，不讀 key。 |
| 47 | `aos llm pool usage K`：看池窗口／占用 | 一行 kernel-pool-status JSON | `aos-kernel-pool-usage --node K`；0 成功、2 用法、1 缺檔／不可讀；年齡及過時診斷走 stderr。 |
| 48 | `aos llm pool step K [--config F]`：推進池 module 一步 | 空 | `aos-llm --node K --config F`，F 預設 K/config/llm-pools.json；依 P-408，0 本步、2 設定、125 前置、1 執行失敗；供持鎖 tick 使用。 |
| 49 | `aos attend ls --socket S [--source N] [--json]`：沿登記樹彙整 open 待辦 | store、來源、ID、原因；JSON 每筆事項含 status | IPC node.ls＋daemon.attention.ls、各 node 的 .aos/attention/；IPC／查詢。 |
| 50 | `aos attend show N ID --socket S [--store daemon\|node] [--json]`：只看一件待辦 | 事項內容；JSON 事項含 status | daemon 走 attention.show；node 讀本地事項；IPC／查詢。 |
| 51 | `aos attend resolve --node R --socket S --handlers F [--source N --issue ID] [--store daemon\|node] [--action ID] [--json]`：執行處理表動作 | 每項動作與結果；JSON 每筆 ops-action-record | `aos-attend`，CLI 依 store 取來源（消化 --json）；0 已回應／排入待送／無項、3 跳過／human、1 失敗／不明、2 用法／表錯、125 前置。 |
| 52 | `aos clean run N --config F [--yes] [--json]`：清一批已可清的資料 | outcome、封存／刪除數、歷史未回收；JSON ops-clean-report | `aos-clean --node N --config F`；0 成功／無變動、2 設定、125 前置／未確認、1 開始後失敗。delete 先確認。 |
| 53 | `aos inst run [T] [--timeout-ms M] [--stderr F] [--json]`：直接跑 inst | 串流依 inst；JSON daemon-runner-report | 固定 bytes／status fd 交 aos-runner，P-109／110；2 用法、125 前置／收尾、126/127 exec 失敗，其餘子程式碼。T 預設 .、只用目前 UID；--json 會和繼承 stdout 混流則執行前回 2。 |

同 node 同 scope 共算限制；同 UID 不隔離 key。

--store 預設 node，daemon 事項明給 daemon；JSON 沿 ops，不靠目錄猜來源。attend 自動做唯一 safe；危險逐件問 /dev/tty，只收 y/Y，無終端跳過，不收 --yes。來源確認 done 才解除。clean 預設 30 日、64 件、封存，未結／unknown／有引用保留。

## H-030．CLI 怎麼變成 method〔第十二批裁定〕

alias 先展開；method 是指令去掉 aos、以點連接。IPC params 沿 schema，檔案 params 是 inst；收件端省目標／--from-node／--file，從 stdin 讀材料，不再投件。

```json
{"jsonrpc":"2.0","id":"m1","method":"agent.say","reply_to":"/srv/aos/top","params":{"argv":["aos","agent","say"],"stdin":"/srv/aos/top/public/m1.json","stdout":{"$opt":"inherit"},"stderr":{"$opt":"inherit"}}}
```

m1.json 內容是 `{"text":"你好"}`；回話用 `{"text":"收到","in_reply_to":"m1"}`。argv 保留 aos，method 對應命令；跨 node inst 可帶 envs／指示詞／任意 stdin 路徑，借權或換程式風險由使用者承擔。tick 提交後投 outbox、刪原件；result 用 work-result，stdout 只給路徑；讀不到報錯，不內嵌或搬運。schedule recheck/quota set 的本地 stdout 為 accepted:true，usage measure 為 res-usage。work submit/llm chat 跨格等業務結果才回，stdout 分別是 work-result/llm-result。

## H-035．常用 alias〔工程預設〕

| 短形 | 正式命令 |
|---|---|
| `aos daemon --config F` | `aos daemon start --config F` |
| `aos ls`／`aos show`／`aos new` | `aos node ls`／`show`／`new` |
| `aos register`／`aos unregister` | `aos node register`／`unregister` |
| `aos wake`／`aos pause`／`aos resume` | `aos node wake`／`pause`／`resume` |
| `aos tick`／`aos log` | `aos node tick`／`log` |
| `aos say`／`aos listen` | `aos agent say`／`listen` |
| `aos run` | `aos inst run` |
| `aos attend --node …` | `aos attend resolve --node …` |
| `aos clean N …` | `aos clean run N …` |

## H-036．七步走到底〔使用者方向；驗收腳本為工程預設〕

前置：非 root、proto6／git／Python 3、git 作者已設，DEMO 尚不存在。A 跑 daemon，B 操作，C 跑 HTTP；都設 DEMO、S。註解為預期輸出。

### 1. 寫 daemon 設定，先開一次空服務

終端 B：

```sh
DEMO="$HOME/aos-cli-demo"
S="$DEMO/run/aos.sock"
mkdir -p "$DEMO/run" "$DEMO/daemon-state" "$DEMO/drafts"
cat > "$DEMO/daemon.json" <<EOFJSON
{"version":1,"socket_path":"$S","state_dir":"$DEMO/daemon-state","roots":[]}
EOFJSON
```

終端 A：

```sh
aos daemon --config "$DEMO/daemon.json"
# helper_pid=none；保持前景
```

B 查詢，A 再按 Ctrl-C：

```sh
aos daemon info --socket "$S" --json
# {"jsonrpc":"2.0","id":"…","result":{"boot_id":"…"}}
# A：Ctrl-C，等 daemon 返回；echo $? 印 0
```

### 2. 建頂層 kernel、設定可重現的測試 LLM，再啟動

B 建頂層，準備測試 HTTP：

```sh
aos node new "$DEMO/top" --template kernel --user "$(id -u)" --socket "$S"
# created …/top; initial_commit=…; tasks=9
cat > "$DEMO/mock.py" <<'PY'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class API(BaseHTTPRequestHandler):
    def do_POST(self):
        q = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        last = q['messages'][-1]
        m = {'role':'assistant','content':'收到'}
        reason = 'stop'
        if last['role'] == 'user' and 'echo' in last['content'] and q.get('tools'):
            m = {'role':'assistant','content':None,'tool_calls':[
                {'id':'call_echo','type':'function','function':
                 {'name':'echo','arguments':'{"text":"工具完成"}'}}]}
            reason = 'tool_calls'
        elif last['role'] == 'tool':
            m['content'] = '工具完成'
        body = json.dumps({'choices':[{'message':m,'finish_reason':reason}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
HTTPServer(('127.0.0.1',18406),API).serve_forever()
PY
cat > "$DEMO/drafts/pools.json" <<'EOFJSON'
{"version":1,"pools":[{"id":"local","endpoint":"http://127.0.0.1:18406/v1","model":"demo-model","quota_scope":"local-account","max_attempts":3}]}
EOFJSON
aos node config add "$DEMO/top" --from "$DEMO/drafts/pools.json" --to config/llm-pools.json
# 各印安裝的 config/... 路徑
cat > "$DEMO/daemon.json" <<EOFJSON
{"version":1,"socket_path":"$S","state_dir":"$DEMO/daemon-state","roots":[{"node_id":"$DEMO/top","identity_grant":[$(id -u)],"interval_ms":1000}]}
EOFJSON
aos llm pool ls "$DEMO/top"
# local http://127.0.0.1:18406/v1 demo-model local-account
```

C 打 `python3 "$DEMO/mock.py"`；A 打 `aos daemon --config "$DEMO/daemon.json"` → helper_pid=none，自動 tick top。B 打 `aos node show "$DEMO/top" --socket "$S"` → 稍後 last_tick.completed、exit_code=0。mock 不驗真實 provider／UID 隔離。

### 3. 建 agent、給路線與份額、保存成員並登記

同 UID、LLM／工具全管；先 pause top 安裝設定。

```sh
aos node pause "$DEMO/top" --socket "$S"
# paused …/top; running=false
cat > "$DEMO/drafts/agent.json" <<EOFJSON
{"version":1,"llm":{"target_node":"$DEMO/top","pool":"local","model":"demo-model","context_tokens":32768,"max_completion_tokens":256,"timeout_ms":30000},"system_prompt":"照使用者要求回答。","tools_file":"config/tools.json","tools":{"target_node":"$DEMO/top"},"daemon_socket":"$S"}
EOFJSON
aos node new "$DEMO/a" --template agent --agent-config "$DEMO/drafts/agent.json" --user "$(id -u)"
# created …/a; initial_commit=…; tasks=1
cat > "$DEMO/drafts/routes.json" <<EOFJSON
{"version":1,"routes":[{"pool_id":"local","model":"demo-model","next_node":null,"next_pool":"local","allowed_origins":[{"node_id":"$DEMO/a","via_node":"$DEMO/a","via_uid":$(id -u)}]}]}
EOFJSON
cat > "$DEMO/drafts/member.json" <<EOFJSON
{"id":"a","node_id":"$DEMO/a","identity_grant":[$(id -u)],"quota":{"version":1,"node_id":"$DEMO/a","seq":1,"resources":{"llm":[{"pool_id":"local","concurrent_requests":1}]}}}
EOFJSON
aos node config add "$DEMO/top" --from "$DEMO/drafts/routes.json" --to config/llm-routes.json
aos kernel members add "$DEMO/top" --from "$DEMO/drafts/member.json"
# a
aos kernel members ls "$DEMO/top"
# a …/a；UID=目前使用者，無週期，local=1
aos node resume "$DEMO/top" --socket "$S"
# resume accepted …/top
aos node wake "$DEMO/top" --socket "$S"
# wake accepted …/top
aos node ls --socket "$S"
# top、a；等同步後 a registered=true
```

a 摘要為 idle。

### 4. 說一句話，看 tick，再聽回覆

```sh
aos agent say '請回覆收到' --target "$DEMO/a" --from-node "$DEMO/top"
# …/a/requests/<input_id>.json
# 可立即請 top 重看：
aos kernel schedule recheck "$DEMO/top" --from-node "$DEMO/a"
# submitted <recheck_id>
aos node show "$DEMO/a" --socket "$S"
# last_tick=completed、exit_code=0；短格可能看不到 running
aos node log "$DEMO/a"
# … aos-tick group agent..agent
aos agent listen --target "$DEMO/top" --last 1
# 等循環完成後：收到
aos agent replies "$DEMO/a"
# final succeeded 收到
aos llm pool usage "$DEMO/top"
# JSON：local-account，active_requests=0、unknown_requests=0；窗口計數依查詢時刻
```

尚無回話用 `aos agent listen --target "$DEMO/top" --wait 300`；--follow 持續看，Ctrl-C 停觀看。


### 5. 加工具，真的呼叫一次，再看工具結果

```sh
cat > "$DEMO/drafts/tools.json" <<EOFJSON
{"version":1,"tools":[{"name":"echo","description":"回傳收到的 JSON","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"],"additionalProperties":false},"argv":["/bin/cat"],"cwd":"$DEMO/a","result":{"kind":"json","schema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"],"additionalProperties":false}},"timeout_ms":5000,"output_limit_bytes":4096}]}
EOFJSON
aos agent tools add "$DEMO/a" --from "$DEMO/drafts/tools.json"
# config/tools.json
aos agent tools ls "$DEMO/a"
# echo 回傳收到的 JSON
aos agent say '請呼叫 echo，內容為工具完成' --target "$DEMO/a" --from-node "$DEMO/top" --wait 300
# 投件位置；工具完成
aos agent listen --target "$DEMO/a" --last 10 --show-calls-full
# 看得到 echo({"text":"工具完成"})、tool 結果 JSON、assistant「工具完成」
aos agent replies "$DEMO/a"
# progress 正在使用 echo；final succeeded 工具完成
aos node ls --socket "$S"
# once：registered=false、completed、exit_code=0
```

證據在 top/state/work、.aos/jobs/。

### 6. 製造設定待辦、修好再恢復

```sh
aos node pause "$DEMO/a" --socket "$S"
python3 - "$DEMO/drafts/agent.json" "$DEMO/drafts/bad-agent.json" <<'PY'
import json,sys
q=json.load(open(sys.argv[1])); q['llm']['context_tokens']=1
open(sys.argv[2],'w').write(json.dumps(q))
PY
aos node config add "$DEMO/a" --from "$DEMO/drafts/bad-agent.json" --to config/agent.json
# config/agent.json；下格驗領域欄位
aos agent config recheck "$DEMO/a"
# invalid llm.context_tokens；exit 1，寫 a/.aos/attention/
aos attend ls --socket "$S" --source "$DEMO/a" --json > "$DEMO/issues.jsonl"
cat "$DEMO/issues.jsonl"
# {…"reason":"config_invalid","actions":["recheck"],"status":"open"}
ISSUE=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).readline())["issue_id"])' "$DEMO/issues.jsonl")
aos node config add "$DEMO/a" --from "$DEMO/drafts/agent.json" --to config/agent.json
cat > "$DEMO/handlers.json" <<EOFJSON
{"version":1,"handlers":[{"id":"recheck","reason":"config_invalid","safety":"safe","effect":"重驗 a 的設定，修好才解除事項","action":{"kind":"exec","argv":["aos-agent-check","--node","$DEMO/a","--recheck"]}}]}
EOFJSON
aos attend resolve --node "$DEMO/a" --socket "$S" --handlers "$DEMO/handlers.json" --source "$DEMO/a" --issue "$ISSUE" --action recheck
# recheck succeeded；子程式 valid 在 stderr
aos attend show "$DEMO/a" "$ISSUE" --socket "$S"
# status=done；a 本地事項由來源確認解除
```

打 `aos node resume "$DEMO/a" --socket "$S"` → resume accepted；recheck 本身不 resume。

### 7. 清理、Ctrl-C 停機、重開後接著說話

```sh
aos node pause "$DEMO/a" --socket "$S"
printf '{"version":1,"archive_dir":"%s/archive-a"}\n' "$DEMO" > "$DEMO/drafts/clean-a.json"
aos clean run "$DEMO/a" --config "$DEMO/drafts/clean-a.json" --json
# {"version":1,"node_id":"…/a","outcome":"unchanged","archived_items":0,"deleted_items":0,"history_space_reclaimed":false}
# A：Ctrl-C，等 daemon 退出；echo $? 應為 0
```

資料未滿 30 日，故 unchanged。A 重開 `aos daemon --config "$DEMO/daemon.json"` → helper_pid=none，頂層自動 tick。B：

```sh
aos daemon info --socket "$S"
# boot_id 和上次不同
aos node ls --socket "$S"
# top、a 已恢復／同步；a paused=true，舊 once 診斷不在本次記憶體
aos node resume "$DEMO/a" --socket "$S"
# resume accepted …/a
aos agent say '重開後請回覆收到' --target "$DEMO/a" --from-node "$DEMO/top" --wait 300
# 投件位置；收到
aos agent listen --target "$DEMO/top" --last 1
# 收到
aos attend ls --socket "$S" --source "$DEMO/a"
# 空表：先前 done 事項不回到 open
# 結束驗收：A 再 Ctrl-C，等 0；C Ctrl-C 停 mock
```

意外中斷及真實服務另驗；unknown 不因重開重做。

## H-034．舊缺口怎麼解、還有什麼留待後續〔主編補〕

| 舊編號 | 解法 |
|---|---|
| D1 登記／tick 證據 | P-106／115 已有 node.ls/show、boot_id、last_tick、once 診斷。 |
| D2 成員／範本 | P-701～715 定 agent 設定／工具；P-801～814 定成員、同步、範本。 |
| D3 回話／context | P-703／708／713／714 定 input_id、reply、history、context；最新回覆 wire 同步見下表。 |
| D4 驗證／待辦／清理 | P-210／712／805／609 定驗證／recheck；P-716／814 定清理遍歷。 |
| D5 池狀態 | P-808～812 定路由、共享窗口及 pool-status，pool usage 有實際落點。 |
| D6 停機／JSON | P-114／116 定 Ctrl-C、存檔重開；stop 已裁定不做。JSON 沿原 schema。 |

| 剩餘缺口 | 為什麼現在不補 |
|---|---|
| 最新協議同步 | 回覆、跨 node inst、兩處待辦須同步 messages/agent/ops/daemon、schema、範例與驗證器，超出小修；node 事項持久格式暫沿 ops，新分支未驗。 |
| unknown／可選 run | 外部副作用由部署 dangerous adapter 判定，CLI 不能代定安全重跑。 |
| 自訂清理、git 歷史回收 | 自訂格式無通用終局／引用證據，報 clean_blocked；歷史回收留後續。 |
| 執行期驗收 | 實作後依 [驗收入口](conformance.md)測權限、中斷、真實 provider。 |
