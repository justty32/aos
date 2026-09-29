# 資源：任務、配額與用量

← [共用約定](README.md)｜[資源正本](../scheduling/admission.md)｜[身分與資源](../base/identity-resources.md)｜[LLM](../scheduling/llm.md)

## P-500．module 就是任務〔使用者方向 2026-09-29〕

module 是 [node P-202～204](node.md) 的普通任務；CPU、memory、pids、LLM、disk、network 可各自選裝，不另加 module 表或 ABI。argv 由任務設定，cwd／stdin／stdout／stderr／環境／鎖完全沿 P-203，不能另切帳號或重取同 node 鎖。

〔建議預設，未拍板〕直接開檔讀配額、已授權量測介面及必要本地證據；寫自己 node 的用量／分配狀態，由 group 提交。退出 0＝本步完成，2＝設定錯，125＝無法開始，1＝已開始但失敗。額度不足可以成功寫摘要後等待；派工用 needs 依賴必要 module，不能在量測失敗時繼續放行。

## P-501．配額檔〔建議預設，未拍板〕

[res-quota.schema.json](schemas/res-quota.schema.json) 是父 kernel 在**自己 repo** 的 `state/resources/` 保存的直接成員配額，每份只管一個 `node_id`。頂層初始額度可在 `config/` 用同格式提供。檔名與引用由任務設定，不把 node 路徑當檔名。

| 欄位 | 意思 |
|---|---|
| `version` | 固定 `1` |
| `node_id` | 受分配的 node；共用 `NodeId`，不是授權證明 |
| `seq` | 此父子關係的配額修訂序號，正整數、遞增；不當作工作排隊序號 |
| `resources` | 只列實際分配的項目，可為 `{}`；欄位見 P-503～P-506 |

同一 `seq` 內容不同報衝突，較舊版本不覆蓋新版本；不能用 mtime 選新版。子層核對可信父子登記與授權來源後，才在已分得範圍內再分。欄位省略表示這份檔**沒另給該項額度**，不是零、無限或解除父限；要降低、撤回既有分配仍須明確更新政策並照 P-504 處理。

最小正例：[quota.minimal.valid.json](examples/resources/quota.minimal.valid.json)。主要錯例：[quota.negative_memory.invalid.json](examples/resources/quota.negative_memory.invalid.json)，負的記憶體 bytes 不合法。

## P-502．用量摘要與檔案交接〔建議預設，未拍板〕

[res-usage](schemas/res-usage.schema.json) 是子層的 `state/resources/` 用量：version:1、node_id、observed_at_ms、resources 必填，涵蓋 node 與受管子樹合計，含工具。只寫能量到的值，resources 可空；上層不再重加子孫。缺項／讀不到／過時不是零，過時門檻由 kernel 政策定。

摘要的同 commit 讀取與只開摘要權限的發布完全依 [messages P-307](messages.md)。改配額用 `kernel.quota.set`、要求重測用 `kernel.usage.measure`，參數、回應與授權只在 [messages P-306](messages.md) 定義；kernel.schedule.recheck 只重判排程。

〔使用者方向 2026-09-29，裁定「LLM 請求送去哪」〕成員直接向另一個 LLM kernel 投件，或 tools.target_node=null 自登 once 時，由成員保存自己的 LLM／工具用量，所屬 kernel 裝 [用量收集任務](kernel-tasks.md)。最小版須授 kernel 必要 repo 讀權，固定同一 commit 讀 [agent P-703](agent-tasks.md) 的 `state/agent/usage/<request_id>.json`；.aos/summary/published.json 只有資源摘要，不能拿並行數冒充逐次 provider usage。收集只記觀測，不假裝攔住請求或替遠端池釋放占用。同一 attempt 在成員、轉交 kernel、池都可能有紀錄；彙總須按原發起 node 與 attempt 去重，不能把同一筆 HTTP 用量加三次。本篇的資源摘要不取代逐次 usage 證據。

**驗收：**成員直投另一個 kernel 後，上層能在下一次收集看見用量；重讀相同 commit 不重加，缺讀權或 usage:null 不顯示成零。

[正例](examples/resources/usage.minimal.valid.json)；[反例](examples/resources/usage.negative_cpu.invalid.json) 的 CPU 累積用量為負。

## P-503．CPU、記憶體與 pids〔使用者方向 2026-09-29〕

