# kernel 的最小預設任務

← [協議入口](README.md)｜[node](node.md)｜[daemon](daemon.md)｜[資源](resources.md)｜[走查](../cli.md)｜[裁定](../../notes/2026-09-29-verdicts.md)

待實作；kernel 是裝了下列任務的 node，格式為預設。

## P-800．最少需要什麼〔來源：裁定第五～九批、最新三點；工程預設〕

七支新任務程式：`aos-kernel-check`、`aos-kernel-members`、`aos-kernel-schedule`、`aos-kernel-work`、`aos-kernel-resources`、`aos-kernel-llm-forward`、`aos-kernel-usage-collect`；另有唯讀 `aos-kernel-pool-usage`。沿用 `aos-llm`、`aos-llm-call`、`aos-work`、`aos-clean`。範本同時列轉交／用量收集，按成員路線分工，不重算。

以下新任務共同契約：用 node user；stdin 不讀、stdout 空、stderr `代號: 白話`；`--node N` 必填絕對路徑，cwd／環境沿 P-203，無 key 環境。設定讀本格 commit 或 P-805 有效版本。`--in-tick` 核對鎖 fd，由 group 提交；直接跑自行持同把非阻塞鎖，拒 dirty／擋板，自己提交。每項獨立 group；每個 phase 各自提交，不能略過前置。

退出：0 本步完成（含等待／隔離壞項）；2 用法錯／缺必要設定；75 鎖忙；125 無法開始；1 自身處理失敗；直接模式提交／還原故障回 3，按 P-205 擋格。個別成員／請求失敗存證後繼續，存不下才讓任務失敗。訊號看 wait；非零不授權重做。沒變動不 commit，boot 不變、無新事件／量測時不刷時間欄。

**驗收：**直接 exec 可用；結果不被 wrapper 結束碼蓋掉，閒置不製造空提交。

## P-801．設定與持久成員〔來源：B-603、S-203、P-501；工程預設〕

追蹤 `config/kernel.json`（[schema](schemas/kernel-config.schema.json)）：`version:1,daemon_socket,attention_dir` 必填；可選 `scan_interval_ms=60000,scan_batch_limit=64,usage_max_age_ms=60000,max_active_members=64`，都是正整數。可選 `quota_file` 絕對路徑讀父 res-quota；頂層可指自己 config 配額；無父配置時可省，LLM 總額用本地 scope，OS 沿實際父限／module 規則，不虛構無限。socket／attention_dir 也用絕對路徑。

追蹤 `config/members.json`（[schema](schemas/kernel-members.schema.json)）：`version:1,revision,members`。revision 正整數，內容改了就加一，不能同版異內容。每項：

| 欄位 | 意思 |
|---|---|
| `id` | 本 kernel 內唯一短名，只用來命名本地檔 |
| `node_id` | 成員資料夾絕對路徑，不由目錄位置推父子 |
| `identity_grant` | 沿 daemon 身分額度；inst user 必須存在且在其中 |
| `interval_ms`（可省） | 登記給 daemon 的週期；子 kernel 建議 1000，agent 通常省略 |
| `provision`（可省） | 沿 daemon 授權，不能超父範圍 |
| `quota` | 完整 res-quota，node_id 必須等於本項；seq 隨配額改動遞增 |

不可重複 id/node_id、登自己、once 或角色。`quota.resources:{}` 不解除父限。members 是期望配置正本；`state/resources/<id>.quota.json` 是 res-quota 副本，`state/kernel/resources.json` 是套用證據。resources.set 驗配置權／seq，同組更新 members/revision／配額副本、提交 accepted；下格才採用，相關新派工暫緩，舊快照不蓋新副本，成員不能自擴額。

**驗收：**清單可重建樹；同版異內容、重複 node、錯指配額都拒用。

## P-802．增刪成員與少量同步〔來源：最新「不要每格重登」、B-603／604、P-104；工程預設〕

```text
aos-kernel-members --node N add --from F
aos-kernel-members --node N rm ID
aos-kernel-members --node N ls
aos-kernel-members --node N --phase sync [--in-tick]
```

人手 `aos kernel members add N --from F`、`rm N ID [--yes]`、`ls N`、`sync N`；rm 先依 H-003 確認再呼叫底層。F 是單項（驗 members.items），相對 cwd；同 ID 同內容無變動，修改走設定匯入。add/rm 持鎖提交清單，stdout 印 ID；rm 不刪資料／帳號。ls 讀 HEAD 印 kernel-members JSON。三者不掛 tick、不呼叫 daemon。

