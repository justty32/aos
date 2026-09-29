# 資源：任務、配額與用量

← [共用約定](README.md)｜[資源正本](../scheduling/admission.md)｜[身分與資源](../base/identity-resources.md)｜[LLM](../scheduling/llm.md)

## P-500．module 就是任務〔使用者方向 2026-09-29〕

module 是 [node P-202～204](node.md) 的普通任務；CPU、memory、pids、LLM、disk、network 可各自選裝，不另加 module 表或 ABI。argv 由任務設定，cwd／stdin／stdout／stderr／環境／鎖完全沿 P-203，不能另切帳號或重取同 node 鎖。

〔建議預設，未拍板〕讀本格有效配額、已授權量測介面及必要本地證據；寫自己 node 的用量／分配狀態，由 group 提交。退出 0＝本步完成，2＝設定錯，125＝無法開始，1＝已開始但失敗。額度不足可以成功寫摘要後等待；派工用 needs 依賴必要 module，不能在量測失敗時繼續放行。

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

摘要的同 commit 讀取與只開摘要權限的發布完全依 [messages P-307](messages.md)。改配額用 `resources.set`、要求重測用 `resources.measure`，參數、回應與授權只在 [messages P-306](messages.md) 定義；kernel.recheck 只重判排程。

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

配額先在父 repo 提交，後續任務才經 daemon 佈建；需要額度的派工依賴核對成功。daemon 重啟後，kernel 用自己已提交的必要配置重新佈建，daemon 不保存另一份持久資源表。

寫 cgroup 是外部效果，group 失敗不會撤回它。設定請求須描述目標限制值，不能是「再加一份」；回覆中斷時先查實際值並核對，不把失聯當成沒做或已成功；用 `node.get.cgroup` 的實際讀值核對，不用登記中的期望值冒充已套用；讀不到就保持阻擋。尚未確認配置可用時停止相關新派工，保留原因並交待處理；不藉重跑 module 重做工具或 LLM。

調低額度不取消已有工作、已開始 attempt 不中途換資源範圍，沿 [S-204](../scheduling/admission.md)與 [B-302](../base/identity-resources.md)。有在途工作時先停止新增占用、保留舊框，逐筆暫停受影響子樹，清空後由 [daemon P-107](daemon.md) 在開格互斥下核對並套新值；不能直接寫較低 `memory.max` 逼出 OOM。採用新版配額表示後續派工政策更新，不表示既有程序已被改限。

## P-505．LLM 份額〔建議預設，未拍板〕

配額 `llm` 是陣列，每項只有 `pool_id`（共用 `ID`）與 `concurrent_requests`（非負整數）；零表示不放行新請求。同檔不可重複 pool；ID 對應目標代發 node 的 pools[].id（[work P-405](work.md)）；路由以「代發 node 路徑＋pool_id」識別，不把別的 node 同名池當同池。

用量 `llm` 每項是 `pool_id`、`active_requests`、`unknown_requests`；後兩者非負且**分開計數**。前者是已知仍占用的請求；後者是遠端執行／占用不明的請求，不能自動歸零。沒有明訂到期釋放估計占用的政策時，兩者合計占用份額；有此政策仍須保留 unknown 計數與證據，沿 [S-304](../scheduling/llm.md)。

只編碼並行份額；provider usage、429 與 unknown 沿 [S-301～S-304](../scheduling/llm.md)及 work 篇。共享 quota_scope 的實際 token／request 窗口格式仍是 [P-008](README.md#p-008) 的待補工程接口；實作補齊前不得聲稱池端共享限流已完成。

〔使用者方向 2026-09-29〕下層未裝不再細分，父額度及池限制仍有效；key 不進本篇檔案、argv 或給 node 的環境，帳號與 key 保護只見 [work P-405](work.md)。

## P-506．磁碟與網路〔使用者方向 2026-09-29〕

磁碟額度只記帳，不是硬限制或隔離承諾；不綁檔案系統。網路 module 可不裝；只承諾已裝且實際可用的能力，沿 [S-203](../scheduling/admission.md)。

〔建議預設，未拍板〕配額 `disk.bytes` 是非負的記帳額度。用量 `disk` 是 `{path, bytes}` 陣列，列出實際盤點的絕對路徑與磁碟配置 bytes；`path` 含其可觀測子樹，列入的範圍不得重疊或重複計同一資料。是否含 git 歷史、封存或外部 workspace，依列出的範圍與實際讀取權限判定，不聲稱涵蓋全機。同一份摘要依 `(st_dev,st_ino)` 去重 hardlink、以配置區塊量計 bytes；reflink／跨 node 共用實體區塊不承諾精確去重。量不到完整範圍就不報完整值、另留診斷；移出工作樹不等於釋放 git 歷史，沿 [B-304](../base/identity-resources.md)及 [B-404](../base/storage.md)。

〔建議預設，未拍板〕用量 `network` 是 `{scope, rx_bytes, tx_bytes}` 陣列；`scope` 明寫量測邊界與計數起點（例如介面／namespace／本次計數器期間），bytes 是該 scope 的累積觀測值。計數器重置就換 scope，不能把負差值當用量；範圍重疊不相加，不能把 host 介面總量冒認為某 node 用量。首版只定可觀測摘要，**不定網路配額欄位與限速 backend**；需要硬限制的部署，在 backend 與授權尚未定義／不可用時應停止相關新工作並報出缺口，不假裝已限制。

## P-507．沒裝、失敗與驗證〔使用者方向 2026-09-29〕

沒裝 module＝該層不另記／另限，不等於父層限制消失；tick 互斥與程序清空不是可關閉的 module。已安裝但 controller／權限不可用是失敗，不能降成「沒裝」後繼續派工。額度不足時等待或寫待處理，不忙跑、不丟已回來的結果；取消與收尾仍可做，沿 [S-203](../scheduling/admission.md)。

〔建議預設，未拍板〕method 只引用 [messages P-306](messages.md)，錯誤封套沿 [P-005](README.md)。本地診斷用 `resource_unavailable`（所需能力不可用）、`resource_limit_exceeded`（額度不足）、`resource_observation_failed`（讀不到必要量測），它們不授權重做 unknown。語法錯誤、跨層授權、pool 重複、配額比較與觀測範圍重疊，分別由 JSON 解碼器、schema 或 module 語意檢查；schema 通過不是執行驗收。

## P-508．待決與跨篇

見 [README P-008](README.md#p-008)。
