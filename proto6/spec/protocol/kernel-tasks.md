# 預設 kernel 範本：最小任務

← [協議入口](README.md)｜[node](../settled/protocol/node.md)｜[daemon](../settled/protocol/daemon/README.md)｜[資源](resources.md)｜[走查](../cli.md)｜[裁定](../../notes/2026-09-29-verdicts.md)

〔使用者方向 2026-09-30，第十八批〕本篇是 aos 附的**預設 kernel 範本**：kernel 是裝了下列任務的 node。任務種類、資源與排程規則都是範本的預設，各 kernel 可以換掉、刪掉，或登記自己的任務種類與資源名稱（[T-06](../terms.md)）。本篇只定範本的檔案、argv、欄位與結束碼；行為以 [scheduling](../scheduling/README.md)（S-201～207、S-401、S-405、S-406）、[daemon](../settled/daemon.md) 與 [tick](../settled/tick.md) 為正本。〔使用者方向 2026-09-30，第十九批〕kernel 範本是掛在 tick 上的「其他掛載」，靠標準配備（git 提交、收件、投件、once、通道等）運作，保證以標準配備全掛為前提（[B-626](../settled/tick.md)、[B-629](../settled/tick.md)）。

## P-800．共同契約〔第十二批裁定；工程預設〕

每個 module 一項任務（[B-620](../settled/tick.md)）：check、members、resources、work、LLM forward、LLM pool、usage、schedule，另有 custom 的 aos-clean；它的輸出及到期間隔依 [P-605](ops.md)。各用 node inst 的帳號（範本任務不帶 `user`，[B-620](../settled/tick.md)）、直接開檔讀設定；stdin 不讀、stderr 診斷，除 clean 外的任務 stdout 空。`--node N` 可省，預設 cwd；tick 在 node 根跑任務。在 tick 裡一律繼承並核對 `AOS_TICK_LOCK_FD`（[B-602](../settled/tick.md)），提交交給 tick。〔使用者方向 2026-09-30，第十九批，追答 10〕任務帶別的 `user` 時，由 tick 一直握著鎖、經 helper 的「以指定帳號開程序」開它，任務照樣繼承同一個鎖 fd、照樣核對；不經 `node.mount`，沒有 helper 時那一項依 [B-620](../settled/tick.md) 回 125（功能受限）。有 `AOS_TICK_LOCK_FD` 卻核對不過就回 125、不改檔，不改成自己取鎖（開它的 tick 還握著鎖）。

任務把完整請求／回應放追蹤的 `.aos/outbox/{requests,responses}/<id>.json`，把已消費原件逐 byte 複製到 `state/messages/{requests,responses}/<id>.json`。收件與派出的先後（組提交後才投件、才刪原件）屬標準配備，以 [B-623、B-624](../settled/tick.md) 為正本，封套見 [P-206](../settled/protocol/node.md)。〔使用者方向 2026-09-30，第十九批〕要找 daemon 的任務照 P-801 找 socket、走通道；once 由 module 經通道 `node.mount` 掛上、`node.kill` 砍掉（[B-613](../settled/daemon.md)），當格新材料先提交、下一格才掛（[S-401](../scheduling/operations.md)）。不在任務中等工具／HTTP；取消時同步等 `node.kill` 收尾到全空是唯一例外，上限是 daemon 的 `shutdown_grace_ms`（[B-203](../base/execution.md)）。

0 本步完成或等待；2 用法／設定錯；75 鎖忙；125 無法開始；1 無法處理或保存；提交／還原故障回 3 並擋格。個別請求失敗能保存就繼續。沒有變動不 commit、不刷新時間欄；程序回 0 不表示所有成員可派工。

## P-801．設定與持久成員〔B-603、S-203、P-501；工程預設〕

