# kernel 的最小預設任務

← [協議入口](README.md)｜[node](node.md)｜[daemon](daemon.md)｜[資源](resources.md)｜[走查](../cli.md)｜[裁定](../../notes/2026-09-29-verdicts.md)

kernel 是裝了下列 module 的 node；本篇是待實作的最小預設。

## P-800．共同契約〔第十二批裁定；工程預設〕

每個 module 一項任務：check、members、resources、work、LLM forward、LLM pool、usage、schedule，另有 custom 的 aos-clean；它的輸出及到期間隔依 [P-605](ops.md)。各用 node user、直接開檔讀設定；stdin 不讀、stderr 診斷，除 clean 外的任務 stdout 空。`--node N` 可省，預設 cwd；tick 在 node 根跑任務。核對繼承鎖 fd 判斷是否由 tick 提交，直接模式自行持鎖、提交後交付。

任務把完整請求／回應放追蹤的 `.aos/outbox/{requests,responses}/<id>.json`，把已消費原件逐 byte 複製到 `state/messages/{requests,responses}/<id>.json`。**tick 在組提交後才投件、才刪相符收件原件**，封套沿 P-206。once 的 IPC 登記另由 module 做：當格新材料先提交，下一格才能啟動；不在任務中等工具／HTTP。

0 本步完成或等待；2 用法／設定錯；75 鎖忙；125 無法開始；1 無法處理或保存；提交／還原故障回 3 並擋格。個別請求失敗能保存就繼續。沒有變動不 commit、不刷新時間欄；程序回 0 不表示所有成員可派工。

## P-801．設定與持久成員〔B-603、S-203、P-501；工程預設〕

`config/kernel.json`（[schema](schemas/kernel-config.schema.json)）必填 `version:1,daemon_socket`；可選 `scan_interval_ms=60000,scan_batch_limit=64,usage_max_age_ms=60000,max_active_members=64`，皆正整數。`quota_file` 可指父層提供的 res-quota；頂層可指本地設定。無父配置時可省，不虛構無限額度。node 事項寫自己的 `.aos/attention/`。

`config/members.json`（[schema](schemas/kernel-members.schema.json)）為 `version:1,revision,members`；revision 正整數，內容改就加一。每項：

| 欄位 | 意思 |
|---|---|
| `id` | 本 kernel 唯一短名 |
| `node_id` | 成員絕對路徑，不由資料夾位置推父子 |
| `identity_grant` | daemon 身分額度；成員 inst 的 user 須在其中 |
| `interval_ms`（可省） | 週期；子 kernel 建議 1000，逐次放行的 agent 省略 |
| `provision`（可省） | 不超父範圍的 daemon 授權 |
| `quota` | 完整 res-quota，node_id 對本項、seq 隨配額遞增 |

拒絕重複 id／node_id、登自己或夾 once。members 提供初始配額；`state/resources/<id>.quota.json` 保存期望配額，`state/kernel/resources.json` 記套用結果。`kernel.quota.set` 的 params 是 inst、stdin 指 res-quota；核權後只更新期望配額，不改 config。兩處以較新 seq 為準，同 seq 異內容報 resource_conflict；新派工等配置核對完成，成員不能自擴額。

## P-802．增刪成員與按需同步〔B-603／604、P-104；工程預設〕

```text
aos-kernel-members [--node N] add --from F
aos-kernel-members [--node N] rm ID
aos-kernel-members [--node N] ls
aos-kernel-members [--node N] sync
```

人手對應 `aos kernel members add N --from F`、`rm N ID`、`ls N`、`sync N`。F 是任意可讀路徑的單項 JSON。add/rm 只持鎖提交清單，stdout 印 ID；同 ID 同內容不變，rm 不刪資料／帳號。ls 印已提交清單。這三項不掛 tick、不叫 daemon。