sync 讀清單、`state/kernel/sync.json`（[schema](schemas/kernel-sync-state.schema.json)）、IPC，寫同步狀態／事項。每格只先 `daemon.info {}` 取 boot_id。boot_id 相同、revision 相同且沒有到期重試時，**不重登也不列整棵樹**。換 boot 重登正常直接成員；清單改版只處理差異，補查遺漏只修該筆。同一連線先 info，完成一批後再 info；斷線重連先 info。boot 變了中止，下格重判，不假設 register 回 boot_id。

狀態存 boot/revision、已確認登記、bootstrap_pending、待解除項與 retry_at_ms；逐項成功才更新，壞項 60 秒後重查。清單外框錯依 P-805 回舊配置；單項格式、路徑、user 或權限錯則隔離該項、寫 `member_invalid`，正常成員仍提交。壞項不當移除，舊登記保留但不排新格，修好再恢復。首次／重啟登記標 bootstrap_pending，P-803 核資源後叫醒一次以重建下層；相同重登不再叫醒。

移除者不再排程，unregister 排空子樹；未清保留 pending_remove／占用。更新依 daemon 暫停／全空要求，busy 留事項待維護，不自動殺工作。RPC 失聯／group 還原先查 node.get，不重做工作。

**驗收：**1000 次閒置只有 info；換 boot／改成員／移除／壞項僅做必要操作。

## P-803．何時叫醒〔來源：S-201～204、P-307；工程預設〕

`aos-kernel-schedule --node N [--in-tick] [--publish]`；人手 `aos kernel schedule N`。needs members／resources-apply。讀有效 members、sync／資源證據、成員 requests/responses 檔名、已提交 summary 及 node.get；寫 `state/kernel/schedule.json`（[schema](schemas/kernel-schedule-state.schema.json)）、kernel.recheck 原件／回件、事項，經 IPC wake。

首格分批掃，平常處理到期、bootstrap 及已驗 recheck；每 scan_interval_ms 補查最多 scan_batch_limit 個，短名排序、scan_after 記游標，輪完重頭，不讀 history。recheck 本格提交原件／判斷，後格才送已提交 accepted／清原件。缺摘要不當 idle，留事項並依收件／bootstrap 判斷。

有收件、summary.ready、due 到期或 bootstrap 才 ready；新 ready 配遞增 ready_seq，等待保位，按序選不超 max_active_members 者。paused/stopping 不 wake，running/pending 不重複叫。保存 wake 當時 last_tick.ended_at_ms，等新格完成再讀摘要／收件，不反覆用舊 ready。wake 後提交失敗，下格以 node.get 合併判斷；bootstrap 確認一格開始才清。interval 是允許週期自跑，需逐次放行的 agent 不設；seq 排先後，時間只判到期。

同組寫自己的 P-307 `summary.json`：ready＝本地可推進，due_ms＝重試／掃描／冷卻最近到期，status 沿 P-307；只等結果而無新件則 ready=false，不因有成員就 ready。後組 `--publish` needs schedule，只把已提交原 bytes 發布到 ignored public/summary.json。

**驗收：**漏通知可補查；等結果不空跑；新件不被舊摘要蓋掉；子 kernel 重建有自己的摘要。

## P-804．分配與收摘要〔來源：P-500～507、S-203／204；工程預設〕

`aos-kernel-resources --node N --phase prepare|apply [--in-tick]`；人手 `aos kernel resources N --phase PHASE`。prepare 讀 members、quota_file 與成員摘要；寫上述配額副本、`state/kernel/resources.json`（[schema](schemas/kernel-resource-state.schema.json)），格式含 member_id、quota_seq、applied、error。apply 在後組 needs prepare／members；讀已提交期望值、IPC 實際 cgroup，經固定 provision 動作配置，寫核對證據及事項。父 apply 將已提交配額原 bytes 原子替換到 ignored `public/quotas/<id>.json`，只給該子 read／traverse；子 quota_file 指此檔，驗 node_id/seq 及僅可信父可寫的權限；確有父配額卻缺／壞，才擋相關再分配。