已裝 OS module 採 cgroup v2；資源層級跟可信 node 登記，不由 inst 或工作檔路徑決定。透過 [daemon P-107](daemon.md) 的 node.provision 先 cgroup_create，再 cgroup_limits；**無 helper 時由 daemon 在 systemd 委派子樹內執行相同動作**。父限制、權限及失敗判斷不變。

| resources 欄位 | 配額 | 用量摘要 | cgroup 對應 |
|---|---|---|---|
| cpu | quota_us、period_us 正整數 | usage_us 非負整數 | cpu.max 原微秒值；cpu.stat 的 usage_usec |
| memory | bytes 正整數 | current_bytes 非負整數 | memory.max／memory.current |
| pids | max 正整數 | current 非負整數 | pids.max／pids.current（含 thread） |

CPU 是 [P-002](README.md) 時間單位的明示例外，不轉毫秒。limits 映為 `cpu_max:{quota_us,period_us}`、memory_max_bytes、pids_max；未配置項不傳，全無限制則不呼叫。分配比 CPU 份額用 quota_us / period_us，子層合計加本身不得超過父；配額不提供字串 max，實際值查詢才可能讀到它。usage_us 是目前 cgroup 存續期間的累積值，重建後不可接著取差值。

分支／執行 leaf、once 的可信 parent_id 歸屬與實際限制查詢，只依 [daemon P-104～107](daemon.md)。OOM 與後代收尾依 [執行器](../base/execution.md)，不只看 SIGKILL 猜 OOM。

## P-504．套用不是 git 回滾〔建議預設，未拍板〕

配額先在父 repo 提交，同一 module 後續一格才經 daemon 佈建；需要額度的派工依賴核對成功。daemon 重啟後，kernel 用自己已提交的必要配置重新佈建，daemon 不保存另一份持久資源表。

寫 cgroup 是外部效果，group 失敗不會撤回它。設定請求須描述目標限制值，不能是「再加一份」；回覆中斷時先查實際值並核對，不把失聯當成沒做或已成功；用 `node.show.cgroup` 的實際讀值核對，不用登記中的期望值冒充已套用；讀不到就保持阻擋。尚未確認配置可用時停止相關新派工，保留原因並交待處理；不藉重跑 module 重做工具或 LLM。

調低額度不取消已有工作、已開始 attempt 不中途換資源範圍，沿 [S-204](../scheduling/admission.md)與 [B-302](../base/identity-resources.md)。有在途工作時先停止新增占用、保留舊框，逐筆暫停受影響子樹，清空後由 [daemon P-107](daemon.md) 在開格互斥下核對並套新值；不能直接寫較低 `memory.max` 逼出 OOM。採用新版配額表示後續派工政策更新，不表示既有程序已被改限。

## P-505．路線與 LLM 份額〔使用者方向 2026-09-29，裁定「LLM 請求送去哪」〕

agent 只按設定的一個 node 位址投 `llm.chat`，結果回 agent 的收件區；請求與結果始終用 [work P-406／407](work.md) 的同一格式。agent 不判斷對面是自己的 kernel、上層 kernel 或管池的另一個 kernel。開 agent 的 kernel 負責選路線、寫設定與配權限，具體範本及程式見 [kernel 任務篇](kernel-tasks.md)。

| kernel 選的路線 | 裝的任務與責任 |
|---|---|
| 全部都管 | agent 位址指向自己的 kernel，裝 `aos-kernel-llm-forward`：核對來源、預留成員份額、排隊，再交本地池、上層或另一個 kernel；轉交及回件也遵守先提交、後送出。 |
| 不管 LLM 派送 | agent 位址指向管池的 LLM kernel，直接投它的 requests/；自己的 kernel 裝 `aos-kernel-usage-collect`，只收成員自記用量。LLM kernel 的授權、池共享限制仍須檢查。 |

工具也用一個 `tools.target_node` 選路：node id 交該 kernel 全管，null 由 agent 自己登記 parent_id=自己的 once、自己記用量，所屬 kernel 只收集。兩條路都沿 [work P-402](work.md)，不靠工作資料夾位置決定資源歸屬。

〔建議預設，未拍板〕配額 `llm` 是陣列，每項只有 `pool_id`（共用 `ID`）與 `concurrent_requests`（非負整數）；零表示不放行新請求。同檔不可重複 pool_id。這個 ID 是**配置該份額之 kernel 的路由名**，由 `config/llm-routes.json` 唯一對到下一個 node 與下一個 pool；本地終點才對到 [work P-405](work.md) 的 pools[].id。不把兩個 node 的同名池當同池，也不讓 agent 指定 endpoint 或 key。路由、授權及回件對照的格式只在 kernel 任務篇定。