`config/kernel.json`（[schema](schemas/kernel-config.schema.json)）必填 `version:1`；可選 `daemon_socket`（絕對路徑）與 `scan_interval_ms=60000,scan_batch_limit=64,usage_max_age_ms=60000,max_active_members=64,member_stale_ms=600000`，數值皆正整數。`quota_file` 可指父層提供的 res-quota；頂層可指本地設定，這份只是分配政策（[S-205](../scheduling/admission.md)）。無父配置時可省，不虛構無限額度。node 事項寫自己的 `.aos/attention/`。

〔使用者方向 2026-09-30，第十九批；取法為建議預設〕**要找 daemon 的任務怎麼找**（members、schedule、resources、work；pool 另照 [P-408](work.md)：它的掛載不帶 `parent_id`，只能走通道，沒有通道變數就報 `no_channel`、回 125，不走下面第二點的無憑證路）：

- 本格有 `AOS_TICK_TOKEN`（daemon 開的格，[B-612](../settled/daemon.md)）：一律用環境變數 `AOS_DAEMON_SOCKET` 那個 socket，設定的 `daemon_socket` 這時不用。只有收憑證的 method（`node.register`、`node.unregister`、`node.wake`、`node.mount`、`node.kill`、`node.send`、`node.take`，[P-117](../settled/protocol/daemon/channel.md)）帶 `token`；`daemon.info`、`node.show`、`node.provision` 等其他 method 不帶（帶了回 `invalid_params`），照 socket 對面的帳號授權（[P-103](../settled/protocol/daemon/startup-and-ipc.md)）。憑證只在開這一格的 daemon 有效。
- 沒有憑證（cron 或人手直接跑，[B-627](../settled/tick.md)）：用設定的 `daemon_socket`，省略時讀 `AOS_DAEMON_SOCKET`；請求不帶 `token`，daemon 照 socket 對面的帳號授權（[P-103](../settled/protocol/daemon/startup-and-ipc.md)）。
- 都沒有：沒有 daemon 可找。要 daemon 的那幾步（登記、叫醒、掛行程、佈建、查實際值）這格不做，狀態檔照留、stderr 印一行，下一格再試；讀收件、記帳、寫摘要等本地部分照做。這只是功能受限（[B-629](../settled/tick.md)），不寫事項。

| 欄位 | 管什麼 |
|---|---|
| `scan_interval_ms`、`scan_batch_limit` | 低頻補查：每隔多久、每批幾個成員（[S-202](../scheduling/admission.md)） |
| `usage_max_age_ms` | 用量多舊要重量，也是沒有 project quota 時磁碟定期量的間隔（P-804） |
| `daemon_socket` | 沒有通道時找 daemon 用的 socket（見上） |
| `max_active_members` | 同時叫醒的成員上限 |
| `member_stale_ms` | 叫醒後多久沒完成新格就寫失聯事項（[S-206](../scheduling/admission.md)） |

成員多時這些欄位怎麼調，見 [S-202](../scheduling/admission.md)。

`config/members.json`（[schema](schemas/kernel-members.schema.json)）為 `version:1,revision,members`；revision 正整數，內容改就加一。每項：

| 欄位 | 意思 |
|---|---|
| `id` | 本 kernel 唯一短名 |
| `node_id` | 成員資料夾的絕對路徑（登記只收資料夾，[B-606](../settled/daemon.md)）。〔第十九批〕建議放在本 kernel 資料夾之內，預設上層就是本 kernel；放在外面時以覆蓋登記（[S-202](../scheduling/admission.md)） |
| `identity_grant` | daemon 身分額度（寫法與包含判定見 [B-606](../settled/daemon.md)）；成員 inst 的 user 須在其中 |
| `interval_ms`（可省） | 週期；子 kernel 建議 1000，逐次放行的 agent 省略 |
| `provision`（可省） | 不超父範圍的 daemon 授權 |
| `quota` | 完整 res-quota，node_id 對本項、seq 隨配額遞增 |