最小分配採成員列出的固定份額，不另做動態最佳化。CPU／memory／pids 只在有明列配額且該任務啟用時套用；父份額比較沿 P-503，自用量與子層總分配不得超額。無相應 module 不新增該類限制；要求已有的能力而不可用則阻擋那名成員的新派工。boot_id 改變先清所有 applied，再核對／佈建；配額變動核對實際值，調低等全空；不能為了省事 resume 人手暫停的 node。成員失敗記 applied=false；排程及 prepare 逐名查 applied／quota_seq，0 不代表全可用。

prepare 也接 resources.set／measure，按 P-801 提交，後格補送已提交回應／清原件。res-usage 只記能量到的範圍，追蹤 `state/resources/<id>.usage.json`；成員 summary.usage 整份替換，node_id／commit／時效核對失敗不補零，不重加孫層。`resources.measure` 收件後提交重測摘要，後格送既有 msg-resource-result；沒裝的量測欄位缺席。LLM 新請求受 route 份額限制，但沒有額度仍收既有結果、回件與取消。

**驗收：**配置失敗只擋該人；斷線核實值，缺用量不補零。

## P-805．壞設定與安全重驗〔來源：A-102、P-203／207、ops P-601；D4 最小版〕

```text
aos-kernel-check --node N [--in-tick] [--cleanup]
aos-kernel-check --node N --validate-only
```

人手 `aos kernel config check N`；安全處理表 recheck 的 exec 是不帶 in-tick。讀 inst／tasks 及本篇有安裝任務使用的 config，驗 schema、引用、重名、父額度、路由與本地 pool／scope 對應；不發 HTTP、不起 once、不 resume node。endpoint 不通留派送處理。members 外框和各項分開驗，壞項依 P-802 隔離；不是整表回退。一般 check 使用固定 commit；validate-only 只驗 caller 持鎖的**目前工作樹**，完全不寫不取鎖不提交，0 合法、2 不合法、125 讀不到，供 node resume 在提交手改之前用。

check 寫追蹤 `state/kernel/config-state.json`（[schema](schemas/kernel-config-state.schema.json)）：每檔保存最後有效 commit，問題保存 path、issue_id、bad_commit、resolved_commit（未解除為 null）。普通設定壞掉沿用上一有效版本，發 `config_invalid`，message 指檔與欄位、actions:[recheck]；沒有舊版本則相關 prepare 停新工作，collect 仍靠已保存原件與工作路徑收結果。inst／tasks 錯誤不回退舊表。成功保存驗證結果即回 0（不表示配置可用），各 prepare 自查所需有效檔；無法保存診斷才失敗。

recheck 不讀 stdin，按本地問題與 open 檔核對 source_node=N、issue_id。第一次錯誤配 ID，同問題不覆蓋通知；修好後先提交採用版本及 resolved_commit。`--cleanup` 是後一組 needs check，讀已提交證據才移該來源 open 到 done；普通直接 check 自行提交後才做同一步。提交失敗不解除，通知失敗下次補；attention_dir 失效另印診斷。unknown、外部副作用、clean 遍歷不由設定重驗解除。

**驗收：**壞設定沿舊值並記事項；修正提交後才移 done，提交失敗仍 open。

## P-806．once 工作四階段〔來源：P-400～404、Q1／Q2；工程預設〕

`aos-kernel-work --node N --phase collect|prepare|dispatch|cleanup [--in-tick]`；人手 `aos kernel work N --phase PHASE`。collect 自成組；prepare needs collect／members／resources-apply；dispatch 另組 needs prepare；cleanup 另組 needs collect。RPC 沿 work-request／work-result。

| 階段 | 讀取、寫入與失敗 |
|---|---|
| collect | 讀 requests/ 的 work.submit、once result／inst.json.err 與狀態；核對成員身分、回址、工作有效 UID，複製追蹤 `state/work/<attempt_id>/request.json`，結果亦放此處；壞件拒收或留事項，未 commit 不刪原件 |
| prepare | 固定材料／base、分配 seq，寫 `state/work/<attempt_id>/kernel.json`（[schema](schemas/kernel-work-state.schema.json)），備好外層 inst 與回應；新派工才查成員份額，排隊者 phase=queued；可派者 prepared |
| dispatch | 只讀已提交材料，建 ignored `work/once/<attempt_id>/`，依 P-402 登記 inst（parent_id=發起成員）再 wake；只投已提交回應；寫 phase 與診斷，外部失敗不還原已執行效果 |
| cleanup | 確認已提交原件 bytes 相同才刪 收件原件；不清在途、unknown 或結果材料 |

