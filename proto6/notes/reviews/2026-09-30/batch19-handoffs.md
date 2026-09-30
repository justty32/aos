← [審稿索引](README.md)

# 第十九批各隊交接（主對話彙整）

## T1 第一階段（完成）
- V-01 正本表新增／改動列：01、04、05、08、09、11、16、22、25（三層）、26（上下層）、27（通道）；預留表：B-606 改、B-610 改名「掛載行程的診斷」、B-612 通道／環境變數／憑證、B-613 掛行程與砍掉（原 once 的 daemon 端）、B-614 暫存訊息與急件、B-626 三層界線、B-627 人手或 cron 直接跑風險自負、B-628 上下層判定、B-629 標準配備清單掛法與 cgroup／git 備援、B-630 全掛檢查與 y／n、T-10 三層（已寫）、P-117 通道環境變數與憑證、P-118 掛行程與砍掉 method、P-119 送訊息取訊息錯誤碼。下一號：daemon.md B-615、tick.md B-631、terms T-11、daemon 協議 P-120。
- 交 T3：B-629 寫 cgroup 與 git 備援及備援下各保證剩什麼；B-630 定「沒全掛」剩哪些情況、看得出備援級；P-203 結束碼表分核心碼（0／1／2／75）與標準配備碼（3／125）；B-620 寫任務帶 `user`、kind 順序改由標準配備檢查。
- 交 T2：B-612 定通道環境變數名；P-117～119 放 protocol/daemon/，daemon/README 條號表改 P-100～119；B-605 寫首推 systemd 使用者委派與檢查步驟；B-614 跟 C-07 對齊（通道外層照 daemon IPC 嚴格，夾帶訊息同檔案收件格式照檔案 RPC 放寬）；B-613 定好後把 V-03「乾淨停機後 once 仍登記……」改寫交 T1。
- 疑點：備援級要不要警告或問 y／n（a stderr 一行不問／b 跟沒全掛一樣問／c 設定決定）；有備援後什麼算沒全掛（a 只剩標準配備被關或損壞／b 備援也失效，如拿不到 subreaper／c 取消 y／n 只留警告）；通道訊息放寬（a 外層嚴格內層放寬 暫定／b 整份嚴格／c 整份放寬）。