重複 id／node_id、登自己、登到自己的上層（成環）或指到單檔，由 check 驗、schema 不擋。members 提供初始配額；`state/resources/<id>.quota.json` 保存期望配額，`state/kernel/resources.json` 記套用結果。`kernel.quota.set` 的 params 是 inst、stdin 指 res-quota；核權後只更新期望配額，不改 config。兩處怎麼選版見 [S-205](../scheduling/admission.md)。

## P-802．增刪成員與按需同步〔B-603／604、B-606、P-104；工程預設〕

```text
aos-kernel-members [--node N] add --from F
aos-kernel-members [--node N] rm ID
aos-kernel-members [--node N] ls
aos-kernel-members [--node N] sync
```

人手對應 `aos kernel members add N --from F`、`rm N ID`、`ls N`、`sync N`。F 是任意可讀路徑的單項 JSON。add/rm 只持鎖提交清單，stdout 印 ID；同 ID 同內容不變，rm 不刪資料／帳號。ls 印已提交清單。這三項不掛 tick、不叫 daemon。

sync 讀清單、`state/kernel/sync.json`（[schema](schemas/kernel-sync-state.schema.json)）與 daemon.info，經通道登記、解除（找 daemon 照 P-801）。何時登記、帶不帶 `parent_id`、怎麼核對 `node.register` 回應的 `{node_id, parent_id, registration_id}`、失敗怎麼隔離、移除成員、換上層兩條路與上層收小授權，都以 [S-202](../scheduling/admission.md) 為正本。

sync.json 欄位：`boot_id`、`members_revision` 是上次成功同步時的 daemon 啟動 ID 與清單版本；`synced` 每項是已確認的登記（`registration` 是送出的登記內容，〔第十九批〕`parent_id` 只在覆蓋時有）與 `bootstrap_pending`；`pending_remove` 是待解除的 node；`retry` 是失敗成員的下次重試時間。

## P-803．何時叫醒〔S-201～204、P-307；工程預設〕

`aos-kernel-schedule [--node N]`，人手 `aos kernel schedule N`。讀 members、同步／資源結果、成員收件檔名、已提交摘要與 node.show，寫 `state/kernel/schedule.json`（[schema](schemas/kernel-schedule-state.schema.json)），〔第十九批〕經通道 `node.wake` 叫醒（找 daemon 照 P-801）。什麼算 ready、叫誰、補查怎麼輪、新格與失聯怎麼判，以 [S-201](../scheduling/admission.md)、[S-202](../scheduling/admission.md)、[S-204](../scheduling/admission.md)、[S-206](../scheduling/admission.md) 為正本。recheck 的 argv 對應 `aos kernel schedule recheck`，執行結果放待送區，交標準配備投出。