kernel.json 記 request_id、seq、phase、boot_id、config_commit、work_dir、finished_at_ms，不複製請求／結果。配對必須是同 request／node／job／attempt。結果只在**後一格** collect；dispatch 不等工具或同格收結果。完成／未知回應先提交再投回，引用的輸出需有接收者讀權。

**驗收：**exit 7 下格回 failed；once 算成員額度，投遞失敗不重開工具。

## P-807．送出中斷與恢復〔來源：B-603、P-104／110、C-03、Q2；工程預設〕

dispatch 只啟動本格新建且已提交的 prepared；舊 prepared 不證明未送出。先查同 boot 登記、last_tick、完整結果及 `<inst>.err`：可信登記尚在且從未開始，才可第一次 wake；已開始則等／收，無可信證據就是 unknown。不能因登記消失、registered:false、換 boot 或逾時重登 once；普通成員重建不包含歷史 once。

啟動失敗旁檔依 P-402 合成結果，矛盾證據留事項。unknown 保留原件、材料及必要占用，不換 ID 重做，人工處置沿 ops。此條同樣約束 LLM 與跨 kernel 投件；已提交回件可補投相同 bytes。

**驗收：**在 register/wake/HTTP 各點崩潰再啟，不多跑同一嘗試。

## P-808．LLM 路由表〔來源：最新「設定裡一個位址」、P-303、S-301；工程預設〕

追蹤 `config/llm-routes.json`（[schema](schemas/kernel-llm-routes.schema.json)）：`version:1,routes`；每項 `pool_id,model,next_node,next_pool,allowed_origins`。pool_id 本層唯一，對應請求 pool／quota.llm.pool_id；model 必須匹配。next_node=null 是自己的池，next_pool 對應 llm-pools.id；非 null 是下一個 kernel，next_pool 是對方路由名，仍收 llm.complete。同名池以 node＋pool 分開。

allowed_origins 列 `{node_id,via_node,via_uid}`：哪個原發起人可經哪個投件者交來。直投兩個 node 相同；代理須下一站明授 origin/via。via_uid 是部署明授非 root UID，投件 owner 必須相符，不用無權的 node.get 或可改 inst 自證；共 UID 不宣稱隔離。未授權／無路由回 work_not_authorized／pool_not_found。

配置不得成環，next_node 不得是自己（本池用 null）；執行時同 origin/job/attempt 再回本 node，回 routing_loop、留事項、不再轉交。接納後固定路由與設定版本，不把在途請求改投他站。

**驗收：**跨隊代理可驗來源，冒稱 origin 不借權；A→B→A 被已保存證據擋住。

## P-809．轉交 module〔來源：最新 kernel 管全部、Q1／Q2、S-302；工程預設〕

`aos-kernel-llm-forward --node N --phase collect|prepare|dispatch|cleanup [--in-tick]`；人手 `aos kernel llm forward N --phase PHASE`。group/needs 沿 P-806：collect 收 llm.complete／回件，prepare 驗 route、排 seq／占份額，dispatch 送已提交原件／回件，cleanup 刪已提交相符收件。

追蹤 `state/work/<原 attempt>/` 的 request.json、forward.json（[schema](schemas/kernel-forward-state.schema.json)）、forward-request.json、forward-response.json、response.json；外部收件 ignored。遠端 request 配新 forward_id／reply_to=本 kernel，method 仍 llm.complete，params 只把 pool 改 next_pool，保留 node/job/attempt/messages/model。下游按 P-808 驗代理授權；回件核對來源／請求，提交後改回原 RPC id、投原 reply_to。每跳都先提交，後格才收結果。

本池**不投自己的 requests**：prepare 提交 request／forward.json（target_node=null、forward_id=null），aos-llm prepare needs 此組直接讀。pool collect 只收 HTTP once 結果，不搶 llm 收件；池結果提交後由 forward 下一格生成原回件，池不另送一次。

直接成員扣自己份額；origin 非成員、via 是成員就扣 via 的本層 route 份額；via 也非成員但符合 allowed_origins，是明授池客戶，只做池共享限制。接納後未終局及 unknown 各占一次，429 內部重試不再占第二份。額度不足留 queued；unknown 不自動釋放／重送；下游仍核自己的窗口，不保證跨 repo 原子保留。

**驗收：**本池不重接納，多跳／外隊不因 origin 非成員卡住，結果仍配回原 agent。

## P-810．直接投 LLM node 與用量收集〔來源：最新 kernel 不管的路線、agent P-710；工程預設〕