sync 讀清單、`state/kernel/sync.json`（[schema](schemas/kernel-sync-state.schema.json)）與 daemon.info。boot_id、revision 都沒變且無到期重試，就不重登、不列整棵樹；換 boot 重登正常直接成員，清單改版只處理差異。每批前後核對 boot，斷線先重查；boot 換了等下格重判。

只保存已確認登記、bootstrap_pending、待解除與重試時間；壞項 60 秒後重查，隔離該項並記事項，不拖住正常成員。首次／換 boot 登記由 schedule 核資源後 wake 一次，逐層重建；沒有變動不反覆 wake。移除者不再排新格，unregister 依 daemon 排空要求，busy 留待維護，不自動殺工作。失聯後先查 node.show。

## P-803．何時叫醒〔S-201～204、P-307；工程預設〕

`aos-kernel-schedule [--node N]`，人手 `aos kernel schedule N`。讀 members、同步／資源結果、成員收件檔名、已提交摘要與 node.show，寫 `state/kernel/schedule.json`（[schema](schemas/kernel-schedule-state.schema.json)），透過 IPC wake。

首格分批掃，平常處理到期、bootstrap 與 `kernel.schedule.recheck`；每 scan_interval_ms 補查最多 scan_batch_limit 個，按短名、scan_after 游標輪流，不讀 history。recheck 的 argv 對應 `aos kernel schedule recheck`，執行結果放待送區交 tick。缺摘要不當 idle，依收件／bootstrap 判斷並記事項。

有收件、summary.ready、due 到期或 bootstrap 才 ready；新 ready 配遞增 ready_seq，按序選不超 max_active_members 者。paused／stopping 不 wake，running／pending 不重複叫。記 wake 當時的 last_tick，等新格完成再用摘要，避免舊 ready 反覆叫醒；IPC 成功但提交失敗，下格查 daemon 合併判斷。

同組寫 `.aos/summary/summary.json`；ready 表示本地可推進，due_ms 取最近重試／掃描／冷卻，只有等待結果則 false。tick 提交後發布 `.aos/summary/published.json`，上層只開摘要權時讀此檔；沒有另列發布任務。

## P-804．分配與量測〔P-500～507、S-203／204；工程預設〕

`aos-kernel-resources [--node N]`，人手 `aos kernel resources N`。讀 members／父額度／成員摘要，按 P-801 選較新配額並核對 IPC 實際值。只對先前已提交的期望配置做 provision；本格配額變更提交後，下格才套用。父配額依 P-503 發布到 `public/quotas/<id>.json`，子 quota_file 指此檔，父才有寫權。

按期望配額的固定份額，只套用已啟用 module 的 CPU／memory／pids 限制。boot 換了重新核對，調低等全空，不 resume 人手 pause。失敗記 applied=false，逐名擋新派工；無 module 不新增限制，缺用量不補零。

同一 module 接 `kernel.quota.set`／`kernel.usage.measure`。後者對應 `aos kernel usage measure`，重測後把結果放指令 stdout，再按 work-result 回件。量到的資料存 `state/resources/<id>.usage.json`；成員 summary.usage 替換觀測，不重加孫層。額度不足仍收既有結果與取消。

## P-805．壞設定與重驗〔A-102、P-203／207、P-601；工程預設〕

```text
aos-kernel-check [--node N]
aos-kernel-check [--node N] --validate-only
```

人手 `aos kernel config check N`。直接讀 inst／tasks 及已裝 module 的 config，驗 schema、引用、重名、父額度、路由與池；不發 HTTP、不起 once、不 resume。validate-only 供 caller 持鎖驗工作樹，不再取鎖、不寫；0 合法、2 不合法、125 讀不到。

一般 check 寫 `state/kernel/config-state.json`（[schema](schemas/kernel-config-state.schema.json)）的 issues：path、issue_id、resolved。設定無效就停依賴它的新工作，仍收已派結果；成員單項錯只隔離那項。修好後重驗、提交設定狀態；人或 agent 確認修好後用 `aos attend done N ID` 標完成。

