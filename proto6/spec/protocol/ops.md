# 待處理事項與清理協議

← [共用約定](README.md)｜行為正本：[S-401／S-405](../scheduling/operations.md)、[B-404](../base/storage.md)

## P-600．範圍〔使用者方向 2026-09-29〕

本篇定 attention、aos-attend 與 aos-clean；權限與兩條請求路線只依 [共用約定](README.md)。

## P-601．兩處事項〔使用者方向 2026-09-29〕

attention 是交給人或 agent 手動處理的待辦清單，誰寫、何時寫以 [S-405](../scheduling/operations.md) 為正本，daemon 那側的停格事項見 [B-607](../settled/deferred/daemon/registration.md)。node 的事項放 `.aos/attention/open/<issue_id>.json`，標完成時搬到 `done/`；整個 `.aos/attention/` ignore，不隨 git 還原。once 單檔未啟動仍沿 [P-110](../settled/deferred/protocol/daemon/provision-and-runner.md) 的 `.err`。建 node 時須授 daemon 寫權。

daemon 產生的事項怎麼暫存、批次寫出見 [B-607](../settled/deferred/daemon/registration.md)。daemon 只保管 helper 消失、state 存不下等自身事項，平常走 IPC 查：ls／show 直接讀 `state_dir/attention/` 的檔案，加上記憶體裡還沒寫出的那幾筆；內有 `open/<source_key>/<issue_id>.json`、`done/<source_key>/<issue_id>.json`。source_node 用受影響的 root，source_key 是其 UTF-8 的 SHA-256 小寫十六進位。

兩處沿用 [ops-attention](schemas/ops-attention.schema.json)：必填 version、source_node、issue_id、reason、白話 `message`；可選 `suggestion` 是「建議處理」文字，可以附建議指令，但不會被自動執行。job_id／attempt_id／request_id 按需附；〔第十八批；第二十批疑點裁定 7 改成格數〕可選 `reported_seq` 是首次回報時寫的那個 node 的第幾格（[B-633](../settled/tick.md)），壞收件原件的保留期從這一格算（[B-404](../base/storage.md)）；取代 `reported_at_ms`。daemon 寫的事項沒有格數，不帶。不帶憑證或完整工作。〔使用者方向 2026-09-30，第十八批〕`argv` 是永遠禁止的鍵（[C-07](../contracts.md)），schema 寫 `"argv": false`，出現就整份拒收。

〔暫定，第十八批〕壞掉的收件（[B-623](../settled/tick/mq.md)）用 `reason:"bad_request"`，`issue_id` 是 `bad-request-` 加檔名 UTF-8 bytes 的 sha256 前 16 個小寫 hex，`request_id` 在檔名合法時附上。〔第二十批〕第十九批的 `standard_incomplete` 事項隨全掛檢查一起撤。

| method（對應 `aos daemon attention <動作>`） | params → result |
|---|---|
| `daemon.attention.done` | `{source_node,issue_id}` → 同形狀；人已處理完，把檔搬到 `done/` |
| `daemon.attention.show` | `{source_node,issue_id}` → 事項加 `status:"open"` 或 `"done"` |
| `daemon.attention.ls` | 可省 source_node、status（預設 open）、limit（1～64、預設 64）、after → `{issues:[show結果],next_after}` |

IPC 只查／標完成 daemon 自身事項。依可信登記 owner／祖先 owner 授權；ls 先篩選再按 `source_key/issue_id` bytes 分頁，after 用上頁 next_after，列完為 null。daemon 內部新增事項，不接受 node 代交。

〔第十九批依方案 A 縮短〕同一問題沿用 ID、標完成與保留期以 [S-405](../scheduling/operations.md) 為正本（壞收件例外：open 或 done 已有就不再寫，[B-623](../settled/tick/mq.md)）。寫檔依 P-003；daemon 自身 IPC／存檔錯誤走 stderr。`aos attend ls` 沿可見的上下層樹（[B-628](../settled/tick.md)）讀 node 目錄，合併 daemon IPC 成一張清單；檔案讀權仍由 OS 決定。

## P-603．aos-attend：列出、查看、標完成〔使用者方向 2026-09-29〕

```text
aos-attend ls --socket S [--source N] [--json]
aos-attend show N ID --socket S [--store node|daemon] [--json]
aos-attend done N ID --socket S [--store node|daemon] [--json]
```