`aos-kernel-usage-collect --node N [--in-tick]`；人手 `aos kernel usage collect N`。讀直接成員在固定 commit 的 `config/agent.json` 與 `state/agent/usage/<request_id>.json`（[agent-usage](schemas/agent-usage.schema.json)），只收 `llm.target_node` 不是本 kernel 的成員；不送 LLM、不扣本層轉交份額、不替池限流。跨層成員只讀它提供的摘要，不穿透下層。

追蹤保存原格式 `state/resources/member-usage/<member_id>/<request_id>.json` 及 `state/kernel/usage-collect.json`（[schema](schemas/kernel-usage-state.schema.json)）。以 node_id/request_id/attempt_id 配對，從同一來源 commit 逐鍵替換，不把累積檔每格再加一次。pending、unknown、usage:null 原樣保留；看不見、過時、壞格式保存 missing/stale/invalid 與事項，不寫假零。新 commit／補查期才讀；沒變動不 commit，不管外部自備憑證。

**驗收：**重讀不重算，429 保留各 attempt，unknown 不補零。

## P-811．池與共享窗口〔來源：P-405～408、S-301～304；D5 最小版〕

追蹤 `config/llm-pools.json` 沿 [llm-config](schemas/llm-config.schema.json)，含 endpoint/model/quota_scope/key_ref/max_attempts。裝 tasks、登記、wake 就啟動池，沒有常駐池 daemon。範本先用無 key 本機 endpoint；key_ref 只指樹外私有檔，key 不進 git/argv/成員環境/回件，同帳號不隔離 key。

追蹤 `config/llm-limits.json`（[schema](schemas/kernel-llm-limits.schema.json)）：每個 scope 唯一一項 concurrent_requests/window_ms/requests_per_window/tokens_per_window，皆正整數。共享 provider 限制必須同 node 同 scope，改名字不代表獨立。

首筆預留開固定長度窗口，到期才重設窗口計數；時鐘倒退不提早釋放。重啟從證據重建，不能證明已過期者再等完整 window_ms。每次 HTTP 預留一個 request、估算 token＝messages/tools UTF-8 JSON bytes＋max_completion_tokens；明標估算，不承諾是 provider tokenizer 精確上界。單筆超上限拒收 capacity_unavailable；本窗口已滿則等，並行／unknown／冷卻也須放行。

預留存在 `state/work/<attempt>/kernel.json.llm`：pool_id/quota_scope/reserved_tokens/reserved_at_ms/retry_at_ms；沿 P-807 派送，每次 HTTP 不同 attempt 資料夾。provider usage 存 llm-result，不因實際輸出少而退還窗口預留。429 留時刻／共享冷卻，依 P-407 Retry-After 與有限次數重試；unknown 不重試、不自動到期釋放估計並行占用，等待可信證據／人工處置。

`aos-llm`／`aos-llm-call` argv、I/O、退出沿 P-408，另讀有效 routes/limits。寫追蹤 `state/llm/pool-status.json`（[schema](schemas/kernel-pool-status.schema.json)）：scope 記 active_requests/unknown_requests、window_started_at_ms/window_requests/window_estimated_tokens、last_429_at_ms/cooldown_until_ms；pool 記 scope 及兩種占用。未知／已知分開，每 attempt 只算一次；尚未 HTTP 的派送預留也算 active。observed_at_ms 記觀測時間，無變更不每格刷新。

**驗收：**兩 endpoint 共 scope 不各拿完整額度；usage 可見 429／unknown；unknown 過窗口不再送。

## P-812．唯讀查詢〔來源：H-034 D1／D5、P-106；工程預設〕

`aos-kernel-pool-usage --node N` 對應 `aos llm pool usage N`；stdin 不讀，stdout 印 P-811 pool-status JSON＋LF，stderr 診斷，退出 0 成功、2 用法錯、1 缺檔／不可讀。固定 HEAD 讀狀態、不叫醒、不量測；年齡寫 stderr（人手 CLI 可另渲染），不混 stdout JSON、不讀 key。

`aos node ls`／`show` 使用 daemon.info/list/get 的 boot_id、registered、last_tick，支援有權看的 once 與本次 daemon 留存的已解除 once。最近格開始／結束時間和 exit_code 是程序證據；重啟消失顯示「本次開機尚無紀錄」，不拿 git commit 猜結束碼、不把 once 消失當重做許可。