改設定在 tick 外持同把鎖；任務不改 config 是軟性原則，不檢查或阻擋，自行修改承擔同格新舊混用。

## P-806．工具 once module〔P-400～404、Q1／Q2；工程預設〕

`aos-kernel-work [--node N]`，人手 `aos kernel work N`。接 `kernel.work.submit`，params.argv 對應 `aos kernel work submit`，stdin 指 work-request 業務 JSON。核對來源／回址／成員身分，保存原件、材料與序號，寫 `state/work/<attempt_id>/kernel.json`（[schema](schemas/kernel-work-state.schema.json)）。

額度不足 queued；可派者 prepared。**本格新建的材料只提交；下一格才讀已提交 prepared**，在 `.aos/jobs/<attempt_id>/` 建 once inst，以可信 parent_id=發起成員登記再 wake。結果或 `<inst>.err` 後格讀，核對 request／node／job／attempt，生成 work-result 放指令 stdout，外層 RPC 指令結果交 tick 投回。

kernel.json 記 request_id、seq、phase、boot_id、work_dir、完成時間，不重存請求。phase 是工作進度，不是任務拆分。輸出只給路徑；投遞失敗不重開工具，額度歸發起成員。

## P-807．中斷與恢復〔B-603、P-104／110、C-03；工程預設〕

已提交材料且 ignored `.aos/jobs/<attempt_id>/launch-started` 不存在，才可首次啟動：先原子排他建立 marker、同步檔案與父目錄，再 register／wake。marker 保留到整件工作可清理；它存在時先核對同 boot 登記、last_tick、完整結果與 `<inst>.err`。可信登記證明從未開始才可第一次 wake；已開始就等／收。沒有可信結果、在途或從未執行證據就是 unknown，不因登記消失、換 boot 或逾時重登歷史 once。

原請求與回件可補投同 ID、同 bytes，只補交付，不重做外部工作。unknown 保持原樣，沒人處理就隨定期清理清掉，不自動重做。此規則也管 LLM 與跨 kernel 轉交。

## P-808．LLM 路由表〔P-303、S-301；工程預設〕

`config/llm-routes.json`（[schema](schemas/kernel-llm-routes.schema.json)）為 `version:1,routes`；每項 `pool_id,model,next_node,next_pool,allowed_origins`。pool_id 本層唯一；next_node=null 用自己的池，其餘送下一個 kernel，仍是 `llm.chat`。同名池以 node＋pool 分開。

allowed_origins 列 `{node_id,via_node,via_uid}`：原發起者及明授投件者／非 root UID；直投兩個 node 相同，代理須下一站授權。依部署權限驗來源，共 UID 不宣稱隔離。未授權／無路由回 work_not_authorized／pool_not_found。

配置不得成環；同 origin/job/attempt 再回本 node，報 routing_loop、不再轉交。接納時保存必要路由與請求材料，在途不改投別站。

## P-809．LLM 轉交 module〔Q1／Q2、S-302；工程預設〕

`aos-kernel-llm-forward [--node N]`，人手 `aos kernel llm forward N`。一項任務收 `llm.chat`／結果、驗 route、排 seq／份額、準備轉交與回件；交 tick 投出及清原件。

追蹤 `state/work/<attempt>/` 的 request、forward-state、轉交請求／結果與最終 response；[forward-state schema](schemas/kernel-forward-state.schema.json)。遠端請求配新 forward_id、reply_to=本 kernel，method 仍 `llm.chat`，params 是對應 inst；stdin 指改 pool=next_pool 的新業務 JSON，其餘 origin/job/attempt/messages/model 保留。回件核對後換回原 RPC id；外層 work-result 的執行 node／ID 也須對應本跳，不直接冒用下游指令結果。

本池不投自己的收件區：本 module 保存已接納材料，pool 任務在後組讀已提交材料。池提交結果後，forward 下一格生成原請求回件。

直接成員扣自己份額；代理成員扣 via 的本層份額；明授外部池客戶只受池共享限制。未終局／unknown 各占一次，429 重試不多占一份；額度不足 queued，unknown 不重送，估計占用隨 P-606 清理。

