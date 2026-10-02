# 資源：任務、配額與用量

← [共用約定](README.md)｜[資源正本](../scheduling/admission.md)｜[身分與資源](../base/identity-resources.md)｜[LLM](../scheduling/llm.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - `aos-as`（任務自己換帳號）：第十三批暫緩（[P-212](../settled/deferred/protocol/tick.md#p-212aos-as切換帳號建議預設未拍板)）；現行切帳號只在 daemon 設定檔做（帳號模組 [B-646](../settled/daemon/account.md)）。
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - `aos-tick-check-task`（原 `aos-needs`）：第十六批暫緩（[暫緩區 B-621](../settled/deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit/08-1001-node模組與統一更新.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

本篇只定**預設 kernel 範本**的資源 module 的檔案格式、欄位與 cgroup 檔對照；行為以 [S-203](../scheduling/admission.md)（框架、巢狀範圍、cgroup 兩級）、[S-205](../scheduling/admission.md)（選版、套用、調整、備援與故障）與 [S-207](../scheduling/admission.md)（用量收集）為正本。〔使用者方向 2026-09-30，第十八批〕資源由各 kernel 定義；六類（CPU、memory、pids、LLM、disk、network）是範本的資源，kernel 可以在同一份配額與用量檔裡放自己的資源名稱（[T-06](../terms.md)）。

## P-500．module 就是任務〔使用者方向 2026-09-29〕

module 是 [node P-202～204](../settled/protocol/tick.md) 的普通任務；範本的六類可各自選裝，不另加 module 表或 ABI。argv 由任務設定，cwd／stdin／stdout／stderr／環境／鎖沿 [P-203](../settled/protocol/tick.md)，不重取同 node 鎖。〔使用者方向 2026-09-30，第十九批，疑點裁定 4〕帳號照 [B-620](../settled/tick.md)：用 node inst 的帳號；任務沒有 `user`（2026-10-01 撤回），要換帳號就包 `aos-as`。

〔建議預設，未拍板〕直接開檔讀配額、已授權量測介面及必要本地證據；寫自己 node 的用量／分配狀態，由標準配備的 group 提交（[B-621](../settled/deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）。退出 0＝本步完成（額度不足而寫好摘要等待也是 0），2＝設定錯，125＝無法開始，1＝已開始但失敗。派工的任務怎麼讀資源狀態、擋什麼，見 [S-205](../scheduling/admission.md)。

## P-501．配額檔〔建議預設，未拍板〕

[res-quota.schema.json](schemas/res-quota.schema.json) 是父 kernel 在**自己 repo** 的 `state/resources/` 保存的直接成員配額，每份只管一個 `node_id`。頂層初始額度可在 `config/` 用同格式提供，這份的意思見 [S-205](../scheduling/admission.md)。檔名與引用由任務設定，不把 node 路徑當檔名。

| 欄位 | 意思 |
|---|---|
| `version` | 固定 `1` |
| `node_id` | 受分配的 node；共用 `NodeId`，不是授權證明 |
| `seq` | 此父子關係的配額修訂序號，正整數、遞增；不當作工作排隊序號 |
| `resources` | 只列實際分配的項目，可為 `{}`；範本六類的欄位見 P-503～P-506，其他鍵是 kernel 自訂資源 |

選版（`seq` 衝突、不用 mtime）見 [S-205](../scheduling/admission.md)。欄位省略表示這份檔**沒另給該項額度**，不是零、無限或解除父限；要降低、撤回既有分配要明確寫一版新的。哪些資源一定要落在父層範圍內見 [S-203](../scheduling/admission.md)。

〔使用者方向 2026-09-30，第十八批〕**自訂資源**：`resources` 裡範本六類以外的鍵，值的形狀由定義它的 kernel 自己定。範本六類的名稱意思固定，自訂資源不能拿這六個名字換別的形狀；〔暫定〕其他名稱的格式不另限。改寫檔案時不認得的鍵原樣保留（[C-07](../contracts.md)）；上層不認得時怎麼辦見 [S-203](../scheduling/admission.md)。

最小正例：[quota.minimal.valid.json](examples/resources/quota.minimal.valid.json)；[quota.custom_resource.valid.json](examples/resources/quota.custom_resource.valid.json) 示範自訂資源。主要錯例：[quota.negative_memory.invalid.json](examples/resources/quota.negative_memory.invalid.json)，負的記憶體 bytes 不合法。

## P-502．用量摘要與檔案交接〔建議預設，未拍板〕

[res-usage](schemas/res-usage.schema.json) 是子層的 `state/resources/` 用量：version:1、node_id、observed_at_ms、resources 必填，涵蓋 node 與受管子樹合計，含工具。只寫能量到的值，resources 可空，可含 kernel 自訂資源；上層不再重加子孫。缺項／讀不到／過時不是零（[S-207](../scheduling/admission.md)），過時門檻由 kernel 政策定。〔第十九批〕cgroup 走備援時，CPU、記憶體、pids 量不到總量，照缺項寫（[S-205](../scheduling/admission.md)）。

摘要的同 commit 讀取與只開摘要權限的發布依 [B-624](../settled/deferred/mq.md) 與 [messages P-307](messages.md)。改配額用 `kernel.quota.set`、要求重測用 `kernel.usage.measure`，參數、回應與授權只在 [messages P-306](messages.md) 定義；kernel.schedule.recheck 只重判排程。

〔使用者方向 2026-09-29，裁定「LLM 請求送去哪」〕成員自記用量、kernel 只收集時，逐次用量檔是成員 [agent P-703](agent-tasks.md) 的 `state/agent/usage/<request_id>.json`，收集任務見 [P-810](kernel-tasks.md)；讀法、缺值與按原發起 node＋attempt 去重依 [S-207](../scheduling/admission.md)。本篇的資源摘要不取代逐次 usage 證據。

[正例](examples/resources/usage.minimal.valid.json)；[反例](examples/resources/usage.negative_cpu.invalid.json) 的 CPU 累積用量為負。

## P-503．CPU、記憶體與 pids〔使用者方向 2026-09-29〕

〔使用者方向 2026-09-30，第十九批〕已裝 OS module 時，由標準配備的 cgroup 框寫進 cgroup v2（[B-629](../settled/deferred/template.md)）；cgroup 子樹、框命名與佈建以 [B-605](../settled/deferred/daemon/cgroup.md) 為正本，佈建參數見 [daemon P-107](../settled/deferred/protocol/daemon/provision-and-runner.md)；上限隨時可改，見 [S-205](../scheduling/admission.md)。下表只在 cgroup 走完整路時適用；走備援時 `cgroup_*` 回 `unsupported`，只剩每程序上限、沒有 pids 上限（[S-203](../scheduling/admission.md)、[B-631](../settled/deferred/cg.md)）。

| resources 欄位 | 配額 | 用量摘要 | cgroup 對應 |
|---|---|---|---|
| cpu | quota_us、period_us 正整數 | usage_us 非負整數 | cpu.max 原微秒值；cpu.stat 的 usage_usec |
| memory | bytes 正整數 | current_bytes 非負整數 | memory.max／memory.current |
| pids | max 正整數 | current 非負整數 | pids.max／pids.current（含 thread） |

CPU 是 [P-002](README.md) 時間單位的明示例外，不轉毫秒。limits 映為 `cpu_max:{quota_us,period_us}`、memory_max_bytes、pids_max；未配置項不傳，全無限制則不呼叫。比較 CPU 份額用 quota_us / period_us；配額不提供字串 max，實際值查詢才可能讀到它。usage_us 是目前 cgroup 存續期間的累積值，重建後不可接著取差值。

框的位置見 [B-605](../settled/deferred/daemon/cgroup.md)，掛載行程的資源歸屬見 [B-613](../settled/deferred/daemon/channel.md)，實際限制查詢見 [P-106](../settled/deferred/protocol/daemon/registration.md)；OOM 判定依 [B-204](../base/execution.md)。

## P-504．套用不是 git 回滾〔建議預設，未拍板〕

（第十八批：行為併入 [S-205](../scheduling/admission.md)，佈建動作見 [B-609](../settled/deferred/daemon/helper-actions.md)。）格式上只留一條：設定請求寫目標限制值，不能寫「再加一份」。

## P-505．路線與 LLM 份額〔使用者方向 2026-09-29，裁定「LLM 請求送去哪」〕

agent 只按設定的一個 node 位址投 `llm.chat`，請求與結果始終用 [llm-work P-406／407](llm-work.md) 的同一格式。kernel 的兩條份額路線（全管、不管派送）與 LLM 三檔以 [S-301](../scheduling/llm.md) 為正本，範本欄位怎麼填見 [P-813](kernel-tasks.md)；工具的 `tools.target_node` 路線同樣見 P-813，兩條路都沿 [work P-402](work.md)。〔第十九批〕資源歸掛行程的那個 tick 或它指定的下層（[B-613](../settled/deferred/daemon/channel.md)），不靠工作資料夾位置決定。

〔建議預設，未拍板〕以下是預設 kernel 範本的份額格式。配額 `llm` 是陣列，每項只有 `pool_id`（共用 `ID`）與 `concurrent_requests`（非負整數）；零表示不放行新請求。同檔不可重複 pool_id。這個 ID 是**配置該份額之 kernel 的路由名**，由 `config/llm-routes.json` 唯一對到下一個 node 與下一個 pool；本地終點才對到 [llm-work P-405](llm-work.md) 的 pools[].id。路由、授權及回件對照的格式只在 kernel 任務篇定。

用量 `llm` 每項是 `pool_id`、`active_requests`、`unknown_requests`；後兩者非負且**分開計數**。前者是已知仍占用的請求；後者是遠端執行／占用不明的請求，兩者合計占用份額。unknown 的估計占用什麼時候釋放，由池所屬 kernel 的池設定決定（[S-304](../scheduling/llm.md)），不綁 [P-606](ops.md) 的資料保留期；釋放也不表示遠端已停止。

本篇只編碼並行份額；共享 quota_scope 的窗口設定與 `state/llm/pool-status.json` 格式見 [P-811](kernel-tasks.md)，查詢見 [P-812](kernel-tasks.md)。〔第十九批〕同名池與 scope 共不共享、上下層份額、provider usage、429、unknown 與這些規則的驗收，以 [S-301～S-304](../scheduling/llm.md) 為正本；key 保護見 [llm-work P-405](llm-work.md)。

## P-506．磁碟與網路〔使用者方向 2026-09-29〕

磁碟與網路擋什麼、不擋什麼見 [S-203](../scheduling/admission.md)；磁碟框架見 [B-304](../base/identity-resources.md)，沒有 project quota 時怎麼定期量見 [S-207](../scheduling/admission.md)。

〔建議預設，未拍板〕配額 `disk.bytes` 是非負的記帳額度。用量 `disk` 是 `{path, bytes}` 陣列，列出實際盤點的絕對路徑與磁碟配置 bytes；`path` 含其可觀測子樹。範圍怎麼劃、hardlink 怎麼去重、量不到完整範圍怎麼辦，以 [S-207](../scheduling/admission.md) 的「磁碟怎麼量」為正本。

〔建議預設，未拍板〕用量 `network` 是 `{scope, rx_bytes, tx_bytes}` 陣列；`scope` 是字串，寫明量測邊界與計數起點（例如介面／namespace／本次計數器期間），bytes 是該 scope 的累積觀測值。計數器重置與範圍重疊怎麼處理見 [S-207](../scheduling/admission.md) 的「網路怎麼量」。首版只定可觀測摘要，**不定網路配額欄位與限速 backend**。

## P-507．沒裝、失敗與驗證〔使用者方向 2026-09-29〕

（第十八批：沒裝與失敗的行為併入 [S-205](../scheduling/admission.md)。）

〔建議預設，未拍板〕method 只引用 [messages P-306](messages.md)，錯誤封套沿 [P-005](README.md)。本地診斷用 `resource_unavailable`（所需能力不可用）、`resource_limit_exceeded`（額度不足）、`resource_observation_failed`（讀不到必要量測），它們不授權重做 unknown。語法錯誤、跨層授權、pool 重複、配額比較與觀測範圍重疊，分別由 JSON 解碼器、schema 或 module 語意檢查；schema 通過不是執行驗收。

## P-508．待決與跨篇

見 [README P-008](README.md#p-008)。