**驗收：**查詢不開 tick；once 結果在重啟前可查，重啟後不假造歷史。

## P-813．建立 agent 的兩條路〔來源：最新 LLM 地址、P-208／303；工程預設〕

- **全部管**：agent llm.target_node=本 kernel，pool/model 配本層 route，members quota 給份額。開 agent→kernel requests、kernel→agent responses；下站若別的 kernel，再開相應雙向投件，下一站明授 origin/via/via_uid。
- **不管**：agent llm.target_node=LLM kernel，直接開兩者 requests／responses 投件權；LLM kernel route 明授該 agent。父裝 usage-collect、取得 agent 已提交 usage 讀權，不給本層轉交份額。

兩種都要父可列成員收件、讀已提交 summary，及日常 work.submit 的雙向投件權。只開摘要可用 public/summary；usage-collect 另須逐 attempt 用量讀權。traverse、發布／刪除、群組／ACL 沿 P-208，不給 agent key／別人 repo 權限。帳號／chown 特權走 daemon helper，其他權限由有 OS 權限的建立者配置，失敗不回可用。父配額發布檔只給該子讀，不能讓子修改。

**驗收：**兩路都用同一 llm.complete／llm-result，agent 不辨別代理與池。

## P-814．完整範本與走查〔來源：H-036、B-603、P-010；工程預設〕

```text
aos node new /srv/aos/top --template kernel --user 1000 --socket /run/user/1000/aos.sock --attention-dir /srv/aos/attention
```

kernel 範本必填 socket／attention-dir；user 省略沿既有繼承規則。建立普通 git node、初始 commit、requests/responses/work 目錄，不覆蓋既有目標、不登記或試 HTTP。[完整 JSON](examples/kernel-tasks/kernel-template.minimal.valid.json) 與 [schema](schemas/kernel-template.schema.json) 的 files 鍵就是產出檔名；範本容器本身不存入 node。包含 inst、tasks、全部設定、gitignore；替換 node 路徑、user、socket、attention_dir 為 CLI 值。

頂層 daemon 設定 roots 放 `{node_id,identity_grant:[1000],interval_ms:1000}`；啟動第一格自跑，子 kernel 的 members interval 同為 1000。依 [members 正例](examples/kernel-tasks/kernel-members.minimal.valid.json) 取 members[0] 存 F 給 members add；用 [routes 正例](examples/kernel-tasks/kernel-llm-routes.minimal.valid.json) 配對成員地址、via_uid、pool/model，再把池 endpoint/model 換成已有服務。空 members/routes 不會自動授權 agent。

完整 tasks 已列跨組 needs；check→check-notify 是 system，收件／prepare／dispatch／cleanup 是 kernel，schedule 後組 publish 摘要，clean 是 custom。沒有本地池可移除池四階段及池設定；全體轉交可移除 usage。修改任務表走重要設定維護，連帶更新 needs。

H-036 接線：① daemon 啟停；② kernel 範本／池／roots；③ agent 範本＋P-813 權限／地址＋members add；④ schedule、下格收工作、node last_tick／pool usage；⑤ config_invalid 重驗解除；⑥ validate-only 驗手改再 resume；⑦ Ctrl-C 停機、換 boot 重建。正式回話/context/say/listen 由 [agent 篇](agent-tasks.md) 接。

清理最小版：queued/prepared/dispatched/sent/unknown、收件未清、無回件消費證據、仍引用的材料皆保留。其餘沿 P-606；缺證據報 clean_blocked，不丟去重依據。完整自動遍歷與 unknown 新嘗試不在本範本內。

**驗收：**範本全 JSON 合法、needs 只指前項；按上面填成員、路由、權限與服務後，接 agent 範本走循環。

## P-815．格式驗收〔來源：P-007；工程預設〕

[範例](examples/kernel-tasks/) 首段對應同名 schema，每種一份 minimal.valid／minimal.invalid。反例原因：members 夾 once；config 批次為零；llm-routes 地址相對；llm-limits 窗口為零；config-state 用 HEAD；sync-state boot_id 非字串；schedule-state 序號為零；resource-state applied 非布林；work-state／forward-state 虛構自動重試階段；usage-state 把缺量當零；pool-status unknown 負數；template 在 task 自設 user。上述檔名前綴皆為 kernel-。

**驗收：**正例全過、反例全不過；wf-lint proto6 broken=0。schema 不替代授權、跨檔一致、重啟與外部 HTTP 驗收。