## P-810．用量收集 module〔LLM 與工具兩條路線；工程預設〕

`aos-kernel-usage-collect [--node N]`，人手 `aos kernel usage collect N`。讀直接成員已提交的 `state/agent/usage/<request_id>.json`（[schema](schemas/agent-usage.schema.json)）：LLM 直送別站、或工具 `tools.target_node=null` 自跑時，由此收量。設定直接開檔讀，不用歷史 commit 當設定來源；跨層只讀下層摘要。

原格式存 `state/resources/member-usage/<member_id>/<request_id>.json`，觀測記 `state/kernel/usage-collect.json`（[schema](schemas/kernel-usage-state.schema.json)）。以 node／request／attempt 逐鍵替換，不把累積檔每格再加。pending／unknown／null 照實保留；不可讀、過時、壞格式記 missing／stale／invalid，不造零。新證據或補查期才讀，無變動不 commit；同一工作只選轉交或自記一種統計來源。

## P-811．池與共享窗口〔P-405～408、S-301～304；工程預設〕

`config/llm-pools.json` 沿 [llm-config](schemas/llm-config.schema.json)，含 endpoint/model/quota_scope/key_ref/max_attempts/schedule。池就是這個 node，代發是 tick 任務，沒有常駐池 daemon；key_ref 只指樹外私有檔，不進 git／argv／成員環境，同帳號不隔離 key。

以下窗口、並行與冷卻只套 `schedule:aos`（自己排，預設）的池；`schedule:endpoint` 的池只轉發，不讀本檔，見 [llm-work P-405](llm-work.md)。

`config/llm-limits.json`（[schema](schemas/kernel-llm-limits.schema.json)）每 scope 一項 concurrent_requests/window_ms/requests_per_window/tokens_per_window，皆正整數。共享 provider 限制須同 node 同 scope；改名字不代表獨立。

首筆預留開固定窗口，到期重設；時鐘倒退不提早釋放。重啟依證據重建，不能證明過期就再等完整窗口。每次 HTTP 預留一個 request，token 估算為 messages/tools JSON UTF-8 bytes＋max_completion_tokens，不保證 tokenizer 上界。單筆超限拒收 capacity_unavailable，窗口滿／並行滿／冷卻就等。

預留存 `state/work/<attempt>/kernel.json.llm`，每次 HTTP 有不同 attempt。`aos-llm [--node N] --config F` 一項任務收結果、更新窗口並準備材料；只對先前已提交的 HTTP 材料啟動 `.aos/jobs/<attempt>/` once。429 依 P-407 有限重試；unknown 不重試，估計並行占用隨 P-606 清理。provider usage 原樣保存，不因少用 token 退窗口預留。

`state/llm/pool-status.json`（[schema](schemas/kernel-pool-status.schema.json)）記 scope 窗口、冷卻及已知／unknown 占用；同 attempt 只算一次，待啟動的預留也算 active，無變化不刷 observed_at_ms。

## P-812．唯讀查詢〔P-106；工程預設〕

`aos-kernel-pool-usage [--node N]` 對應 `aos llm pool usage N`。只讀已提交 pool-status，stdout JSON＋LF，stderr 診斷／年齡；不量測、不 wake、不讀 key。0 成功、2 用法錯、1 缺檔或不可讀。

`aos node ls`／show 讀 daemon.info／node.ls／node.show 的 boot_id、registered、last_tick。正常停機的 state.json 可接續登記／pause／未處理 wake；換 boot 不把舊在途當仍活著。程序結束碼要有 last_tick 證據，不能從 git 猜，也不能把 once 消失當重跑許可。

## P-813．建立 agent 的兩條路〔第十一、十二批裁定；工程預設〕

