# 人手打的操作 CLI

← [規格入口](README.md)｜[協議共用約定](protocol/README.md)｜[裁定第一～十一批](../notes/2026-09-29-verdicts.md)

CLI 規格草案，尚非實作；「缺」表示目前不能走通。

## H-001．一支 aos，按用途分層〔使用者方向 2026-09-29〕

正式形狀 `aos <用途> <動作> [更深子命令]`：node 管共通生命週期，kernel 管成員／配額／用量，agent 管訊息／回覆／context；其餘用途為 daemon、inst、llm、attend、clean。人與 agent 依[兩條通則](README.md#原則能下指令能管檔案就能交給-agent)共用入口。包既有 IPC、檔案 RPC、程式／git；命名／旗標為建議預設，不改底層來源等級。

**驗收：**alias 只改 argv，不加權限／行為。

## H-002．參數、輸出與結束碼〔建議預設，未拍板〕

N＝node、K＝kernel node、T＝inst 目標、F＝檔案。路徑依 cwd 轉正規化絕對路徑；IPC 必選 `--socket S` 或 `--daemon-config F`（取 socket_path），環境不授權。

預設 stdout 短句／表格，stderr 診斷／確認。`--json` 用各節列出的原協議物件，每筆加 LF，多筆為 JSON Lines，不加自創封套。缺 JSON schema 的命令暫不收 --json（2），列 D6；參數錯不送請求。

共同碼依 [P-006](protocol/README.md)：0 成功、2 用法／設定錯且未開始、125 自己無法開始；CLI 補 1＝已開始後失敗／結果不明，IPC 業務拒絕亦回 1、保留原 error。子程式碼依各節轉交。訊號看 wait；runner 有 inst 特例。斷線不代表沒做，禁止盲重送。

**驗收：**缺資料不補零；125 不冒充從未執行證據。

## H-003．危險確認〔使用者方向 2026-09-29〕

危險動作列影響、終端問 y/n；無終端拒絕（125），除非明給 `--yes`。unregister、停機、提高額度、特權佈建、採用手改、delete 清理都須確認；權限仍照底層。

--yes 不能跳過重複副作用／unknown 確認。`attend resolve` 完整沿 [P-603](protocol/ops.md)，不收 --yes／--yes-all（2），不得在外層代答 y；無終端的危險處置跳過、保持 open。

**驗收：**無確認不送危險請求；unknown 每次須終端確認。

## H-004．daemon start：前景啟動〔使用者方向 2026-09-29〕

**argv：**`aos daemon start --config F`（短形 `aos daemon --config F`）。**底層：**同一 daemon，[P-101～102](protocol/daemon.md)，前景、不讀 stdin；stdout 只印 helper_pid，診斷 stderr。

**權限／輸出／碼：**一般帳號為無 helper 模式；sudo 時 fork helper、主程式永久降為非 root common_user，預設 SUDO_UID；直接 root 啟動須明設非 root common_user。0 正常停機、2 設定錯、125 初始化／收尾失敗；啟動 JSON 缺 D6。**例：**`sudo aos daemon --config /etc/aos/daemon.json` → `helper_pid=1234`；不用 sudo → `helper_pid=none`。helper PID 不是 daemon PID。

**驗收：**kill helper 不自動重拉；daemon 死亡 helper 跟著退出。

## H-005．daemon stop：停機的入口〔建議預設，未拍板〕

**argv 提案：**`aos daemon stop [--yes]`。**缺 D6：**沒有 shutdown IPC／安全程序 handle 查詢，本版不提供（2、stdout 空、stderr 缺口）。不能由 socket 或 helper PID 猜 daemon。

目前以 daemon 前景 Ctrl-C，或持有啟動程序 handle 的部署管理器送 TERM；OS 須允許發訊號，明示停機不再問 y/n。依 [B-604](daemon.md) 停新格、寬限、清後代，啟動命令回 0 才算停好，失敗 125。**例：**`aos daemon --config F` → Ctrl-C → 停機診斷。訊號接法須補 daemon 明文契約。

**驗收：**全空才成功。

## H-006．node ls：列登記〔建議預設，未拍板〕

**argv：**`aos node ls --node T [--node T ...] [--json] --socket S`。每目標呼叫 [P-106](protocol/daemon.md) `node.get`；須其 owner／祖先 owner。表列路徑、owner_uid、identity_grant、once、interval_ms、paused、running、pending、stopping；JSON 每筆原 RpcResponse。碼 H-002，部分失敗整體 1。

**例：**`aos ls --node /srv/aos/top --node /srv/aos/job/inst.json --socket "$S"` → 兩列，標「僅查指定目標」。**缺 D1：**無枚舉 method／完整成員來源，裸 aos ls 回 2；不能掃資料夾當全表，once 消失回 not_registered。

**驗收：**不開 tick、不宣稱列全樹。

## H-007．node show：看單一 node〔建議預設，未拍板〕

**argv：**`aos node show N [--attention-dir D] [--part registration|summary|attention] [--json] --socket S`。底層 `node.get` 加直接讀 [P-307](protocol/messages.md) 同 commit／public 摘要、[P-601](protocol/ops.md) 通知；part 省略全看。登記依 owner／祖先授權，檔案依 OS 讀權。

文字顯示登記、摘要來源／觀測時間、可讀 open 件數；未指定 D 或無權時不填 0。JSON 依序原 RpcResponse、summary、逐件 attention；碼 H-002。**例：**`aos show /srv/aos/a --attention-dir /srv/aos/attention --socket "$S"` → `running=no summary=waiting_result open=1（可讀範圍）`。

**缺 D1／驗收：**沒有最近 tick 結果格式；最後 commit 只是一組、無變動不提交，不能拿來宣稱最近一格成功。

## H-008．node register：登記 node 或 once〔建議預設，未拍板〕

**argv：**`aos node register T --parent N --identity-grant F [--interval-ms N | --once] [--provision F] [--yes] [--json] --socket S`。F 分別是身分 JSON 陣列／provision 物件；組 `node.register`，照 [P-104](protocol/daemon.md)、[P-010](protocol/README.md)。頂層只能改 daemon 設定重開。

首次須父／祖先 owner；重登原 owner 可做、擴額只准父層於自身授權內下授。修改既有項須子樹逐筆暫停全空；提高額度問確認。文字 `registered T（未叫醒）`，JSON 原 RpcResponse，碼 H-002。**例：**`aos register /srv/aos/a --parent /srv/aos/top --identity-grant /tmp/grant.json --socket "$S"`，grant=`["aos-agent"]`。

**驗收：**user 已存在；once 的 parent 是真正發起 node、先登記再 wake，不因失聯重跑；新登記不自動開格。

## H-009．node unregister：排空並解除〔建議預設，未拍板〕

**argv：**`aos node unregister T [--yes] [--json] --socket S`。包 [P-105](protocol/daemon.md) node.unregister；須目標 owner／祖先，確認含已登記子樹後排空解除。文字 `unregistered T`／JSON 原 RpcResponse，碼 H-002。

**例：**`aos unregister /srv/aos/a --socket "$S"`。只改記憶體，持久停用缺 H-021，父可能重登。

**驗收：**後代全空才成功，不刪帳號／home。

## H-010．node wake：提前一格〔建議預設，未拍板〕

**argv：**`aos node wake T [--json] --socket S` → node.wake；目標 owner／祖先可用。印 `wake accepted（不保證開跑）`／原 RpcResponse，碼 H-002。running 合併 pending，paused 只留提示，不能解除 unknown 或繞資源政策。

**例／驗收：**`aos wake /srv/aos/a --socket "$S"`；重複提示不開重疊格，0 不等於完成。

## H-011．node pause：停新格並等全空〔使用者方向 2026-09-29〕

**argv：**`aos node pause N [--json] --socket S`。owner／祖先呼叫 `node.pause`，再以 `node.get` 等 running:false；只停本 node 新格、不殺本格、不遞迴，[P-105](protocol/daemon.md)。文字先報等待、全空才報 `paused, running=false`；JSON 先 pause 回應、最後 get 回應，進度 stderr；碼 H-002，中斷不撤銷 pause。

**例：**`aos pause /srv/aos/a --socket "$S"`。手改仍要 repo 寫權與 [P-203](protocol/node.md) 同把鎖；等待遇別人 resume 要重新核對。

**驗收：**本格能結束；查詢瞬間不當維護鎖。

## H-012．node resume：先採用手改，再開閘〔建議預設，未拍板〕

**argv：**`aos node resume N [--yes] [--json] --socket S`。包 [Q3](agent/configuration.md)／[P-207](protocol/node.md) 鎖／驗證／git，再 node.resume；須 IPC owner／祖先及 repo 寫權。

get 確認 paused、全空，再持 tick 鎖核對基線／擋板，列 staged、unstaged、新檔、刪檔完整 diff，確認驗證後提交；不含 ignored，無變動不 commit。有未採用受管變動／驗證失敗就保持暫停；不自動清擋板，乾淨才送 resume。

**例／輸出：**`aos resume /srv/aos/a --socket "$S"` → diff、問 y/n → `adopted <OID>; resume accepted`；JSON 原 RpcResponse、其餘 stderr。碼 0 成功、2 設定錯、75 鎖忙、125 前置失敗／未確認、1 commit/RPC 失敗；故障按 P-205。

**缺 D4／驗收：**完整 validator 介面，缺 adapter 不開閘；不抹手改、不重試 unknown。

## H-013．node new：建一個空 node〔建議預設，未拍板〕

**argv：**`aos node new N [--user NAME|UID] [--tasks F | --template NAME]`。普通檔案操作＋git init／初始 commit，按 [P-200～202](protocol/node.md) 建 inbox 分流／.tmp、work、config、state、inst、.gitignore、空 tasks；inst 跑 aos-tick。只收新／空目錄，不建空業務表。

須父目錄寫權；user 只寫 inst，不切 UID／建帳號。--tasks 裝合法完整表；**缺 D2：**kernel/agent 範本真實 argv／設定，未知範本回 2。git 作者沿既有設定，失敗保留現場。

**例／輸出：**`aos new /srv/aos/a --user aos-agent` → `created N; initial_commit=<OID>; tasks=0`。碼 0 成功、2 參數錯、125 前置失敗、1 建立／提交失敗；JSON 缺 D6。helper 見 H-014。

**驗收：**有初始 commit 才稱建好，空 node 不冒稱 agent。

## H-014．node provision：固定佈建動作〔建議預設，未拍板〕

**argv：**`aos node provision N --from F [--yes] [--json] --socket S`。F 是 [P-107](protocol/daemon.md) params 去掉 node_id，CLI 補 N；只包 `node.provision` 六種固定動作。須 owner／祖先且登記 actions／paths 相符；確認影響後做一件，JSON 原 RpcResponse，文字 `provision completed`，碼 H-002。

**例：**F=`{"action":"account_create","user":"aos-agent"}`，`aos node provision /srv/aos/top --from /tmp/account.json --socket "$S"`。名稱須頂層預授，可先借父的佈建權建帳號再登記孩子。account_create／chown／quota／mount 需 helper；cgroup 可用委派子樹。

**驗收：**chown 單路徑不遞迴；多步不回滾、失聯先查 OS；改限前子樹逐筆暫停全空，--yes 不越權。

## H-015．node config add：加入普通設定〔建議預設，未拍板〕

**argv：**`aos node config add N --from work/F --to config/F`。同程式 `aos-config-add --node N --from … --to …`，[P-207](protocol/node.md)。呼叫者 repo 寫權／tick 鎖，不切身分，不能在同 node tick 內呼叫。成功印目標路徑，JSON 缺 D6。

**例：**先編 `/srv/aos/a/work/tools.json`，再 `aos node config add /srv/aos/a --from work/tools.json --to config/tools.json`。安裝整份草稿（刪項也先改整份），工具 schema 缺 D2、由 adapter 驗證，下一格生效。

**碼：**0 已提交／無變動、2 參數／JSON 錯、75 busy、125 前置失敗、1 寫入失敗已還原、3 commit／還原故障。**驗收：**work 草稿不自行生效，不順便提交 dirty 檔。

## H-016．node tick：手動跑一格〔建議預設，未拍板〕

**argv：**`aos node tick N` → 原 `aos-tick --node N`，[P-203](protocol/node.md)。用執行者 UID／資源，不從 inst 切身分；要依登記身分執行用 wake。任務 stdout／stderr 原樣轉交，JSON 格式缺 D6。

**碼：**0 全組完成、1 組失敗／跳過、2 表錯未開任務、3 commit／收尾故障、75 鎖忙、125 無法開始。**例：**`aos tick /srv/aos/a`。daemon pause 不會禁止這個直接入口，維護期間不能另直跑。

**驗收：**直接呼叫照樣拿同把鎖，與 daemon tick 不重疊。

## H-017．inst run：直接跑一次 inst〔建議預設，未拍板〕

**argv：**`aos inst run [T] [--timeout-ms N] [--stderr F] [--json]`，T 預設 `.`。包 [P-109～110](protocol/daemon.md) runner，固定 inst bytes、提供 inst/status fd。目標照 P-010；timeout 正整數；不沿 proto5 非 JSON 直接執行、--dir-target、-- ARG 或 --stderr -。

只用有效 UID／資源，user 省略繼承、不同 UID 拒絕；authorized-uid 不授權，受管跨 UID 工作走 kernel/once。串流照 inst、摘要 stderr，JSON 印 P-110 回報；stdout 會繼承混入 JSON 時執行前拒絕（2），不偷偷重導向。

**碼／例：**2 用法錯、125 前置／收尾失敗、126/127 exec 失敗，其餘原子程式碼，訊號沿 inst 特例；`aos run /srv/aos/job/inst.json --json` → `{"started":true,"exit_code":0}`。

**驗收：**P-010 不變；started:false 不寫 exit，缺回報仍不明。

## H-018．node log：看提交歷史〔建議預設，未拍板〕

**argv：**`aos node log N [--all] [--limit N]`。包唯讀 git log，預設 limit=20、篩固定 `aos-tick group ` 前綴，--all 含維護提交；須 repo 讀權。輸出短 OID／時間／主旨，JSON 缺 D6。碼 0 查完、2 用法錯、125 無法開始、1 讀取失敗。

**例／驗收：**`aos log /srv/aos/a --all` → `abc123 aos-tick group receive..prepare`；一格可多筆或零筆，非完整格歷史。

## H-019．kernel members ls：看成員〔建議預設，未拍板〕

**提案 argv：**`aos kernel members ls K [--json]`。原意讀父已提交成員設定再逐筆 node.get；須父設定讀權與 IPC 授權。**缺 D2：**成員路徑／schema／adapter，本版回 2、stdout 空、stderr 缺口。

**例／驗收：**`aos kernel members ls /srv/aos/top` → 缺接口；不得掃子目錄猜成員，目前明列 ID 用 H-006。

## H-020．kernel members add：保存成員宣告〔建議預設，未拍板〕

**提案 argv：**`aos kernel members add K N --from F`。要包父成員設定 adapter、再由 tick node.register；須父設定寫權／配置權。**缺 D2：**持久格式與任務未定，本版回 2、stdout 空、stderr 缺口。

**例／驗收：**`aos kernel members add /srv/aos/top /srv/aos/a --from /tmp/member.json`；H-008 只登記記憶體，不冒稱下次開機會重建。

## H-021．kernel members remove：持久停用〔建議預設，未拍板〕

**提案 argv：**`aos kernel members remove K N [--yes]`。要包 H-020 adapter，再依 [B-604](daemon.md) 排空解除；須父配置權及 unregister 授權、危險確認。**缺 D2：**本版回 2、stdout 空、stderr 缺口。

**例／驗收：**`aos kernel members remove /srv/aos/top /srv/aos/a`；不刪帳號／home，不把 unregister 當永久移除。

## H-022．kernel quota set：提交資源配額〔建議預設，未拍板〕

**argv：**`aos kernel quota set K --from-node N --file F [--yes] [--json]`。F 是 [res-quota](protocol/schemas/res-quota.schema.json)，以 resources.set 投 quota.node_id 的可信父 K；須父 owner／祖先配置權，來源 N 依 H-025 提交發布，提高額度先確認。

**例／輸出：**`aos kernel quota set /srv/aos/top --from-node /srv/aos/top --file /tmp/a-quota.json` → `submitted <ID>`／原 FileRpcRequest；碼 H-025，未確認 125。

**驗收：**seq 明給、不由重送加一；accepted 不等於 OS 已套用，須查實際 cgroup，缺 module 回 -32601。

## H-023．kernel usage show：讀用量摘要〔建議預設，未拍板〕

**argv：**`aos kernel usage show N [--json]`。直接讀 [P-307](protocol/messages.md) 同 commit／public summary 的 usage，須摘要讀權，不開 tick。文字列用量／來源／觀測時間，JSON 完整 res-usage；0 成功、2 用法錯、125 前置讀取失敗、1 缺失／讀取失敗。

**例／驗收：**`aos kernel usage show /srv/aos/a` → `local active=1 unknown=0`；摘要已含子樹，不重加子孫、不補零。

## H-024．kernel usage measure：要求重測〔建議預設，未拍板〕

**argv：**`aos kernel usage measure N --from-node K [--json]`。resources.measure 檔案 RPC、params 空，須目標 owner／可信直接父；提交／發布及碼依 H-025。

**例／輸出：**`aos kernel usage measure /srv/aos/a --from-node /srv/aos/top` → `submitted <ID>`／原 FileRpcRequest。回應由 H-026 查，不原地等 tick。

**驗收：**不啟用缺席 module；沒有任務回 -32601。

## H-025．agent send：投一則訊息〔建議預設，未拍板〕

**argv：**`aos agent send N --from-node R --text-file F [--attachment F ...] [--json]`，F=`-` 讀 stdin。包 `agent.send`／[P-306](protocol/messages.md)；R 必須是可回件 node。須 R repo 寫權、N 投件權、附件對收件者可讀，--from-node 不證明身分。

CLI 產生固定 ID，持 R tick 鎖且工作區乾淨，保存原請求與目標關係、commit 後按 P-003 發布同 bytes。不另建 outbox，不盲重送；未明按 Q2/P-304 保留 unknown。H-022／024 共用此發布方式。

**輸出／碼／例：**`aos send /srv/aos/a --from-node /srv/aos/top --text-file /tmp/message.txt` → `submitted <ID>`；JSON 原 FileRpcRequest。0 已發布、2 內容錯、75 鎖忙、125 前置失敗、1 提交／發布失敗或未確認。投件由 kernel 判斷 wake。

**驗收：**先 commit 才派送；accepted 不等於 agent 完成。

## H-026．node receipt：看 RPC 收件回應〔建議預設，未拍板〕

**argv：**`aos node receipt R ID [--json]`。須 R 訊息讀權，讀同 commit 的 `state/messages/responses/ID.json`、核對原請求／可信來源；只在 inbox 就提示未提交，不消費。可查通用資源回應，不硬套 LLM/work 路徑。

**例／輸出：**`aos node receipt /srv/aos/top m1 --json` → 原 RpcResponse；文字列 method/result。碼 0 成功回應、1 待回／error／無可信配對、2 用法錯、125 前置失敗；無正式回應 stdout 空、原因 stderr。

**驗收：**不開 tick，同 ID 不等於可信、accepted 不等於 final。

## H-027．agent replies：看正式回覆〔建議預設，未拍板〕

**提案 argv：**`aos agent replies N [--input ID] [--json]`。讀 [A-203](agent/input.md) 已提交 progress/final，須輸出讀權。**缺 D3：**路徑／schema／輸入關聯，本版回 2、stdout 空、stderr 缺口。

**例／驗收：**`aos agent replies /srv/aos/a --input m1`；accepted、模型 message、未提交片段都不冒充 final。

## H-028．agent context show：看本次 context〔建議預設，未拍板〕

**提案 argv：**`aos agent context show N --request ID [--json]`。應讀已提交 context／LLM 請求，須其全文讀權。**缺 D3：**P-406 雖有 messages 格式，缺穩定定位／領域 adapter，本版回 2、stdout 空、stderr 缺口。

**例／驗收：**`aos agent context show /srv/aos/a --request q1`；不重新計算並冒充當時的 context。

## H-029．llm pool ls：讀池設定〔建議預設，未拍板〕

**argv：**`aos llm pool ls N --config config/F [--json]`。固定 commit 讀 [P-405](protocol/work.md) llm-config，路徑限 repo 內、須設定讀權。文字列 id／endpoint／model／quota_scope，JSON 原 llm-config（可含 key_ref 路徑，不讀 key）。0 成功、2 設定／用法錯、125 前置失敗、1 讀取失敗。

**例／驗收：**`aos llm pool ls /srv/aos/top --config config/llm.json` → `local example-model account-a`；只是配置，不測連線或顯示假健康。

## H-030．llm pool usage：讀最小池用量〔建議預設，未拍板〕

**argv：**`aos llm pool usage N [--json]`。底層／權限／碼同 H-023，文字列 llm 的 pool_id／active_requests／unknown_requests／觀測時間；JSON 完整 res-usage。

**例：**`aos llm pool usage /srv/aos/top` → `local active=1 unknown=0`。**缺 D5／驗收：**共享窗口、剩餘 token、冷卻／健康狀態無格式；不歸零 unknown、不拿單次 usage 冒充池總量。

## H-031．attend ls：只看待處理〔建議預設，未拍板〕

**argv：**`aos attend ls --attention-dir D [--source N --issue ID] [--json]`。直接讀 [P-601](protocol/ops.md) open、核對來源／檔名；須通知讀權，source/issue 同給。文字列來源／ID／reason／message／actions，JSON 原 attention；0 查完、2 用法錯、125 前置失敗、1 讀驗失敗。無權範圍明示不完整。

**例／驗收：**`aos attend ls --attention-dir /srv/aos/attention` → `a issue-1 config_invalid …`；不呼叫會自動做 safe 的 attend 本體。

## H-032．attend resolve：處理事項〔建議預設，未拍板〕

**argv：**`aos attend resolve --node N --attention-dir D --handlers F [--source N --issue ID] [--action ID] [--json]`。同一 aos-attend，[P-602～604](protocol/ops.md)／[S-405](scheduling/operations.md) 管行為；執行者既有權限，--node 不授權。

文字列來源／動作／結果，JSON 原 ops-action-record，子程式輸出 stderr。碼 0 回應／已送／無項、3 skipped/human、1 失敗／不明優先、2 表／用法錯（含 --yes）、125 前置失敗。

**例：**`aos attend --node /srv/aos/top --attention-dir /srv/aos/attention --handlers /srv/aos/handlers.json`。無 action 也可做唯一 safe，純看用 ls；缺 D4 adapter 就 action_not_available。

**驗收：**危險逐件 y/n，來源確認才移 done。

## H-033．clean run：跑既有清理〔建議預設，未拍板〕

**argv：**`aos clean run N --config F [--yes] [--json]` → 原 `aos-clean --node N --config F`，[P-605～606](protocol/ops.md)。用執行者 repo／封存寫權；delete 模式先確認，--yes 由 CLI 消化、不傳給原程式；人用入口不收 --in-tick。

文字列本批數量／outcome／歷史未回收，JSON 原 ops-clean-report。0 本批成功／無項、2 設定錯、125 前置失敗／未確認、1 開始後失敗。**例：**`aos clean /srv/aos/a --config /srv/aos/clean.json --json`。

**缺 D4／驗收：**缺終局／消費／引用遍歷證據就保留、報 clean_blocked；history_space_reclaimed 固定 false。

## H-034．待補與要決定的界線〔建議預設，未拍板〕

**D1（daemon/node）：**缺授權範圍的登記枚舉（含 once）／最近 tick 結果。

**D2（node/messages/agent）：**缺持久成員、增刪／重建 adapter、agent 領域設定及真實任務範本；先補最小完整循環。

**D3（agent/messages）：**缺 progress/final、輸入關聯、context 定位/schema；先按輸入 ID 查回覆。

**D4（node/ops）：**缺完整 validator、來源重驗／解除、unknown/run 與 clean 遍歷 adapter；缺證據不做。

**D5（resources/work）：**缺共享窗口及池狀態；目前只查配置／並行觀測。

**D6（daemon/node）：**缺停機訊號契約、跨終端 stop、啟動/new/config-add/tick/log JSON。請決定現在是否要跨終端 stop；建議先 Ctrl-C，後補授權 shutdown IPC。

**驗收：**本次不改正本，缺接口不回假成功；已裁定不重問。

## H-035．常用 alias〔建議預設，未拍板〕

參數原樣轉交。

| 短形 | 正式命令 |
|---|---|
| `aos daemon --config F` | `aos daemon start --config F` |
| `aos ls` | `aos node ls` |
| `aos show` | `aos node show` |
| `aos register` | `aos node register` |
| `aos unregister` | `aos node unregister` |
| `aos wake` | `aos node wake` |
| `aos pause` | `aos node pause` |
| `aos resume` | `aos node resume` |
| `aos new` | `aos node new` |
| `aos send` | `aos agent send` |
| `aos run` | `aos inst run` |
| `aos tick` | `aos node tick` |
| `aos log` | `aos node log` |
| `aos attend --node …` | `aos attend resolve --node …` |
| `aos clean N …` | `aos clean run N …` |

**驗收：**裸 aos ls 仍報 D1。

## H-036．完整循環走查〔使用者方向 2026-09-29〕

以下為落地驗收腳本，git 作者已設定；不是現在已跑通。**「缺」後畫面是待驗收條件。**

### 1. 寫設定、開兩種 daemon

```sh
DEMO="$HOME/aos-demo"
mkdir -p "$DEMO/attention" "$DEMO/run"
S="$DEMO/run/daemon.sock"
cat > "$DEMO/daemon.json" <<EOF
{"version":1,"socket_path":"$S","attention_dir":"$DEMO/attention","roots":[]}
EOF
aos daemon --config "$DEMO/daemon.json"
# helper_pid=none；前景 Ctrl-C，等 0。
sudo aos daemon --config "$DEMO/daemon.json"
# helper_pid=1234；已降權。Ctrl-C，等 0。
```

sudo 設定／父目錄須可信，跨 UID socket ACL 另配。**缺 D6：**前景訊號契約。

### 2. 建頂層，設池與代發

```sh
aos new "$DEMO/top"
# created …/top; tasks=0
cat > "$DEMO/daemon.json" <<EOF
{"version":1,"socket_path":"$S","attention_dir":"$DEMO/attention","roots":[{"node_id":"$DEMO/top","identity_grant":[$(id -u)],"interval_ms":1000}]}
EOF
cat > "$DEMO/top/work/llm.json" <<'EOF'
{"version":1,"pools":[{"id":"local","endpoint":"http://127.0.0.1:4000/v1","model":"example-model","quota_scope":"local-account"}]}
EOF
aos node config add "$DEMO/top" --from work/llm.json --to config/llm.json
# config/llm.json
python3 - "$DEMO/top" <<'PYTASK'
import json, pathlib, sys
n = pathlib.Path(sys.argv[1])
tasks = []
for phase in ('collect', 'prepare', 'dispatch', 'cleanup'):
    t = dict(id='llm-'+phase, kind='kernel', argv=['aos-llm', '--node', str(n), '--config', str(n/'config/llm.json'), '--phase', phase])
    if phase in ('collect', 'prepare'): t['group'] = 'llm-prepare'
    if phase != 'collect': t['needs'] = ['llm-collect' if phase == 'prepare' else 'llm-prepare']
    tasks.append(t)
(n/'tasks.json').write_text(json.dumps(dict(version=1, tasks=tasks)))
PYTASK
git -C "$DEMO/top" add tasks.json
git -C "$DEMO/top" commit -m 'configure llm phases'
aos llm pool ls "$DEMO/top" --config config/llm.json
# local example-model local-account
aos daemon --config "$DEMO/daemon.json"
# helper_pid=none；保留前景，另終端設相同 DEMO、S。
```

endpoint/model 換成已有服務；key_ref 指 node 樹外私有檔，不把 key 放 argv/git。**同 UID 不隔離 key。缺 D2/D5：**成員／排程任務與共享窗口 adapter。

### 3. 建 agent、給身分與登記

```sh
aos new "$DEMO/a" --user "$(id -u)"
printf '[%s]\n' "$(id -u)" > "$DEMO/grant.json"
aos register "$DEMO/a" --parent "$DEMO/top" --identity-grant "$DEMO/grant.json" --socket "$S"
# registered …/a（未叫醒）
aos ls --node "$DEMO/top" --node "$DEMO/a" --socket "$S"
# a once=no paused=no running=no interval=未設
```

獨立 UID 支線：停 daemon，在 top 額度預授 `aos-demo-agent`，provision 授 account_create/chown 與 a 路徑；sudo 重開看 helper PID。寫 `{"action":"account_create","user":"aos-demo-agent"}` 到 account.json，打：

```sh
aos node provision "$DEMO/top" --from "$DEMO/account.json" --socket "$S"
# 顯示影響，答 y；帳號建好
```

新 node 用 `new --user aos-demo-agent`；既有 a 暫停／提交／全空重登。逐路徑 chown、ACL 配 repo/inst/requests/responses/socket，chown 不遞迴。

**缺 D2：**agent 範本／LLM 設定／持久成員 adapter。a 仍是空 node；補好才可裝範本、設定 LLM、父保存成員／配額，重啟才長回。

### 4. 傳訊到正式回覆

```sh
printf '請只回覆「收到」。\n' > "$DEMO/message.txt"
aos send "$DEMO/a" --from-node "$DEMO/top" --text-file "$DEMO/message.txt"
# submitted m1（以下換成實際 ID）
aos show "$DEMO/a" --attention-dir "$DEMO/attention" --socket "$S"
# 任務補好後：running/summary 改變
aos log "$DEMO/a"
# receive/prepare 組提交
aos llm pool usage "$DEMO/top"
# 有量測才可見 active=1
aos node receipt "$DEMO/top" m1
# 接件與回件都提交後 accepted=true
aos agent context show "$DEMO/a" --request q1
# 缺 D3：LLM 請求定位
aos agent replies "$DEMO/a" --input m1
# 缺 D3：下格收 LLM 後應有 final「收到」
```

**缺 D1/D3：**commit 不能證明最近格結果、LLM 已送／下格已收；accepted 不當 final，不用 wake 繞過資源判斷。

### 5. 弄壞設定、看事項、修掉

**缺 D2/D4：**agent 設定／重驗 adapter。補好才準備 a/work 下領域欄位錯誤的 bad-agent.json、正確 good-agent.json；handlers.json 依 P-602 接真實安全 recheck：

```sh
aos node config add "$DEMO/a" --from work/bad-agent.json --to config/agent.json
# 下一格沿舊有效設定，來源發事項
aos attend ls --attention-dir "$DEMO/attention"
# a issue-1 config_invalid …
aos node config add "$DEMO/a" --from work/good-agent.json --to config/agent.json
aos attend --node "$DEMO/top" --attention-dir "$DEMO/attention" --handlers "$DEMO/handlers.json" --source "$DEMO/a" --issue issue-1 --action recheck
# 只報本步結果；來源之後核對解除
aos attend ls --attention-dir "$DEMO/attention"
# 來源確認後 issue-1 才消失
```

### 6. 暫停、鎖內手改、恢復提交

```sh
aos pause "$DEMO/a" --socket "$S"
# paused, running=false
GIT_DIR_TASK="$(git -C "$DEMO/a" rev-parse --absolute-git-dir)"
flock -x "$GIT_DIR_TASK/aos/tick.lock" sh -c '"${EDITOR:-vi}" "$1/tasks.json"' sh "$DEMO/a"
# 編入一個合法 custom 任務；維護期間不另直跑 tick
aos resume "$DEMO/a" --socket "$S"
# 完整 diff，答 y → adopted <OID>; resume accepted
aos log "$DEMO/a" --all
# 看見手改提交
```

**缺 D4：**完整 validator。維護中不重啟 daemon（pause 不耐久）；故障擋板先修復。

### 7. 清理、歷史、停機、樹重建

```sh
printf '{"version":1,"mode":"archive","archive_dir":"%s/archive-a"}\n' "$DEMO" > "$DEMO/clean.json"
aos clean "$DEMO/a" --config "$DEMO/clean.json"
# unchanged/archived；缺遍歷證據保留並報 clean_blocked
aos log "$DEMO/a" --all
# tick 各組及維護提交
# 回 daemon 終端 Ctrl-C，等 0；不要 kill helper 代替停機
aos daemon --config "$DEMO/daemon.json"
# helper_pid=none；不同 UID 部署改用 sudo
aos ls --node "$DEMO/top" --node "$DEMO/a" --socket "$S"
# 頂層先出現，補好 D2 持久成員後 a 才逐層回來
```

**驗收：**舊程序全空、unknown 不重做，有 final／來源解除事項／父重建才算跑通；空表 tick 0 不算。目前 D1～D6 仍缺。

