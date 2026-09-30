# 資源：任務、配額與用量

← [共用約定](README.md)｜[資源正本](../scheduling/admission.md)｜[身分與資源](../base/identity-resources.md)｜[LLM](../scheduling/llm.md)

本篇只定**預設 kernel 範本**的資源 module 的檔案格式、欄位與 cgroup 檔對照；行為以 [S-203](../scheduling/admission.md)（框架、巢狀範圍）與 [S-205](../scheduling/admission.md)（套用、調整與故障）為正本。〔使用者方向 2026-09-30，第十八批〕資源由各 kernel 定義；六類（CPU、memory、pids、LLM、disk、network）是範本的資源，kernel 可以在同一份配額與用量檔裡放自己的資源名稱（[T-06](../terms.md)）。

## P-500．module 就是任務〔使用者方向 2026-09-29〕

module 是 [node P-202～204](node.md) 的普通任務；範本的六類可各自選裝，不另加 module 表或 ABI。argv 由任務設定，cwd／stdin／stdout／stderr／環境／鎖完全沿 P-203，不能另切帳號或重取同 node 鎖。

〔建議預設，未拍板〕直接開檔讀配額、已授權量測介面及必要本地證據；寫自己 node 的用量／分配狀態，由 group 提交。退出 0＝本步完成，2＝設定錯，125＝無法開始，1＝已開始但失敗。額度不足可以成功寫摘要後等待。派工的任務不用 `needs` 串資源任務，而是讀它已提交的狀態，只擋新啟動（[S-205](../scheduling/admission.md)）。

## P-501．配額檔〔建議預設，未拍板〕

[res-quota.schema.json](schemas/res-quota.schema.json) 是父 kernel 在**自己 repo** 的 `state/resources/` 保存的直接成員配額，每份只管一個 `node_id`。頂層初始額度可在 `config/` 用同格式提供；頂層這份只是分配政策，不承諾頂層自己被卡住（[S-205](../scheduling/admission.md)）。檔名與引用由任務設定，不把 node 路徑當檔名。

| 欄位 | 意思 |
|---|---|
| `version` | 固定 `1` |
| `node_id` | 受分配的 node；共用 `NodeId`，不是授權證明 |
| `seq` | 此父子關係的配額修訂序號，正整數、遞增；不當作工作排隊序號 |
| `resources` | 只列實際分配的項目，可為 `{}`；範本六類的欄位見 P-503～P-506，其他鍵是 kernel 自訂資源 |

同一 `seq` 內容不同報衝突，較舊版本不覆蓋新版本；不能用 mtime 選新版。欄位省略表示這份檔**沒另給該項額度**，不是零、無限或解除父限；要降低、撤回既有分配仍須明確更新並照 [S-205](../scheduling/admission.md) 處理。只有 cgroup 上限必須落在父層範圍內；其他資源「子層在已分得範圍內再分」是範本預設（[S-203](../scheduling/admission.md)）。

〔使用者方向 2026-09-30，第十八批〕**自訂資源**：`resources` 裡範本六類以外的鍵，值的形狀由定義它的 kernel 自己定。範本六類的名稱意思固定，自訂資源不能拿這六個名字換別的形狀。不認得的 kernel 不解釋、不代管，改寫檔案時原樣保留（[C-07](../contracts.md)）。

最小正例：[quota.minimal.valid.json](examples/resources/quota.minimal.valid.json)；[quota.custom_resource.valid.json](examples/resources/quota.custom_resource.valid.json) 示範自訂資源。主要錯例：[quota.negative_memory.invalid.json](examples/resources/quota.negative_memory.invalid.json)，負的記憶體 bytes 不合法。

## P-502．用量摘要與檔案交接〔建議預設，未拍板〕

[res-usage](schemas/res-usage.schema.json) 是子層的 `state/resources/` 用量：version:1、node_id、observed_at_ms、resources 必填，涵蓋 node 與受管子樹合計，含工具。只寫能量到的值，resources 可空，可含 kernel 自訂資源；上層不再重加子孫。缺項／讀不到／過時不是零，過時門檻由 kernel 政策定。