| 工作 | kernel 全管 | kernel 不管 |
|---|---|---|
| LLM | llm.target_node=本 kernel，裝 forward，配本層 route／份額 | llm.target_node=管池的 node，直接授雙向投件權 |
| 工具 | tools.target_node=本 kernel，裝 work，代登 once | tools.target_node=null，agent 自己登 once，parent_id 是 agent |
| 用量 | 由代辦 module 記，agent 記錄供核對 | agent 自記，父 kernel 裝 usage-collect 讀 |

LLM 另有 `llm.target_node=null` 的「直連」檔：agent 自己打 endpoint，不經池、不扣份額，key 必然讓 agent 讀得到（[S-301](../scheduling/llm.md)，之後再做）。

兩種工作可分別選路線。父須能列成員收件與讀摘要；僅開摘要權時讀 `.aos/summary/published.json`，用量另授讀權。轉交要開相應 requests／responses 權限，下一站明授 origin/via。自跑工具需 daemon 授權與 jobs 路徑權限；所有 once 資源都算可信 parent_id，工具不自選。

OS 帳號與 chown 特權走 daemon helper；其他群組由有權建立者配置（首版不用 ACL）。父配額只讓該子讀，不給子寫。

## P-814．完整範本與走查〔B-603、P-010；工程預設〕

```text
aos node new /srv/aos/top --template kernel --user 1000 --socket /run/user/1000/aos.sock
```

建立普通 git node、初始 commit、requests／responses／work／public／`.aos/jobs/`／`.aos/attention/`，不覆蓋既有目標、不試 HTTP。[完整 JSON](examples/kernel-tasks/kernel-template.minimal.valid.json) 與 [schema](schemas/kernel-template.schema.json) 的 files 是實際產物，不另存 template 容器；包括 `.aos/inst.json`、`.aos/tasks.json`、設定與 gitignore。

任務表共 **9 項**，每項是 inst（含 `_metainfo`，不填 user）加 id／kind／needs；group 省略、各自一組。外層 `_metainfo` 是 aos-tasks 第 1 版。

| id | kind | 程式（cwd 為 node 根） | needs |
|---|---|---|---|
| check | system | aos-kernel-check | 無 |
| members | kernel | aos-kernel-members sync | check |
| resources | kernel | aos-kernel-resources | members |
| work | kernel | aos-kernel-work | resources |
| forward | kernel | aos-kernel-llm-forward | resources |
| pool | kernel | aos-llm --config config/llm-pools.json | forward |
| usage | kernel | aos-kernel-usage-collect | check |
| schedule | kernel | aos-kernel-schedule | members、resources |
| clean | custom | aos-clean --config config/clean.json | 無 |

範本 task 用 `stderr:{"$opt":"inherit"}` 讓診斷交 tick。沒有本地池可刪 pool／池設定；全體轉交可移除 usage，連帶維護 needs。agent 範本有 agent 與 clean 兩項。清理間隔在 config/clean.json，預設一天，由 aos-clean 自己記時間。

daemon roots 填頂層 node、身分額度與 interval_ms=1000，**啟動即 tick 頂層**。正常退出存 state.json；意外退出照 roots 啟動，各 kernel 見 boot_id 換了才逐層重登。成員、routes、endpoint/model 按實際部署補齊，空清單不授權 agent。正式回話與查 context 由 [agent 篇](agent-tasks.md) 接。

清理依 P-606：一般 queued／prepared／在途、未消費收件、未確認回件及在用引用仍保留；unknown 到期後連同內部關聯與估計占用一起清，不等人工結案。不認得的資料不碰、不回報。

## P-815．格式驗收〔P-007〕

[範例](examples/kernel-tasks/) 依同名前綴驗 schema。反例涵蓋 members 夾 once、批次／窗口為零、相對路由、設定狀態錯型、boot 非字串、零序號、applied 非布林、未知工作階段、把缺量當零、unknown 負數、task 自設 user。

正例全過、反例全拒；`bash wf/tools/wf-lint.sh proto6` broken=0。格式不代替授權、跨檔配對、重啟與實際 HTTP 驗收。