## T2 第一階段（完成）
### 定下的名字
- 環境變數：`AOS_DAEMON_SOCKET`（daemon 的 socket_path 絕對路徑）、`AOS_TICK_TOKEN`（本格憑證，32 小寫 hex；schema `daemon-registration.schema.json#/$defs/Token`）。daemon 開的每格、每個掛載行程都放；inst `envs` 用 `clear` 會清掉。
- method：`node.register`（`node_id`、`identity_grant` 必填；`parent_id` 改可省＝省略看資料夾推上層；`interval_ms`、`provision`、`token` 可省；拿掉 `once`；result 改 `{node_id, parent_id, registration_id}`）；`node.unregister`、`node.wake` 多可省 `token`；新 `node.mount`（取代 register once＋wake＋unregister；`node_id` 必填，`parent_id`、`token` 可省，不帶 token 時 parent_id 必填；不收週期與身分額度；result `{node_id, registration_id}`）；新 `node.kill`（`node_id`＋可省 token；result `{node_id}`）；新 `node.send`（`token`、`to`、`message`＝FileRpcRequest 必填，`urgent` 可省預設 false；result `{node_id}`）；新 `node.take`（`token` 必填，`limit` 1～256 預設 256；result `{messages, more}`）；`mount.clear`（原 once.clear 改名，`{node_id}`→`{node_id, cleared}`）。其餘 method 不收 token，帶了回 invalid_params。
- 改名：設定 `once_diag_max`／`once_diag_ttl_ms`→`mount_diag_max`／`mount_diag_ttl_ms`；cgroup 框 `once-<h>`→`mount-<h>`；node.show／ls 的 `once`→`mount`，新增必填 `parent_override`，掛載行程無 `identity_grant`、`tick_seq` 固定 1；state.json 拿掉 once、加 parent_override。
- helper：`daemon.helper.start` 多必填 `token`；`daemon.helper.bind` 登記分三種 BoundRegistration／TopRegistration／MountRecord。
- daemon 啟動 stdout 多印 `standard: cgroup=full` 或 `standard: cgroup=fallback`（寫法同 T3 的 tick）。
- 錯誤碼（-32000，data.code）：`token_invalid`（不可重試）、`kind_mismatch`（不可重試；對掛載行程送 unregister／wake／pause／resume／send、對登記 node 送 kill、掛載行程自己呼叫 take）、`mailbox_full`（可重試）、`message_too_large`（不可重試）；沒寫權、只有一方上層同意、憑證的 tick 不在目標上層鏈上都回 `forbidden`；`no_channel` 只在客戶端用（缺環境變數時自己擋）。
- 上限寫死：每收件 tick 最多 256 件、合計 16 MiB；單件 196608 bytes。
- 新條號：B-612 tick–daemon 通道、B-613 掛行程與砍掉、B-614 暫存訊息與急件、B-610 改標題「掛載行程的診斷：留存、淘汰與清除」；P-117 通道變數與憑證、P-118 掛行程與砍掉、P-119 送訊息取訊息與通道錯誤碼，都在新檔 `protocol/daemon/channel.md`；P-105 改標題「解除、叫醒、暫停、恢復與清除掛載診斷」。
- 授權讀法：帶憑證時「X 的 owner 或祖先 owner」讀成「憑證所屬 tick 就是 X 或在 X 的有效上層鏈上」；socket 對面帳號須是該格執行帳號或在該 node 身分額度內。
- B-605：啟動偵測完整路或備援路並印出、不問 y／n；首推 `systemd-run --user --scope -p Delegate=yes`＋五步檢查；備援時收尾改 subreaper＋程序群組（引 T3 的 B-631）；只在有 cgroup 時適用的（B-611 cgroup 鎖、框命名、上限、逃生口、`cgroup_*` 動作走備援回 `unsupported`）都標明；daemon 只剩 Python 3.9 硬需求，git 不查、引 B-630、B-632。
### 交 T1
conformance.md:48 `once-*`→`mount-*`，「取消在跑的 once」→「砍掉掛載行程（B-613）」；conformance.md:163 `aos once clear`→`mount.clear`、淘汰設定改 `mount_diag_*`；V-03「沒 cgroup v2 啟動報錯退出」改「照常啟動、印出走備援（B-605）」；V-01 `.err` 行為正本改 B-613。
V-03：daemon 開的 tick 有兩個通道變數、直接跑的沒有、客戶端報 `no_channel`；上一格憑證拿到下一格用回 `token_invalid`、daemon 重啟舊憑證全失效；寄件帳號對收件 `requests/` 沒寫權回 `forbidden`；急件送到叫醒收件 tick、一般件不叫醒下一格取得到；第一格掛常駐行程第四格 `node.kill` 砍得掉、別隊砍不掉；覆蓋上層只有一方同意被拒；沒 cgroup 時 daemon 照常啟動開格、`cgroup_*` 回 `unsupported`。
### 交 T3
base/inst.md:59「runner 不注入 `AOS_*`」改「除 daemon 放的兩個通道變數（B-612）外不注入；`envs` 用 `clear` 會一起清掉」；B-303「不把管理 socket 傳給 runner」加同一例外；B-302「cgroup v2 子樹拿不到就不啟動」改「改走備援（B-605、B-631）」；B-202、B-203 的 `once-*`→`mount-*`，「請 daemon 對 once 框收尾」→「送 `node.kill`」；inst.md:46「繼承上層」→「繼承有效上層」；B-623 收件任務用 `node.take` 取通道訊息。
### 交 T4
P-402 once 登記改經通道 `node.mount`：帶 `token`、替成員派的工作 `parent_id` 填成員、不帶 `identity_grant`；範例裡 `once:true` 都要改；P-408 寫兩個變數名。
### 交 T5
P-801 `daemon_socket` 改可省、預設讀 `AOS_DAEMON_SOCKET`；kernel-sync-state 引用的 `RegistrationOpen` 已拿掉 once、parent_id 可省；`node.register` 回應改 `{node_id, parent_id, registration_id}`；P-802 換父寫兩條路（搬資料夾或改登記）。
### 交 T6
CLI `aos once clear` 建議改名 `aos mount clear`（對應 `mount.clear`）；node.show 顯示欄位改 `mount`、`parent_override`；H-004 第 1 列改印 `standard: cgroup=…` 不再拒絕啟動；H-036 改用 `systemd-run --user`；commands.md:25「第二次 SIGTERM 也立即停」標工程補充；A-401 自開 once 改經通道 `node.mount`；P-701 `daemon_socket` 改可省。
### 疑點
中間資料夾後來開新 tick，已登記下層要不要改上層（a 登記時定死、要改照換父 暫定／b 每格重算自動換／c 變了寫事項等人手換）；資料夾推得的上層沒在此 daemon 登記（如 cron 跑的），覆蓋時怎麼同意（a 只要新上層 暫定／b 拒收要它先登記／c 看它的帳號經 socket 表態）；設定裡兩棵 root 互相包含（a 整份不收 暫定／b 各自頂層／c 被包含者自動變子層）；明寫 cgroup_root 卻準備不好（a 報錯退出 建議預設／b 改走備援只警告）；通道能否也傳回應（a 只傳請求 暫定／b 也可以）；掛載已登記的 tick 資料夾（現回 `registration_conflict`／或允許靠核心鎖擋）；急件叫醒要不要受上層節流（原疑-9，照 a 直接叫醒 暫定）。