摘要的同 commit 讀取與只開摘要權限的發布完全依 [messages P-307](messages.md)。改配額用 `kernel.quota.set`、要求重測用 `kernel.usage.measure`，參數、回應與授權只在 [messages P-306](messages.md) 定義；kernel.schedule.recheck 只重判排程。

〔使用者方向 2026-09-29，裁定「LLM 請求送去哪」〕成員自記用量、kernel 只收集時，逐次用量檔是成員 [agent P-703](agent-tasks.md) 的 `state/agent/usage/<request_id>.json`，收集任務見 [P-810](kernel-tasks.md)；讀法、缺值與按原發起 node＋attempt 去重依 [S-207](../scheduling/admission.md)。本篇的資源摘要不取代逐次 usage 證據。

[正例](examples/resources/usage.minimal.valid.json)；[反例](examples/resources/usage.negative_cpu.invalid.json) 的 CPU 累積用量為負。

## P-503．CPU、記憶體與 pids〔使用者方向 2026-09-29〕

已裝 OS module 採 cgroup v2；cgroup 子樹、框命名與佈建以 [B-605](../daemon.md) 為正本，佈建參數見 [daemon P-107](daemon.md)；上限隨時可改，見 [S-205](../scheduling/admission.md)。

| resources 欄位 | 配額 | 用量摘要 | cgroup 對應 |
|---|---|---|---|
| cpu | quota_us、period_us 正整數 | usage_us 非負整數 | cpu.max 原微秒值；cpu.stat 的 usage_usec |
| memory | bytes 正整數 | current_bytes 非負整數 | memory.max／memory.current |
| pids | max 正整數 | current 非負整數 | pids.max／pids.current（含 thread） |

CPU 是 [P-002](README.md) 時間單位的明示例外，不轉毫秒。limits 映為 `cpu_max:{quota_us,period_us}`、memory_max_bytes、pids_max；未配置項不傳，全無限制則不呼叫。分配比 CPU 份額用 quota_us / period_us，子層合計加本身不得超過父；配額不提供字串 max，實際值查詢才可能讀到它。usage_us 是目前 cgroup 存續期間的累積值，重建後不可接著取差值。

分支／執行 leaf、once 的可信 parent_id 歸屬與實際限制查詢，只依 [daemon P-104～107](daemon.md)。OOM 與後代收尾依 [執行器](../base/execution.md)，不只看 SIGKILL 猜 OOM。

## P-504．套用不是 git 回滾〔建議預設，未拍板〕

（第十八批：行為併入 [S-205](../scheduling/admission.md)，佈建動作見 [B-609](../daemon.md)。）格式上只留一條：設定請求寫目標限制值，不能寫「再加一份」。

## P-505．路線與 LLM 份額〔使用者方向 2026-09-29，裁定「LLM 請求送去哪」〕

agent 只按設定的一個 node 位址投 `llm.chat`，請求與結果始終用 [llm-work P-406／407](llm-work.md) 的同一格式。kernel 的兩條份額路線（全管、不管派送）與 LLM 三檔以 [S-301](../scheduling/llm.md) 為正本，範本欄位怎麼填見 [P-813](kernel-tasks.md)；工具的 `tools.target_node` 路線同樣見 P-813，兩條路都沿 [work P-402](work.md)，不靠工作資料夾位置決定資源歸屬。

〔建議預設，未拍板〕以下是預設 kernel 範本的份額格式。配額 `llm` 是陣列，每項只有 `pool_id`（共用 `ID`）與 `concurrent_requests`（非負整數）；零表示不放行新請求。同檔不可重複 pool_id。這個 ID 是**配置該份額之 kernel 的路由名**，由 `config/llm-routes.json` 唯一對到下一個 node 與下一個 pool；本地終點才對到 [llm-work P-405](llm-work.md) 的 pools[].id。不把兩個 node 的同名池當同池，也不讓 agent 指定 endpoint 或 key。路由、授權及回件對照的格式只在 kernel 任務篇定。