人手入口把 `aos-attend` 換成 `aos attend`；N 是來源 node，ID 是事項 ID，store 預設 node。三個動作做什麼以 [S-405](../scheduling/operations.md) 為正本。ls 列出來源、ID、位置與 message；show 顯示 message 與有填才顯示的「建議處理」；show／done 查 daemon 時走相應 IPC；已在 done 再標一次不變。ls 可用 --source 篩來源；--json 時 ls／show 每筆輸出事項加 status，done 輸出 `{source_node,issue_id}`，沿 IPC done 的 result。

實際修理由人或 agent 自己下指令。用呼叫者權限，不取得 N 的身分；stdin 不讀，stdout 是查詢內容或完成的來源／ID，stderr 是白話錯誤。0 成功或清單為空；2 用法錯；125 無法開始；1 讀取、移檔或 IPC 失敗。done 不改工作結果，也不提交 git。agent 設定檢查的結束碼要不要跟 kernel 統一，延後（[P-008](README.md#p-008)）。

## P-605．aos-clean 的 argv 與設定〔建議預設，未拍板〕

```text
aos-clean [--node <node>] --config <設定檔>
```

〔使用者方向 2026-09-30，第二十批〕`aos-clean` 是系統級任務，在沒有 git 版範本裡排最後，有 git 版排在 `aos-git close` 之前（[B-629](../settled/tick/template.md)）；清理資格、保留期、鎖與提交以 [B-404](../base/storage.md) 為正本。`--node` 是 node id，省略用 cwd；設定檔相對路徑依呼叫 cwd。stdin 不讀（任務設定用 `/dev/null`）；stdout 一個 [ops-clean-report](schemas/ops-clean-report.schema.json) 加 LF，stderr 白話診斷。直接跑用執行者身分；tick 中用 tick 的有效帳號（任務沒有 `user`，2026-10-01；要換帳號包 `aos-as`，[B-620](../settled/tick.md)）。沒有自訂的必填環境；aos-clean 自己不切換身分。讀 node 的已提交工作／結果、消費與引用證據、必要 requests／responses 原件及設定；寫本 node 追蹤區的清理變動與設定的封存區，不清別的 node 或 submodule repo。

[ops-clean-config](schemas/ops-clean-config.schema.json) 只要求 `version:1`；〔第二十批，時長改格數，算本 node 的格〕`interval_ticks` 預設 1000、`retention_ticks` 預設 100000（〔使用者方向 2026-09-30，第二十批〕直接用格數訂：週期 1 秒時約 17 分鐘與 28 小時，週期 30 秒時約 8 小時與 35 日；取代 `interval_seconds` 86400、`retention_ms` 2592000000）、`batch_limit` 預設 64、`mode` 預設 `archive`，亦可明選 `delete`。`archive_dir` 只適用 archive，預設 node 內 ignored 的 `.archive/`；相對路徑依 `--node`。不自動改 `.gitignore`，該落點需事先配置為 ignored，或放 node repo 外。封存區不能指回被清理的日常資料或 requests／responses；無效設定回 2。

預設 agent／kernel 任務表各有一項 `aos-clean --config config/clean.json`，每格呼叫；任務表不加間隔欄位。aos-clean 自己在追蹤的 `state/ops/clean.json` 記 `{version:1,last_cleaned_seq}`（〔第二十批〕上次清理完成是本 node 第幾格，取代 `last_cleaned_at_ms`）；沒有這個檔就算已到期。現在第幾格：讀 `.aos/tick/current/record.json` 的 `seq`——在 tick 內就是本格（`$AOS_TICK_CWD/.aos/tick/current/record.json`，[P-213](../settled/protocol/tick.md)；2026-10-01 第九批紀錄拆成資料夾，原 `current.json`），tick 外直接跑就是最近一格；都讀不到（不知道 `seq`）時不清、回 0、stderr 印 `no_record`。何時更新見 [B-404](../base/storage.md)。

直接跑與在 tick 內跑時怎麼持鎖、誰提交，以 [B-404](../base/storage.md) 與 [B-602](../settled/tick.md) 為正本。〔使用者方向 2026-09-29〕不為清理另開全域定時程序或叫醒冷 node，有權限者可直接清退役 node。

〔建議預設，未拍板〕結束碼 `0`＝未到期、本批成功或無可清項，`2`＝用法／設定錯且未開始，`125`＝自身前置失敗且尚未開始改動；`1`＝已開始後的執行、保存或提交失敗。訊號依 wait 狀態判定。清哪些資料見 B-404。

## P-606．清理、封存與回報〔使用者方向 2026-09-29〕

候選資格與保留期起算點完全依 [B-404](../base/storage.md)／[B-503](../base/transport.md)，不重述終局、消費、引用與去重規則；〔第十八批〕候選含過了保留期的壞收件原件與本地動作的 `.stdout` 檔。每批最多 batch_limit 項；每次重新核對，通知 done 不免驗資格。〔建議預設，未拍板〕unknown 到期連同內部關聯與待收結果一起清，不等人工結案；估計占用何時釋放依 [S-304](../scheduling/llm.md)，資料保留依本條；其他內容仍依一般保護條件。預設 agent 遍歷沿 [agent P-716](agent-tasks.md)，kernel 沿 [P-814](kernel-tasks.md)。

archive 每項以 `archive_dir/<清理前_commit>/<node_相對路徑>` 保存（〔第二十批〕沒有 git 時 `<清理前_commit>` 換成 `seq-<本格的 seq>`，[B-632](../settled/tick/git.md)），以 P-003 寫副本，保留原目錄關係；歸檔索引可由原 commit 及相對路徑取得，不另造第二份工作狀態。封存、刪除、提交與故障恢復的行為以 [B-404](../base/storage.md) 為正本。

回報 `outcome`：`staged`＝本次在 tick 內做完的變動（沒有 git 時變動即生效；有 git 時待本格 `aos-git close` 提交，[B-630](../settled/tick/git.md)）；`committed`＝直接執行已提交；`unchanged`＝未到期、無變動；`failed`＝失敗並帶共用錯誤（開放版 `ErrorOpen`）。`archived_items`／`deleted_items` 是本批備好或已提交的項數，依 outcome 解讀；failed 不得被當成移除已生效。git 歷史回收延後（[P-008](README.md#p-008)）。

## P-607．schema 與最小範例〔建議預設，未拍板〕

Schema 與解析沿 [共用約定](README.md)，三份都放寬、不認得的欄位忽略（[P-007](README.md)）；正反例見下；授權、鎖、引用與 commit 留待實作驗收。

| 格式 | 最小正例 | 主要錯誤例及原因 |
|---|---|---|
| 事項 | [valid](examples/ops/attention.minimal.valid.json) | [invalid](examples/ops/attention.executable.invalid.json)：夾帶永遠禁止的 `argv` |
| 清理設定 | [valid](examples/ops/clean-config.minimal.valid.json) | [invalid](examples/ops/clean-config.unbounded.invalid.json)：batch_limit 為 0 |
| 清理回報 | [valid](examples/ops/clean-report.minimal.valid.json) | [invalid](examples/ops/clean-report.failed-without-error.invalid.json)：失敗缺錯誤 |

## P-608．待決與跨篇

見 [README P-008](README.md#p-008)。

## P-609．最小設定錯誤與修好後重驗〔主編補；依 A-102、CLI H-036 第 5、6 步〕

〔第十九批依方案 A 縮短〕誰檢查、錯了停什麼、事項誰寫與沿用同一 `issue_id`，以 [S-405](../scheduling/operations.md) 為正本；重驗持鎖、不送 LLM／不派 once／不 resume、修好後標完成，以 [A-102](../agent/configuration.md) 為正本。本條只留格式。

- **事項**：沿 P-601 寫在來源 node 的 `.aos/attention/`，`reason:"config_invalid"`；message 說檔案、欄位與原因，不夾設定全文或 key；suggestion 可寫建議的檢查指令。
- **檢查指令**：kernel 用 [P-805](kernel-tasks.md) 的 `aos-kernel-check`，agent 用 [P-712](agent-tasks.md) 的 `aos-agent-check`（兩者結束碼要不要統一延後，[P-008](README.md#p-008)）：

```text
aos-kernel-check --node /srv/aos/top
aos-agent-check --node /srv/aos/a --recheck
```

- 不加新的 RPC method；`kernel.schedule.recheck` 只管排程，不是設定重驗。