〔使用者方向 2026-09-29，第十七批；審稿必-4〕給 kernel 的一般回話（`agent.say`）也由這個任務收，只記錄（行為見 [S-406](../scheduling/operations.md)）：原件照 P-800 複製到 `state/messages/requests/<id>.json`；另寫一筆 `state/kernel/history/<id>.json`（形狀沿 [agent-history](schemas/agent-history.schema.json)：`input_id` 是這則 agent.say 的 id，`source_path` 填 `state/messages/requests/<id>.json`）；序號存 `state/kernel/sequence.json`（形狀沿 [agent-sequence](schemas/agent-sequence.schema.json)），在鎖內遞增、與 history 同組提交。指令 stdout `{"accepted":true}` 當確認回件。agent 之間的問答延後（[P-008](README.md#p-008)）。

schedule.json 欄位：`next_seq` 是下一個要配的 `ready_seq`；`scan_after`、`next_scan_ms` 是補查游標（上次掃到的成員短名）與下次補查時間；`members[]` 每項記 `ready_seq`（不 ready 為 null）、`due_ms`、讀摘要時釘的 `summary_commit`（成員走 git 備援時沒有 commit，記 null）與 `wake_mark`。〔審稿新必-2〕`wake_mark` 是 wake 回應的 `registration_id` 與 `tick_seq` 連同叫醒時間；沒叫醒過為 null。

同組寫 `.aos/summary/summary.json`；ready 表示本地可推進，due_ms 取最近重試／掃描／冷卻，只有等待結果則 false。標準配備在提交後發布 `.aos/summary/published.json`（[B-624](../settled/tick.md)、[P-307](messages.md)），上層只開摘要權時讀此檔；沒有另列發布任務。

## P-804．分配與量測〔P-500～507、S-203／204；工程預設〕

`aos-kernel-resources [--node N]`，人手 `aos kernel resources N`。讀 members／父額度／成員摘要，寫期望配額與資源狀態檔，經 daemon 佈建（[B-609](../settled/daemon.md)）並以 `node.show` 核對實際值。選版、套用時點、調高調低、走 cgroup 備援與故障，以 [S-205](../scheduling/admission.md) 為正本；公開檔的發布時點見 [S-203](../scheduling/admission.md)。

〔審稿建-15〕**父配額公開檔**：`public/quotas/<id>.json` 是 `state/resources/<id>.quota.json` 的發布副本（格式 [P-501](resources.md)），由父的資源任務發布，發布時點依 [S-203](../scheduling/admission.md)。子的 quota_file 指此檔；只讓該子讀、只有父能寫。佈建的 limits 只放已啟用 module 的 CPU／memory／pids，對照見 [P-503](resources.md)。

`state/kernel/resources.json`（[schema](schemas/kernel-resource-state.schema.json)）是 kernel 自己的資源狀態檔：

| 欄位 | 意思 |
|---|---|
| `members[].member_id`、`quota_seq`、`applied`、`error` | 每個成員套用到哪一版配額、成功與否；失敗 `applied=false` 並附錯誤 |
| `members[].fallback`（可省） | 〔第十九批，暫定〕daemon 走 cgroup 備援、佈建回 `unsupported` 時為 true：這版配額已採用、只記帳，沒寫進 cgroup（S-205） |
| `members[].over_limit`（可省） | 〔Q17〕調低上限時量到現用量已超過新上限，記一筆 `{resource,limit,current,observed_at_ms}`；〔暫定〕resource 只記 memory 或 pids；下次套用新值時換掉 |
| `over_allocated`（可省） | 〔Q8〕本層分到的額度小於已分給成員的合計時，列出超分的資源名，並寫一件事項 |

這幾個欄位各擋哪些新派工、不擋什麼，見 [S-205](../scheduling/admission.md)。

同一 module 接 `kernel.quota.set`／`kernel.usage.measure`。後者對應 `aos kernel usage measure`，重測後把結果放指令 stdout，再按 work-result 回件。量到的資料存 `state/resources/<id>.usage.json`；成員 summary.usage 替換觀測，不重加孫層。沒有 project quota 時磁碟也由本任務定期量，間隔與範圍見 [S-207](../scheduling/admission.md)。

## P-805．壞設定與重驗〔A-102、P-203／207、P-601；工程預設〕

設定何時生效與怎麼改的原則（含 tick 裡的任務不改 config 的軟性原則）見 [A-102](../agent/configuration.md)；事項怎麼寫見 [S-405](../scheduling/operations.md)。範本裡 check 是 kernel 類（〔使用者方向 2026-09-30，第十八批〕，[B-626](../settled/tick.md)）。

```text
aos-kernel-check [--node N]
aos-kernel-check [--node N] --validate-only
```

人手 `aos kernel config check N`。直接讀 inst／tasks 及已裝 module 的 config，驗 schema、引用、重名、父額度、路由與池；不發 HTTP、不掛行程、不 resume。validate-only 供 caller 持鎖驗工作樹，不再取鎖、不寫；0 合法、2 不合法、125 讀不到。〔使用者方向 2026-09-29，第十七批〕**一般 check 只要跑完、把問題寫進下述 config-state 就回 0**，設定有問題也是 0（問題看 issues）；只有檢查自己跑不起來才非 0：用法錯 2、鎖忙 75、讀不到或前置不符 125、問題紀錄寫不出 1。validate-only 不寫紀錄，照舊用 0／2 告訴持鎖的 caller（例如 [P-210](../settled/protocol/node.md) 的 resume）能不能採用。

一般 check 寫 `state/kernel/config-state.json`（[schema](schemas/kernel-config-state.schema.json)）的 issues：path、issue_id、resolved。設定無效時擋什麼、不擋什麼（check 失敗不擋收結果）以 [S-205](../scheduling/admission.md) 為正本。修好後重驗、提交設定狀態；人或 agent 確認修好後用 `aos attend done N ID` 標完成。

## P-806．工具 once module〔P-400～404、Q1／Q2；工程預設〕

`aos-kernel-work [--node N]`，人手 `aos kernel work N`。接 `kernel.work.submit`，params.argv 對應 `aos kernel work submit`，stdin 指 work-request 業務 JSON。核對來源／回址／成員身分，保存原件、材料與序號，寫 `state/work/<attempt_id>/kernel.json`（[schema](schemas/kernel-work-state.schema.json)）；目錄名是 `<前綴>-<attempt_id>`，前綴取自**配出這個 attempt_id 的 node**（[P-402](work.md)）。

`phase` 的 `queued`／`prepared`、何時掛、掛上後怎麼收結果與回件，以 [S-401](../scheduling/operations.md) 的「預設 kernel 範本代掛工具的步驟」為正本；掛載參數見 [P-402](work.md) 的表（`parent_id` 填發起成員）。收齊後的 work-result 放指令 stdout，外層 RPC 指令結果交標準配備投回。

kernel.json 欄位：

| 欄位 | 意思 |
|---|---|
| `request_id`、`seq`、`phase`、`boot_id`、`work_dir`、`finished_at_ms` | 原請求 ID、本 kernel 序號、工作進度（不是任務拆分）、接件 boot、工作目錄、完成時間；不重存請求 |
| `submitter_uid` | 接件時原請求檔的擁有 UID，取消核權用 |
| `owner_exec_uid`（可省） | 接件時記下、接件那一項任務實際的有效 UID（範本任務不帶 `user`，就是 node inst 的執行帳號；〔暫定〕任務帶了自己的 `user` 時是那個帳號），取消核權的第二種主人（[B-203](../base/execution.md)） |
| `attempt_allocator`（可省） | 配出 attempt_id 的 node；省略＝材料的 node_id。讀目錄時核對前綴＝它的雜湊（P-402） |
| `llm`（可省） | 〔審稿必-9〕LLM 工作才有：pool 任務維護的預留（P-811） |

〔使用者方向 2026-09-29，第十七批〕同一 module 也接 `work.cancel`（格式見 [work P-411](work.md)）；核權、排隊中拿掉、在跑的經通道 `node.kill` 砍掉（[B-613](../settled/daemon.md)）以 [B-203](../base/execution.md) 為正本，`phase` 用 `canceling` 記「已要求取消、還沒收尾」。

## P-807．中斷與恢復〔B-603、B-613、P-110、C-03；工程預設〕

（第十八批：判斷規則併入 [S-401](../scheduling/operations.md)。）檔案位置：啟動標記是 ignored 的 `.aos/jobs/<attempt_id>/launch-started`，保留到整件工作可清理；單檔目標沒開始的旁檔是 `<inst>.err`（行為見 [B-613](../settled/daemon.md)，格式見 [P-110](../settled/protocol/daemon/provision-and-runner.md)）。補投同 ID、同 bytes 見 [B-503](../base/transport.md)。

## P-808．LLM 路由表〔P-303、S-301；工程預設〕

`config/llm-routes.json`（[schema](schemas/kernel-llm-routes.schema.json)）為 `version:1,routes`；每項 `pool_id,model,next_node,next_pool,allowed_origins`。pool_id 本層唯一；next_node=null 用自己的池，其餘送下一個 kernel，仍是 `llm.chat`。同名池以 node＋pool 分開。

allowed_origins 列 `{node_id,via_node,via_uid}`：原發起者、明授的投件者 node 與非 root UID；直投時 `node_id` 與 `via_node` 相同。錯誤碼 `work_not_authorized`、`pool_not_found`、`routing_loop`。〔第十九批〕怎麼驗來源、成環與在途不改投別站，以 [S-307](../scheduling/llm.md) 的「轉交的路由與授權」為正本。

## P-809．LLM 轉交 module〔Q1／Q2、S-302；工程預設〕

`aos-kernel-llm-forward [--node N]`，人手 `aos kernel llm forward N`。一項任務收 `llm.chat`／結果、驗 route、排 seq／份額、準備轉交與回件；交標準配備投出、清原件。

追蹤 `state/work/<attempt>/` 的 request、forward-state、轉交請求／結果與最終 response；[forward-state schema](schemas/kernel-forward-state.schema.json)。遠端請求配新 forward_id、reply_to=本 kernel，method 仍 `llm.chat`，params 是對應 inst；stdin 指改 pool=next_pool 的新業務 JSON，其餘 origin/job/attempt/messages/model 保留。回件核對後換回原 RPC id；外層 work-result 的執行 node／ID 也須對應本跳，不直接冒用下游指令結果。

本池不投自己的收件區：本 module 保存已接納材料，pool 任務在後組讀已提交材料。池提交結果後，forward 下一格生成原請求回件。

份額扣在誰身上、何時占與還，依 [S-302](../scheduling/llm.md)、[S-304](../scheduling/llm.md)。

## P-810．用量收集 module〔LLM 與工具兩條路線；工程預設〕

`aos-kernel-usage-collect [--node N]`，人手 `aos kernel usage collect N`。讀直接成員已提交的 `state/agent/usage/<request_id>.json`（[schema](schemas/agent-usage.schema.json)），原格式存 `state/resources/member-usage/<member_id>/<request_id>.json`，觀測記 `state/kernel/usage-collect.json`（[schema](schemas/kernel-usage-state.schema.json)，狀態值含 missing／stale／invalid；成員有 git 時記 `source_commit`，〔第十九批〕走 git 備援時 `source_commit` 為 null、改記成員最新完成紀錄的 `source_journal_seq`）。收集、替換、缺值與去重的行為依 [S-207](../scheduling/admission.md)。

## P-811．池與共享窗口〔P-405～408、S-301～304；工程預設〕

池就是這個 node，代發是 tick 任務，沒有常駐池 daemon；key 的放法與保護範圍依 [S-301](../scheduling/llm.md)。`config/llm-pools.json` 沿 [llm-config](schemas/llm-config.schema.json)，含 endpoint/model/quota_scope/key_ref/max_attempts/schedule。窗口、預留、token 估算與結算依 [S-302](../scheduling/llm.md)；重試與冷卻依 [S-303](../scheduling/llm.md)；unknown 依 [S-304](../scheduling/llm.md)。以下只定格式，只有 `schedule:aos` 的池讀 llm-limits（[llm-work P-405](llm-work.md)）。

`config/llm-limits.json`（[schema](schemas/kernel-llm-limits.schema.json)）為 `version:1,scopes`；每 scope 一項：

| 欄位 | 意思 |
|---|---|
| `quota_scope` | 共享限制的名字 |
| `concurrent_requests`、`window_ms`、`requests_per_window`、`tokens_per_window` | 並行上限、固定窗口長度、每窗口請求數、每窗口 token 數，皆正整數 |
| `unknown_hold_ms`（可省） | unknown 請求占本 scope 份額多久；省略＝該請求的 `timeout_ms`，0＝不占 |

預留存在 `state/work/<attempt>/kernel.json` 的 `llm` 欄（[kernel-work-state](schemas/kernel-work-state.schema.json)）：`pool_id,quota_scope,reserved_tokens,reserved_at_ms,retry_at_ms`，每次 HTTP 有不同 attempt。

`aos-llm [--node N] --config F`：一項任務收結果、更新窗口並準備材料，只對先前已提交的 HTTP 材料，經通道 `node.mount` 掛上 `.aos/jobs/<attempt>/` 的 once（[S-307](../scheduling/llm.md)、[P-402](work.md)）。

`state/llm/pool-status.json`（[schema](schemas/kernel-pool-status.schema.json)）記各 scope 的窗口、冷卻及已知／unknown 占用，同 attempt 只算一次，待啟動的預留也算 active；無變化不刷 observed_at_ms。

## P-812．唯讀查詢〔P-106；工程預設〕

`aos-kernel-pool-usage [--node N]` 對應 `aos llm pool usage N`。只讀已提交 pool-status，stdout JSON＋LF，stderr 診斷／年齡；不量測、不 wake、不讀 key。0 成功、2 用法錯、1 缺檔或不可讀。

`aos node ls`／show 讀 daemon.info／node.ls／node.show 的 boot_id、registration_id、registered、last_tick（含 `tick_seq`）。重啟、接續與換 boot 怎麼看以 [B-603](../settled/daemon.md) 為正本；程序結束碼要有 last_tick 證據，掛載行程查不到不是重掛許可（[S-401](../scheduling/operations.md)）。

## P-813．建立 agent 的兩條路〔第十一、十二批裁定；工程預設〕

兩條份額路線（kernel 全管、kernel 不管）與直連檔以 [S-301](../scheduling/llm.md) 為正本，各欄位填法也在那張表；範本另要照下面配權限。

兩種工作可分別選路線。父須能列成員收件與讀摘要；僅開摘要權時讀 `.aos/summary/published.json`，用量另授讀權。轉交要開相應 requests／responses 權限，下一站明授 origin/via。〔第十九批〕自跑工具經通道 `node.mount` 掛（[P-402](work.md)），要 jobs 路徑權限；資源歸掛的那個 tick 或它指定的下層（[B-613](../settled/daemon.md)），工具不自選。

OS 帳號、chown 與多帳號交接用的群組（建群組、加成員、改檔案群組）走 daemon 佈建的固定動作（[B-609](../settled/daemon.md)），首版不用 ACL。父配額只讓該子讀，不給子寫。

## P-814．完整範本與走查〔B-603、[inst 目標](../base/inst.md#inst-目標檔案或資料夾)；工程預設〕

```text
aos node new /srv/aos/top --template kernel --user 1000 --socket /run/user/1000/aos.sock
```

〔第十九批〕`--socket` 可省，省略時 `config/kernel.json` 不寫 `daemon_socket`（P-801）。

建立普通 git node、初始 commit、requests／responses／work／public／`.aos/jobs/`／`.aos/attention/`，不覆蓋既有目標、不試 HTTP。[完整 JSON](examples/kernel-tasks/kernel-template.minimal.valid.json) 與 [schema](schemas/kernel-template.schema.json) 的 files 是實際產物，不另存 template 容器；包括 `.aos/inst.json`、`.aos/tasks.json`、設定與 gitignore。

任務表共 **9 項**，每項是 inst（含 `_metainfo`）加 id／kind／needs／methods；group 省略、各自一組，needs 全空。外層 `_metainfo` 是 aos-tasks 第 1 版。〔使用者方向 2026-09-30，第十九批，疑點裁定 4〕範本任務不填 `user`，照 node inst 的帳號跑；任務可以帶 `user`，由標準配備的切換使用者開（[B-620](../settled/tick.md)）。〔使用者方向 2026-09-29，第十七批〕`methods` 是該任務處理的檔案請求（[node P-202](../settled/protocol/node.md)）；下表沒列 method 的任務不收請求，別人投來沒人宣告的 method 由標準配備的收件回 -32601（[B-623](../settled/tick.md)）。

| id | kind | 程式（cwd 為 node 根） | needs | methods |
|---|---|---|---|---|
| check | kernel | aos-kernel-check | 無 | 無 |
| members | kernel | aos-kernel-members sync | 無 | 無 |
| resources | kernel | aos-kernel-resources | 無 | kernel.quota.set、kernel.usage.measure |
| work | kernel | aos-kernel-work | 無 | kernel.work.submit、work.cancel |
| forward | kernel | aos-kernel-llm-forward | 無 | llm.chat |
| pool | kernel | aos-llm --config config/llm-pools.json | 無 | 無（讀 forward 已接納的材料） |
| usage | kernel | aos-kernel-usage-collect | 無 | 無 |
| schedule | kernel | aos-kernel-schedule | 無 | kernel.schedule.recheck、agent.say |
| clean | custom | aos-clean --config config/clean.json | 無 | 無 |

〔使用者方向 2026-09-30，第十八批；審稿新必-1〕**範本任務之間都不設 needs**，理由見 [S-205](../scheduling/admission.md)。先後照表的位置（〔暫定〕kind 分段照 [B-620](../settled/tick.md)），每項各自一組，後面的任務讀得到前面已提交的結果。check 是 kernel 類；clean 是 custom 類、排最後，〔第十九批，疑點裁定 2〕但 aos-clean 本身屬標準配備（[B-626](../settled/tick.md)、[B-629](../settled/tick.md)）。kernel 可以在範本上加自己的任務，自訂種類〔暫定〕寫成「類別.名稱」（B-620）。

範本 task 用 `stderr:{"$opt":"inherit"}` 讓診斷交 tick。沒有本地池可刪 pool／池設定；〔審稿必-6〕只裝 pool、不裝 forward 時，pool 要自己宣告 `llm.chat`，否則別人投來的 `llm.chat` 由標準配備回 -32601（[S-307](../scheduling/llm.md)）。全體轉交可移除 usage。agent 範本有 agent 與 clean 兩項。清理間隔在 config/clean.json，預設一天，由 aos-clean 自己記時間。

daemon roots 填頂層 node、身分額度與 interval_ms=1000；啟動、重啟與逐層重登以 [B-603](../settled/daemon.md) 為正本。〔使用者方向 2026-09-30，第十九批〕成員資料夾建議放在頂層資料夾之下（例如 `/srv/aos/top/a`），預設上層就是 top、不用覆蓋；top 的 git 自動排除這些下層資料夾（[B-628](../settled/tick.md)）。成員、routes、endpoint/model 按實際部署補齊，空清單不授權 agent。正式回話與查 context 由 [agent 篇](agent-tasks.md) 接。

清理資格與保留期以 [B-404](../base/storage.md) 為正本，範本資料怎麼遍歷見 [P-606](ops.md)，unknown 占用何時釋放見 [S-304](../scheduling/llm.md)，只記錄的回話見 [S-406](../scheduling/operations.md)。範本要清的檔案另含本地動作的 `.stdout` 檔（`state/messages/requests/<id>.stdout`）；`state/kernel/sequence.json` 不清。

## P-815．格式驗收〔P-007〕

[範例](examples/kernel-tasks/) 依同名前綴驗 schema。反例涵蓋成員額度含 root、批次／窗口為零、相對路由、設定狀態錯型、boot 非字串、零序號、applied 非布林、未知工作階段、把缺量當零、unknown 負數、範本缺任務表。〔第十九批〕範本任務帶 `user` 不再是反例（B-620）。〔第十八批〕本篇 schema 都是持久檔或檔案 RPC，一律放寬：多一個不認得的欄位照收（[P-007](README.md)）；成員指到單檔、成環改由 check 驗。

正例全過、反例全拒；`bash wf/tools/wf-lint.sh proto6` broken=0。格式不代替授權、跨檔配對、重啟與實際 HTTP 驗收。