用量 `llm` 每項是 `pool_id`、`active_requests`、`unknown_requests`；後兩者非負且**分開計數**。前者是已知仍占用的請求；後者是遠端執行／占用不明的請求，兩者合計占用份額。unknown 的估計占用什麼時候釋放，由池所屬 kernel 的池設定決定（[S-304](../scheduling/llm.md)），不綁 [P-606](ops.md) 的資料保留期；釋放也不表示遠端已停止。

本篇只編碼並行份額；provider usage、429 與 unknown 沿 [S-301～S-304](../scheduling/llm.md)及 [llm-work P-407](llm-work.md)。共享 quota_scope 的最小窗口設定及 `state/llm/pool-status.json` 由 [kernel 任務篇 P-811](kernel-tasks.md) 定；`aos llm pool usage` 讀同一已提交版本，顯示並行占用、unknown、最近 429 及冷卻時間。狀態是該池 node 的觀測，讀不到或過時就明說；不同 node 的同名 quota_scope 不會自動共享計數。〔使用者方向 2026-09-30，第十八批〕共用 provider 限制要不要匯到同一個池、要不要分片或讓兄弟借用，是各 kernel 自己的資源政策（[S-301](../scheduling/llm.md)）。

上下層份額的關係見 [S-301](../scheduling/llm.md)。key 不進本篇檔案、argv 或給 node 的環境，帳號與 key 保護只見 [llm-work P-405](llm-work.md)。

**驗收：**同一份 agent 請求可經自己的 kernel 轉交或直接交 LLM kernel，wire 格式不變；轉交不能靠改 pool 名跳過份額；兩個共用 scope 的池在 429 後一起冷卻。

## P-506．磁碟與網路〔使用者方向 2026-09-29〕

磁碟額度只記帳，不是硬限制或隔離承諾；不綁檔案系統。〔使用者方向 2026-09-29 晚〕project quota 有就用；沒有（或設定強制關）就由資源任務定期量，間隔是資源任務的設定（[P-804](kernel-tasks.md)），框架見 [B-304](../base/identity-resources.md)。網路 module 可不裝；**首版只記用量、不做硬限速**，要求硬限速的部署明確報不支援（第十一批）；只承諾已裝且實際可用的能力，沿 [S-203](../scheduling/admission.md)。

〔建議預設，未拍板〕配額 `disk.bytes` 是非負的記帳額度。用量 `disk` 是 `{path, bytes}` 陣列，列出實際盤點的絕對路徑與磁碟配置 bytes；`path` 含其可觀測子樹，列入的範圍不得重疊或重複計同一資料。是否含 git 歷史、封存或外部 workspace，依列出的範圍與實際讀取權限判定，不聲稱涵蓋全機。同一份摘要依 `(st_dev,st_ino)` 去重 hardlink、以配置區塊量計 bytes；reflink／跨 node 共用實體區塊不承諾精確去重。量不到完整範圍就不報完整值、另留診斷，沿 [B-304](../base/identity-resources.md)。

〔建議預設，未拍板〕用量 `network` 是 `{scope, rx_bytes, tx_bytes}` 陣列；`scope` 明寫量測邊界與計數起點（例如介面／namespace／本次計數器期間），bytes 是該 scope 的累積觀測值。計數器重置就換 scope，不能把負差值當用量；範圍重疊不相加，不能把 host 介面總量冒認為某 node 用量。首版只定可觀測摘要，**不定網路配額欄位與限速 backend**；需要硬限制的部署，在 backend 與授權尚未定義／不可用時應停止相關新工作並報出缺口，不假裝已限制。

## P-507．沒裝、失敗與驗證〔使用者方向 2026-09-29〕

（第十八批：沒裝與失敗的行為併入 [S-205](../scheduling/admission.md)。）

〔建議預設，未拍板〕method 只引用 [messages P-306](messages.md)，錯誤封套沿 [P-005](README.md)。本地診斷用 `resource_unavailable`（所需能力不可用）、`resource_limit_exceeded`（額度不足）、`resource_observation_failed`（讀不到必要量測），它們不授權重做 unknown。語法錯誤、跨層授權、pool 重複、配額比較與觀測範圍重疊，分別由 JSON 解碼器、schema 或 module 語意檢查；schema 通過不是執行驗收。

## P-508．待決與跨篇

見 [README P-008](README.md#p-008)。