用量 `llm` 每項是 `pool_id`、`active_requests`、`unknown_requests`；後兩者非負且**分開計數**。前者是已知仍占用的請求；後者是遠端執行／占用不明的請求，不能自動歸零。沒有明訂到期釋放估計占用的政策時，兩者合計占用份額；有此政策仍須保留 unknown 計數與證據，沿 [S-304](../scheduling/llm.md)。

本篇只編碼並行份額；provider usage、429 與 unknown 沿 [S-301～S-304](../scheduling/llm.md)及 work 篇。共享 quota_scope 的最小窗口設定及 `state/llm/pool-status.json` 由 [kernel 任務篇 P-811](kernel-tasks.md) 定；`aos llm pool usage` 讀同一已提交版本，顯示並行占用、unknown、最近 429 及冷卻時間。狀態是該池 node 的觀測，讀不到或過時就明說；不同 node 的同名 quota_scope 不會自動共享計數，共用 provider 限制必須匯到同一管池 node。

〔使用者方向 2026-09-29〕下層未裝不再細分，父額度及池限制仍有效；key 不進本篇檔案、argv 或給 node 的環境，帳號與 key 保護只見 [work P-405](work.md)。

**驗收：**同一份 agent 請求可經自己的 kernel 轉交或直接交 LLM kernel，wire 格式不變；轉交不能靠改 pool 名跳過份額；unknown 不自動釋放，兩個共用 scope 的池在 429 後一起冷卻。

## P-506．磁碟與網路〔使用者方向 2026-09-29〕

磁碟額度只記帳，不是硬限制或隔離承諾；不綁檔案系統。網路 module 可不裝；**首版只記用量、不做硬限速**，要求硬限速的部署明確報不支援（第十一批）；只承諾已裝且實際可用的能力，沿 [S-203](../scheduling/admission.md)。

〔建議預設，未拍板〕配額 `disk.bytes` 是非負的記帳額度。用量 `disk` 是 `{path, bytes}` 陣列，列出實際盤點的絕對路徑與磁碟配置 bytes；`path` 含其可觀測子樹，列入的範圍不得重疊或重複計同一資料。是否含 git 歷史、封存或外部 workspace，依列出的範圍與實際讀取權限判定，不聲稱涵蓋全機。同一份摘要依 `(st_dev,st_ino)` 去重 hardlink、以配置區塊量計 bytes；reflink／跨 node 共用實體區塊不承諾精確去重。量不到完整範圍就不報完整值、另留診斷；移出工作樹不等於釋放 git 歷史，沿 [B-304](../base/identity-resources.md)及 [B-404](../base/storage.md)。

〔建議預設，未拍板〕用量 `network` 是 `{scope, rx_bytes, tx_bytes}` 陣列；`scope` 明寫量測邊界與計數起點（例如介面／namespace／本次計數器期間），bytes 是該 scope 的累積觀測值。計數器重置就換 scope，不能把負差值當用量；範圍重疊不相加，不能把 host 介面總量冒認為某 node 用量。首版只定可觀測摘要，**不定網路配額欄位與限速 backend**；需要硬限制的部署，在 backend 與授權尚未定義／不可用時應停止相關新工作並報出缺口，不假裝已限制。

## P-507．沒裝、失敗與驗證〔使用者方向 2026-09-29〕

沒裝 module＝該層不另記／另限，不等於父層限制消失；tick 互斥與程序清空不是可關閉的 module。已安裝但 controller／權限不可用是失敗，不能降成「沒裝」後繼續派工。額度不足時等待或寫待處理，不忙跑、不丟已回來的結果；取消與收尾仍可做，沿 [S-203](../scheduling/admission.md)。

〔建議預設，未拍板〕method 只引用 [messages P-306](messages.md)，錯誤封套沿 [P-005](README.md)。本地診斷用 `resource_unavailable`（所需能力不可用）、`resource_limit_exceeded`（額度不足）、`resource_observation_failed`（讀不到必要量測），它們不授權重做 unknown。語法錯誤、跨層授權、pool 重複、配額比較與觀測範圍重疊，分別由 JSON 解碼器、schema 或 module 語意檢查；schema 通過不是執行驗收。

## P-508．待決與跨篇

見 [README P-008](README.md#p-008)。