## T3 第一階段（完成）
### 定下的名字
- tick.md：B-626 三層界線（換主題）、B-602 同一資料夾一次一格：互斥鎖、B-620 任務註冊表：照表依序跑、B-628 上下層判定、B-629 標準配備清單與掛載方式、B-630 全掛檢查：走完整還是備援、B-631 cgroup 框的備援、B-632 git 提交的備援：檔案日誌、B-623 收件：分派、-32601，commit 後才刪原件（-32601 從 B-620 搬來）、B-627 人手或 cron 直接跑一格：風險自負。
- 標準配備清單正式名稱：git 提交、group 與 needs、收件、投件與鬧鐘、發布摘要、aos-clean、切換使用者、cgroup 框、once、通道傳訊、daemon 端（重啟清空、排空停機）、全掛檢查。
- 全掛：cgroup 或 git 不能用走備援仍算全掛；沒 helper、沒通道只算功能受限不警告；「沒全掛」只剩標準配備本身不能跑（有終端機 y／n，n 回 2；沒終端機照跑記警告）。
- 檔案：鎖 `.aos/tick.lock`；擋板 `.aos/tick-blocked`；git 備援日誌 `.aos/journal/<seq>.json`（schema `node-journal`），投出副本 `.aos/journal/sent/`，失敗組 `.aos/journal/discarded/`。
- 待送封套新欄：`channel`（布林，只用於待送請求）、`urgent`（只在 channel:true 時可寫）。
- `aos-tick --check`：只查不跑，每塊印 `<元件>=full|fallback`；0 全掛、1 沒全掛、2 用法錯。每格 stderr 印 `standard: cgroup=… git=…`。
- 事項：`reason:"standard_incomplete"`、`issue_id:"standard-incomplete"`。git 備援換回 git 的第一個 commit 訊息 `aos-tick adopt`。
- 結束碼：0、1、2、75 核心；3、125 標準配備（125 只表示格首看到擋板檔）。
### 交 T1
V-01 預留表補 B-628～632，B-626、B-627、B-602、B-620、B-623 換標題；正本表 08、11 列的 -32601 改指 B-623；T-07 指 B-626、T-06「tick 基底」「system 屬基底」改寫；README 定位與依賴段：cgroup、git 是標準配備完整路線要的，沒有就走 B-631、B-632；C-07 拿掉任務 `user`；T-02、C-02 上層改看 B-628；T-03 加 tick 路徑正規化；P-004 -32601 改由標準配備回（B-623）。
V-03：沒有 daemon、git、cgroup 的機器上，同資料夾同時跑兩格一格回 75、照陣列順序跑、預設上層照資料夾算得出（B-602、B-620、B-628）；任務帶 `user` 照收、沒 helper 時帶別帳號那項回 125（B-620）；框外直接跑 `aos-tick` 照常做完一格、stderr 印 `cgroup=fallback`（B-627、B-630）；沒 git 時寫完成紀錄前當機原件還在下格重收、寫完後當機下格補刪原件不重吃、同 ID 重送從 `.aos/journal/sent/` 補投原 bytes（B-632）；取消送 TERM 後程序自己 exit 0 並完整發布，回原結果不是 canceled（B-203）。
### 交 T2
daemon 開的格回 75（有人手正在跑同資料夾）當普通結束、不停格、pending 照留；B-607 刪「不在框就拒跑見 tick」；`node.show` 最近結果要帶掛載行程的結束碼（任務帶別的 user 時 tick 用 `node.mount` 開它、再用 `node.show` 等結束碼）；B-605 自檢指向 B-630、核心只需 Python 3.9。
### 交 T5
S-405「沿登記樹」改上下層樹（B-628），收 `standard_incomplete`；S-203 在 cgroup 備援下只剩每程序各自上限、不是總量（B-631）；S-406「交 tick 投出」改標準配備。
### 交 T6
A-102 接住 P-207 的鎖與提交流程；H-036 與 A-102 接住 P-210 的建立與恢復流程（T3 之後縮 P-207、P-210）；H-004 撤框外拒跑、可加對應 `aos-tick --check` 的指令；agent-tasks、agent-template 的 `"user": false` 與 `agent-tasks.task-user.invalid` 範例跟著改；P-704 的核框句刪掉。
### 疑點
沒 git 時失敗組改動要不要還原（a 不還原留工作區 暫定／b 檔案級快照失敗時還原）；沒 git 跑一陣後裝好 git 第一格（a 整棵提交成 `aos-tick adopt` 暫定／b 擋下等人手／c 一個 node 定了路線不換）；任務帶別的 user 怎麼開（a 借 `node.mount` 開、跑在掛載框、不繼承鎖 暫定／b T2 另開事務在 `task-*` 框開並繼承鎖）；通道上沒人取的訊息（a 不回 -32601 暫定／b 格末代取、沒人宣告回 -32601）。照建議預設標暫定：kind 分段保留、有 tick 的資料夾看有無 inst 檔、補投時 git 歷史被整理當證據已清。

