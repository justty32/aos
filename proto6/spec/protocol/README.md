# 協議篇：共用約定與分工

← [規格入口](../README.md)｜[名詞](../terms.md)｜[daemon](../daemon.md)｜[通用 tick](../tick.md)｜[inst](../base/inst.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)｜[條號索引](#p-index)

2026-09-29 依 node 架構整合。本篇把主規格落成**程式之間**的指令形狀、JSON 與資料夾交接。人手操作見 [CLI](../cli.md)；本篇定機器用的形狀，同一批程式人也能直接跑（[通則](../README.md#原則能下指令能管檔案就能交給-agent)）。

## P-001．範圍與原則〔主編補〕

- 主規格是行為正本，本篇只定編碼與傳送方式；兩邊衝突以主規格和裁定為準，發現缺口寫進 P-008，不在格式裡偷定新行為。
- **兩條請求路線**〔使用者方向 2026-09-29〕：要 daemon／helper 做事＝**IPC 找 daemon**（本機 socket 上的 JSON-RPC）；要別的 node（上層 kernel、LLM 代發服務、別隊 agent）做事＝**檔案承載的 JSON-RPC**，投進對方收件區。沒有第三種。
- 精簡：一個格式能用就不做兩個；欄位只放主規格真的需要的；不為 agent、工具另開入口。
- 原生 Linux 與 WSL2 同一套格式。

## P-002．JSON〔建議預設，未拍板〕

- UTF-8、無 BOM；一份檔案或一行訊息恰好一個 JSON object。拒絕重複 key、非有限數、尾隨資料。
- ID 是字串：`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`，可直接當檔名。node id 是 node 資料夾的絕對路徑（正規化、無 `..`、無結尾 `/`）。
- 時間點用 UTC 毫秒整數、時長用毫秒，欄位名以 `_ms` 結尾；明示例外：清理設定 `interval_seconds` 用秒；cgroup CPU 的`quota_us`、`period_us`、`usage_us` 直接用微秒，不換算或捨去精度；逾時用經過時間，排先後用序號，不靠牆鐘、mtime 或檔名排序。
- 自己的持久 JSON 檔帶 `"version": 1`，未知版本拒絕；inst 與 tasks 用自己的 `_metainfo`，JSON-RPC 用 `"jsonrpc": "2.0"`，不另加 `version`。
- 未知欄位：協議物件預設拒絕；要擴充的地方明列 `ext` object。

## P-003．檔案發布與收件〔建議預設，未拍板〕

- **發布**：在目標資料夾的 `.tmp/` 寫完、fsync、rename 成正式名，再 fsync 目錄。名字以 `.` 開頭的一律不處理。rename 不覆蓋已有檔；撞名須比對內容，見 [messages P-304](messages.md)。
- **收件區**〔使用者方向 2026-09-29〕：每個 node 根下的 `requests/`（別人問我）與 `responses/`（我問別人、別人回我），都在 `.gitignore` 裡；`inbox` 這名字保留給日後的工具，不當資料夾名。投件者要對目標那格有寫權限（權限怎麼開見 node.md）。收件只看檔案，不看 inotify；inotify／IPC 叫醒只是門鈴，可遺失。
- **去重**：檔名就是請求 ID；同 ID 同內容已有檔／已提交紀錄＝收過。內容不同的同 ID 當衝突，寫一件待處理事項，不猜。
- **消費**（[Q1](../tick.md)）：任務保存原件，tick 在 group commit 後才刪相同收件原件（P-206）。
- **送出**（[Q2](../tick.md)）：任務寫 `.aos/outbox/`，tick 在 group commit 後才投出請求／回應（P-206）。

## P-004．JSON-RPC 的兩種載體〔建議預設，未拍板〕

物件形狀照 JSON-RPC 2.0：請求 `{"jsonrpc":"2.0","id":"<ID>","method":"...","params":{...}}`，回應 `{"jsonrpc":"2.0","id":"<ID>","result":{...}}` 或 `"error":{...}`。`id` 必填且是 P-002 的 ID；唯解析／請求錯誤（-32700／-32600）取不到合法 ID 時，回應用 `id:null`，成功回應與請求仍不准 null；不用 batch、不用 notification。公開 method 就是對應指令去掉 `aos`、以 `.` 連接，例如 `agent.say` 對 `aos agent say`；內部 helper 用 `daemon.helper.*` 對 `aos daemon helper ...`，仍只走私有通道。

1. **socket（daemon IPC）**：Unix stream socket，一行一個 object、以 LF 結尾，單行上限 256 KiB。呼叫者身分只看 `SO_PEERCRED`，封包裡自稱的身分不算。
2. **檔案（node 之間）**：params 是一份 inst，argv 保留 `aos`，展開後必須和 method 對上同一條已開放指令，否則 -32601；回應 result 用 [work-result](work.md) 的指令執行結果。請求檔名 `<id>.json`，內容就是上面的請求物件，外加頂層 `"reply_to"`：回應要投去的收件區（node id）。子目錄及回件規則見 [messages P-301～303](messages.md)；檔案回應必須有合法 ID，壞件沒有可信 ID／回址就只留本地診斷及事項，不產生 `null.json`。檔案上限 256 KiB，大內容放檔案、用路徑引用。對方不常駐，回應可能要好幾格 tick 後才來；沒回應不代表沒做，查詢或重送一律用同一個 `id`。

## P-005．錯誤〔建議預設，未拍板〕

JSON-RPC `error` 的 `code` 照 2.0 保留碼（-32700 解析、-32600 請求不合法、-32601 沒這個 method、-32602 參數不合法、-32603 內部）；其他一律 -32000，真正的意思放 `error.data.code`（小寫底線字串，例如 `user_not_granted`、`not_registered`、`busy`），另帶 `error.data.retryable`（bool）。各篇列自己的 `data.code`，不另編數字碼。錯誤訊息不夾帶別的 node 的內容或 key。

## P-006．程式：argv、環境、結束碼〔建議預設，未拍板〕

- 每支程式的篇章要列：完整 argv、stdin／stdout／stderr 各放什麼、讀寫哪些檔、用誰的身分跑、環境變數、結束碼。
- argv 直接 exec，不經 shell。大資料走 stdin 或檔案，不塞 argv；key 永遠不進 argv 或環境給 node。
- aos 自己的環境變數用 `AOS_` 開頭；環境不是授權依據。
- 結束碼共同意思：`0` 成功；`2` 用法或設定錯，還沒開始做事；`125` 自己無法開始（如身分不准）；runner 收尾失敗也是 125，須以 P-110 的 started／error 區分，不能只看碼。其他碼由各篇自己定；被訊號殺掉由父程序看 wait 狀態，不猜 `128+n`。
- 程式名：daemon 是 `aos daemon`；其他沿主規格已有名字（`aos-tick`、`aos-clean`、`aos-attend`）。新公開指令用 `aos <用途> <動作> [更深]`。

## P-007．schema 與範例〔主編補〕

- schema 用 JSON Schema 2020-12，放 `schemas/`，檔名以該篇前綴開頭（例如 `daemon-register.schema.json`）。共用型別（ID、NodeId、TimeMs、Error、JSON-RPC）只在 `schemas/common.schema.json` 的 `$defs`，各篇以相對 `$ref` 引用。
- 範例放 `examples/<篇名>/`，命名 `<主題>.<情境>.valid.json`／`.invalid.json`；每個 invalid 在正文說明為什麼錯。**只做真的需要的範例**：每種訊息一個最小正例、一個主要錯誤；不求量。
- schema 通過不代表授權或狀態正確；那些由主規格的驗收管。

<a id="p-008"></a>

## P-008．暫定與待決〔建議預設，未拍板〕

### 已裁定（第十一批）

- **once 資源歸屬與啟動失敗證據**〔使用者方向 2026-09-29〕：照 [daemon P-104／110](daemon.md)；以可信 parent_id 固定算在發起 node 的資源框內，runner 根本沒啟動時由 daemon 在 inst 檔名後加 `.err` 寫旁檔（例如 `job.json.err`）。
- **首版網路**〔使用者方向 2026-09-29〕：只記用量摘要，不做硬限速；要求硬限速的部署明確報不支援（[resources P-506](resources.md)）。

### 工程預設與待補接口

第九批已准工程數字先照建議、實作量過再調；各篇「建議預設」可替換，不逐條再問使用者。

- 首次由父 kernel 登記、既有項可重登；IPC、bytes 去重、摘要發布、資源 method、鎖 fd 與故障停格，依 [daemon](daemon.md)、[messages](messages.md)、[node](node.md)。
- **LLM 共享窗口與池狀態**：最小格式及估算由 [kernel P-811～812](kernel-tasks.md) 定義；unknown 的估計占用隨定期清理移除，不當作遠端已停止的證據。相同 provider 限制交同一池管理 node，不能靠同名 scope 跨 node 同步（[resources P-505](resources.md)）。
- **領域接口**：模型／人格／工具 adapter、正式回話、context 與預設清理遍歷已由 [agent 任務篇](agent-tasks.md) 及 [kernel 任務篇](kernel-tasks.md) 定義。unknown 放著隨定期清理，不自動重做；不做自訂清理接口。
- done 留存、磁碟 hardlink 計量與池路由照各篇工程預設；格式驗證不等於產品實作。

## P-009．分工表〔主編補〕

| 篇章／條款 | 唯一正本責任 |
|---|---|
| [daemon](daemon.md)／P-100～ | 設定、IPC／helper、註冊與資源框、runner 及故障證據 |
| [node](node.md)／P-200～ | 布局、inst／tasks、tick、鎖、git 與設定匯入 |
| [messages](messages.md)／P-300～ | 檔案路由、去重、method 目錄、摘要讀取／發布 |
| [work](work.md)／P-400～ | once 工作、結果、LLM 池與程式契約 |
| [resources](resources.md)／P-500～ | module、配額／用量與各類資源 |
| [ops](ops.md)／P-600～ | 待辦、aos-attend、aos-clean |
| [agent 任務](agent-tasks.md)／P-700～ | agent 設定、工具、對話、context、用量及建立範本 |
| [kernel 任務](kernel-tasks.md)／P-800～ | 持久成員、排程、工作轉交、LLM 路由／池及建立範本 |

## P-010．inst 目標：檔案或資料夾〔使用者方向 2026-09-29〕

沿 proto5 `aos-exec xxx` 的慣例，凡是「給一個目標去跑 inst」（daemon 註冊、runner、人手直接跑）都照這條找 inst：

| 目標 `xxx` 是 | 用哪份 inst | base（相對路徑起點、`cwd` 沒寫時的預設） |
|---|---|---|
| 檔案 | 就是它，當 inst JSON 讀 | 檔案所在的資料夾 |
| 資料夾 | 先找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json` | `xxx` 自己 |

〔使用者方向 2026-09-29〕首版**不提供**改尋找路徑的選項（環境變數或旗標都沒有），只照上表。資料夾裡兩個位置都沒有＝用法錯（2）。先看是不是資料夾，再當檔案。node 是資料夾；`once` 工作通常是單檔。登記的 id 就是這個目標路徑。

<a id="p-index"></a>

## 條號索引（P-xxx → 檔案）

協議篇各條所在的檔案；別篇多用條號引用，照這張表找。檔案拆分或搬位置時條號不變，只改這張表。

| 條號 | 標題 | 檔案 |
|---|---|---|
| P-001 | 範圍與原則 | [README.md](README.md)（本篇） |
| P-002 | JSON | [README.md](README.md)（本篇） |
| P-003 | 檔案發布與收件 | [README.md](README.md)（本篇） |
| P-004 | JSON-RPC 的兩種載體 | [README.md](README.md)（本篇） |
| P-005 | 錯誤 | [README.md](README.md)（本篇） |
| P-006 | 程式：argv、環境、結束碼 | [README.md](README.md)（本篇） |
| P-007 | schema 與範例 | [README.md](README.md)（本篇） |
| P-008 | 暫定與待決 | [README.md](README.md)（本篇） |
| P-009 | 分工表 | [README.md](README.md)（本篇） |
| P-010 | inst 目標：檔案或資料夾 | [README.md](README.md)（本篇） |
| P-100 | 範圍 | [daemon/README.md](daemon/README.md) |
| P-101 | 啟動、設定與 socket | [daemon/startup-and-ipc.md](daemon/startup-and-ipc.md) |
| P-102 | sudo 與 helper 生死 | [daemon/startup-and-ipc.md](daemon/startup-and-ipc.md) |
| P-103 | IPC 封包與授權 | [daemon/startup-and-ipc.md](daemon/startup-and-ipc.md) |
| P-104 | 註冊 | [daemon/registration.md](daemon/registration.md) |
| P-105 | 解除、叫醒、暫停與恢復 | [daemon/registration.md](daemon/registration.md) |
| P-106 | 查登記與最近一格 | [daemon/registration.md](daemon/registration.md) |
| P-107 | 佈建固定動作 | [daemon/provision-and-runner.md](daemon/provision-and-runner.md) |
| P-108 | daemon 與 helper 的私有通道 | [daemon/provision-and-runner.md](daemon/provision-and-runner.md) |
| P-109 | runner argv 與解析 | [daemon/provision-and-runner.md](daemon/provision-and-runner.md) |
| P-110 | runner 結束與 125 | [daemon/provision-and-runner.md](daemon/provision-and-runner.md) |
| P-111 | 錯誤 | [daemon/provision-and-runner.md](daemon/provision-and-runner.md) |
| P-112 | schema 與最小範例 | [daemon/provision-and-runner.md](daemon/provision-and-runner.md) |
| P-113 | 待決與跨篇 | [daemon/README.md](daemon/README.md) |
| P-114 | 前景 Ctrl-C 停機 | [daemon/shutdown.md](daemon/shutdown.md) |
| P-115 | 啟動 ID 與按需重建 | [daemon/registration.md](daemon/registration.md) |
| P-116 | 存檔與重開 | [daemon/shutdown.md](daemon/shutdown.md) |
| P-200 | 資料夾布局 | [node.md](node.md) |
| P-201 | inst 的格式與展開驗證 | [node.md](node.md) |
| P-202 | 任務註冊表 | [node.md](node.md) |
| P-203 | aos-tick 與任意任務程式 | [node.md](node.md) |
| P-204 | 成敗、group 與 needs | [node.md](node.md) |
| P-205 | git 提交與恢復 | [node.md](node.md) |
| P-206 | 收件與派送的提交邊界 | [node.md](node.md) |
| P-207 | 加入普通設定與重要設定手改 | [node.md](node.md) |
| P-208 | 收件區權限 | [node.md](node.md) |
| P-209 | 待決與跨篇 | [node.md](node.md) |
| P-210 | 預設範本與恢復前驗證 | [node.md](node.md) |
| P-300 | 兩條路各做什麼 | [messages.md](messages.md) |
| P-301 | 收件區分請求與回應 | [messages.md](messages.md) |
| P-302 | 完整封包 | [messages.md](messages.md) |
| P-303 | 回應路由與來源 | [messages.md](messages.md) |
| P-304 | 同 ID、衝突與重送 | [messages.md](messages.md) |
| P-305 | 送出、消費與門鈴順序 | [messages.md](messages.md) |
| P-306 | method 就是指令 | [messages.md](messages.md) |
| P-307 | 上層直接讀成員摘要 | [messages.md](messages.md) |
| P-308 | schema 與最小範例 | [messages.md](messages.md) |
| P-309 | 待決與跨篇 | [messages.md](messages.md) |
| P-400 | 兩個入口 | [work.md](work.md) |
| P-401 | 工作材料 | [work.md](work.md) |
| P-402 | once 與工作材料 | [work.md](work.md) |
| P-403 | 結果與串流 | [work.md](work.md) |
| P-404 | unknown 與拒收 | [work.md](work.md) |
| P-405 | 代發啟動與池設定 | [llm-work.md](llm-work.md) |
| P-406 | LLM 請求與 messages | [llm-work.md](llm-work.md) |
| P-407 | LLM 結果、usage 與有限重試 | [llm-work.md](llm-work.md) |
| P-408 | 程式契約 | [work.md](work.md) |
| P-409 | schema 與最小範例 | [work.md](work.md) |
| P-410 | 待決與跨篇 | [work.md](work.md) |
| P-500 | module 就是任務 | [resources.md](resources.md) |
| P-501 | 配額檔 | [resources.md](resources.md) |
| P-502 | 用量摘要與檔案交接 | [resources.md](resources.md) |
| P-503 | CPU、記憶體與 pids | [resources.md](resources.md) |
| P-504 | 套用不是 git 回滾 | [resources.md](resources.md) |
| P-505 | 路線與 LLM 份額 | [resources.md](resources.md) |
| P-506 | 磁碟與網路 | [resources.md](resources.md) |
| P-507 | 沒裝、失敗與驗證 | [resources.md](resources.md) |
| P-508 | 待決與跨篇 | [resources.md](resources.md) |
| P-600 | 範圍 | [ops.md](ops.md) |
| P-601 | 兩處事項 | [ops.md](ops.md) |
| P-603 | aos-attend：列出、查看、標完成 | [ops.md](ops.md) |
| P-605 | aos-clean 的 argv 與設定 | [ops.md](ops.md) |
| P-606 | 清理、封存與回報 | [ops.md](ops.md) |
| P-607 | schema 與最小範例 | [ops.md](ops.md) |
| P-608 | 待決與跨篇 | [ops.md](ops.md) |
| P-609 | 最小設定錯誤與修好後重驗 | [ops.md](ops.md) |
| P-700 | 範圍 | [agent-tasks.md](agent-tasks.md) |
| P-701 | 設定檔 | [agent-tasks.md](agent-tasks.md) |
| P-702 | 工具清單與參數 adapter | [agent-tasks.md](agent-tasks.md) |
| P-703 | 檔案落點 | [agent-tasks.md](agent-tasks.md) |
| P-704 | 一項 module、一項任務 | [agent-tasks.md](agent-tasks.md) |
| P-705 | 收話與收結果 | [agent-tasks.md](agent-tasks.md) |
| P-706 | 組 context 與發 LLM | [agent-tasks.md](agent-tasks.md) |
| P-707 | 模型決定與兩種工具路線 | [agent-tasks.md](agent-tasks.md) |
| P-708 | 正式回覆 | [agent-tasks.md](agent-tasks.md) |
| P-709 | 投件故障與恢復 | [agent-tasks.md](agent-tasks.md) |
| P-710 | agent 自記用量 | [agent-tasks.md](agent-tasks.md) |
| P-711 | 工具清單 CLI | [agent-tasks.md](agent-tasks.md) |
| P-712 | 設定檢查與重驗 | [agent-tasks.md](agent-tasks.md) |
| P-713 | say／listen | [agent-tasks.md](agent-tasks.md) |
| P-714 | replies／context | [agent-tasks.md](agent-tasks.md) |
| P-715 | new 的完整產物 | [agent-tasks.md](agent-tasks.md) |
| P-716 | 最小清理遍歷 | [agent-tasks.md](agent-tasks.md) |
| P-717 | 格式驗收 | [agent-tasks.md](agent-tasks.md) |
| P-800 | 共同契約 | [kernel-tasks.md](kernel-tasks.md) |
| P-801 | 設定與持久成員 | [kernel-tasks.md](kernel-tasks.md) |
| P-802 | 增刪成員與按需同步 | [kernel-tasks.md](kernel-tasks.md) |
| P-803 | 何時叫醒 | [kernel-tasks.md](kernel-tasks.md) |
| P-804 | 分配與量測 | [kernel-tasks.md](kernel-tasks.md) |
| P-805 | 壞設定與重驗 | [kernel-tasks.md](kernel-tasks.md) |
| P-806 | 工具 once module | [kernel-tasks.md](kernel-tasks.md) |
| P-807 | 中斷與恢復 | [kernel-tasks.md](kernel-tasks.md) |
| P-808 | LLM 路由表 | [kernel-tasks.md](kernel-tasks.md) |
| P-809 | LLM 轉交 module | [kernel-tasks.md](kernel-tasks.md) |
| P-810 | 用量收集 module | [kernel-tasks.md](kernel-tasks.md) |
| P-811 | 池與共享窗口 | [kernel-tasks.md](kernel-tasks.md) |
| P-812 | 唯讀查詢 | [kernel-tasks.md](kernel-tasks.md) |
| P-813 | 建立 agent 的兩條路 | [kernel-tasks.md](kernel-tasks.md) |
| P-814 | 完整範本與走查 | [kernel-tasks.md](kernel-tasks.md) |
| P-815 | 格式驗收 | [kernel-tasks.md](kernel-tasks.md) |