## T2 第二輪（完成）
- 交 T1：V-03「乾淨停機後 once 仍登記……」改成「掛載行程不存檔；daemon 重啟或停機時被收尾的，由掛它的 tick 照 unknown 規則核對，重啟後不接回（B-603、B-613）」。
- 疑點：`mount_diag_max` 設 0 時掛載行程一結束診斷就不留、tick 用 node.show 拿不到結束碼（a 照現狀寫明／b 在跑和剛結束還沒被查的不算進上限／c 改用 node.kill 或另開 method 直接回結果）。
- 待回：B-606「有效上層須已在同 daemon 登記」（T3）vs 暫定「只要新上層同意」（T2 疑點 2）。

## T4（完成）
- 交 T3：B-101 或 B-202 補「掛載行程的外層 inst 用工作所屬 node 已授權的有效身分；內層 inst 省略 `user` 時繼承，寫了必須解成同一 UID；kernel 不可讓工具繼承自己較高的權限」（之後 T4 刪 P-402 對應句）；B-203 要有舊-09（取消同步等收尾逾時記 unknown）。
- 交 T5：kernel-work-state.schema.json 第 22 行 description「once 自己 inst 的 user 不算」改掛載行程說法；kernel P-806「向 daemon 登記 once、wake」改 `node.mount`。
- 交 T6：agent-tasks 第 102 行「向 daemon 登記 once、wake」改 `node.mount`。
- 交 T1 V-03：kernel 替成員派工具時 `node.mount` 的 `parent_id` 填成員且不帶 `identity_grant`、工作歸成員；池的 `aos-llm` 掛 `aos-llm-call` 時省略 `parent_id`、歸池 node；缺通道變數時 `aos-llm` 報 `no_channel`、結束碼 125。
- 疑點：池 node 不在 daemon 底下時 aos-llm 沒通道掛不了 aos-llm-call（a 維持前提「池要跑在 daemon 底下」暫定／b 明文標功能受限／c 允許池自己直接跑 aos-llm-call）；`no_channel` 回 125（暫定）或 2。

## T6（完成）
- 交 T1：新條 A-304（清理遍歷）進 V-01 agent 段；A-201、A-203、A-401、A-403、N-14、A-102 擴寫，正本表描述跟上；H-004 總數 60（新增第 58 `aos node check`、59 `aos mount run`、60 `aos mount kill`）；V-03：`aos node check` 回 0／1／2、`aos mount run` 不帶 `--parent` 被拒、`aos mount kill` 對登記 node 回 `kind_mismatch`、agent 的 `node.take` 取件不超過每格 64 件、任務表帶 `user` 範例 schema 通過；走查的 `$CG` 與 sudo 說法已不存在，相關驗收句要改。
- 交 T3：P-207、P-210 可縮（行為在 A-102）。
- 交 T5：kernel-config 的 `daemon_socket` 改可省（P-801），對上 H-004 第 6 列「kernel 的 `--socket` 可省、省略讀 AOS_DAEMON_SOCKET」。
- 疑點：人手指令名（a `aos mount run`／`aos mount kill`／`aos node check` 暫定／b 掛在 aos node 下／c 這輪不加人手指令）；巢狀資料夾上層 git 提交排除下層由誰何時寫 `info/exclude`（a `aos node new` 建下層時寫進上層／b 上層標準配備每次提交前寫／c 走查手動加）；agent 由人手或 cron 跑時沒通道、自跑 once 掛不了（a 功能受限不管／b 讀 `daemon_socket` 走無憑證路線 parent_id 必填／c 設定檢查改成提醒）。

## T3 第四輪
- P-207、P-210 已縮；P-210 原驗收句拿掉了，交 T1 決定是否搬進 V-03（或 A-102）。

## T5（完成）
- 交 T3：P-605 拿掉「任務不能另切帳號」、aos-clean 改屬標準配備；P-601 登記樹改上下層樹；B-631 寫清每程序上限的值從哪來（備援時 daemon 的 `cgroup_*` 回 `unsupported`，kernel 分的額度到不了成員）。
- 交 T4：S-307 或 S-301 接住 P-808 的路由成環（`routing_loop`）、未授權（`work_not_authorized`）、在途不改投別站；S-301 接住 P-505 驗收（wire 格式不變、不能靠改 pool 名繞份額、共用 scope 的池遇 429 一起冷卻）。之後 T5 縮 P-808、P-505。
- 交 T1 V-03：成員在 kernel 資料夾內登記不帶 parent_id、在外面帶覆蓋、資料夾上層不同意只隔離那一項；daemon 走 cgroup 備援時資源任務不報套用失敗、成員記 `fallback:true`、新派工照額度放行；掛載紀錄還在跑不重掛、daemon 重開後查不到也沒結果和 `.err` 記 unknown；沒被叫醒過的成員不寫失聯事項；範本任務帶 `user` 照收。
- 疑點：備援時 kernel 分的 CPU／記憶體額度（a 只記帳不擋 暫定／b daemon 開格換算成每程序上限／c kernel 寫進成員設定由成員 tick 自設）；不在 daemon 底下的成員怎麼判失聯（a 不判 暫定／b 看摘要 `observed_at_ms` 超過 `member_stale_ms`／c 要求 kernel 成員一定要在 daemon 登記）；標記建了 `node.mount` 還沒送出就當掉（a 記 unknown 暫定／b 同次 daemon 啟動且診斷未淘汰時查不到准重掛）。
