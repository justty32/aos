# 待處理事項與清理協議

← [共用約定](README.md)｜行為正本：[S-401／S-405](../scheduling/operations.md)、[B-404](../base/storage.md)

## P-600．範圍〔使用者方向 2026-09-29〕

本篇定 attention、aos-attend 與 aos-clean；權限與兩條請求路線只依 [共用約定](README.md)。

## P-601．attention_dir 與事項檔〔建議預設，未拍板〕

使用者指定絕對 attention_dir；布局為 `open/<source_key>/<issue_id>.json` 與 `done/<source_key>/<issue_id>.json`。source_key 是正規化 source_node UTF-8 的 SHA-256 小寫十六進位。

[ops-attention](schemas/ops-attention.schema.json) 必填 version、source_node、issue_id、reason、message、actions；actions 是處理表 ID，無可用項就 []。job_id／attempt_id／request_id 按需附，結果不明用 reason:unknown。通知不帶程式、憑證或完整工作；核對路徑與正文來源／ID，權限只開給可看摘要／處置者。

每檔最多 256 KiB，發布依 P-002／003。同一問題沿用 ID，異內容不覆蓋；解除後再發生用新 ID。來源保留實際問題並補遺失通知；daemon 的啟動問題由 daemon 核對。

只有來源確認解除才 rename 到同鍵 done，不覆蓋並 fsync 兩端；相符 done 可補完搬移、異內容報衝突。寫不出報 stderr，不宣稱已保存或解除 unknown。done 由來源保存搬入時間，預設留 30 日、仍被引用就留；來源退役交有權限者手動處理，不讓 clean 掃別的來源。

## P-602．人與 agent 都能編輯的處理表〔建議預設，未拍板〕

[ops-handlers](schemas/ops-handlers.schema.json) 為 `{version:1,handlers:[...]}`。列的 id 唯一，須在事項 actions 內且 reason 相符。safety 為 safe／dangerous／human，effect 是白話影響；human 無 action，其餘選一種：

| action.kind | 欄位及執行 |
|---|---|
| exec | argv 非空陣列直接 exec，stdin 給事項 JSON，cwd 為操作者 --node；不展開通知文字或自動套 shell |
| daemon_ipc | socket、method、params，可帶 bindings，組 RpcRequest 送 daemon |
| node_rpc | target_node、method、params，可帶 bindings，組 FileRpcRequest，reply_to 為操作者 node |

RPC id 用 operation_id、jsonrpc 固定 2.0。bindings 只將 source_node、issue_id、job_id、attempt_id、request_id、operation_id 搬到指定頂層參數；前五取事項、末項取本次動作。缺來源或與 params 撞鍵就拒，無插值、遞迴或指示詞；完成後照目標 schema／授權驗。

表由操作者明選，一次讀定，不能從通知目錄載入；追蹤設定的修改依 [A-102](../agent/configuration.md)。unknown 可執行列強制 dangerous，不能改標籤跳過確認。method 只用 [messages P-306](messages.md)／[daemon P-103](daemon.md)；尚缺的 unknown／run 接口用明選的部署 adapter，沒有就 action_not_available，不虛構 method。

## P-603．aos-attend 呼叫與確認〔建議預設，未拍板〕

完整 argv：

```text
aos-attend --node <操作者_node> --attention-dir <絕對路徑> --handlers <檔案> [--source <來源_node> --issue <ID>] [--action <ID>]
```

source／issue 一起給，省略看全部可讀 open。未選 action 只自動做唯一匹配的 safe；沒有／多個就列出，human 只顯示。不提供 --yes／--yes-all，傳入回 2。安全／危險界線依 [S-405](../scheduling/operations.md)，unknown 處置依 S-401，不在本工具重判。

stdin 不讀資料；只從 /dev/tty 問逐件 y/n，stderr 顯示來源、工作與影響。只接受去空白的 y／Y；其他字、EOF、無終端都跳過並保持 open。stdout 每項一行 [ops-action-record](schemas/ops-action-record.schema.json)＋LF，診斷及子程式輸出走 stderr。

讀 open、處理表與操作者紀錄；寫 P-604 紀錄／請求及目標 inbox，不自行移通知或改原工作結果。使用執行者身分、記實際有效 UID；--node 不授權。其他相對參數依呼叫 cwd，PATH 沿環境；exec adapter 收 AOS_ATTEND_NODE／AOS_ATTEND_OPERATION_ID 供定位，皆非憑證。

退出：0 全有回應／已送出或無 open；3 有跳過／human；1 有失敗或不明（優先於 3）；2 用法／表錯，尚未開始；125 工具前置失敗、尚未寫入。開始後的執行／紀錄／commit 失敗回 1，不能據此重做；子程式碼不直接當工具碼，訊號看 wait。

## P-604．動作紀錄、路由與失敗〔建議預設，未拍板〕

每次明示新動作配 operation_id，追蹤在 `state/ops/actions/<operation_id>/`。[ops-action-record](schemas/ops-action-record.schema.json) 記來源／事項、action、actor_uid、at_ms、outcome、message。執行前 prepared.json，之後另寫 result.json；跳過只寫 result，尚未選 action 的 skipped 可省 action_id。RPC 原請求存 request.json，不套新封套。

直接呼叫先取 node 鎖、確認乾淨、提交 prepared／請求，再釋鎖執行；完成後取鎖提交 result。不要把本體掛進已持鎖 tick；tick 使用 adapter／收件任務。無變動不 commit。

exec 正常 0 記 succeeded，非零／訊號記 failed，只表示本步。IPC 最多等 30000 ms，斷線／逾時無可信回應記 unknown；檔案 RPC 依 [messages](messages.md) 發布，成功只記 submitted，由後續收件任務接回應，不原地等 tick。

prepared 無結果不自動再做；允許的重送沿用原請求，unknown 的新動作須逐次確認、配新 operation ID（不是 attempt ID）。來源仍核對授權與原工作，不信紀錄自報 UID，也不把 submitted／exec 0 當解除問題。

錯誤沿 P-005，data.code：handler_invalid、action_not_available、confirmation_required、action_unknown、attention_conflict、clean_blocked、archive_failed、commit_failed；預設 retryable:false，目標 RPC 錯誤原樣保留。

## P-605．aos-clean 的 argv 與設定〔建議預設，未拍板〕

```text
aos-clean --node <node> --config <設定檔> [--in-tick]
```

`--node` 是 node id，設定檔相對路徑依呼叫 cwd。stdin 不讀（任務設定用 `/dev/null`）；stdout 一個 [ops-clean-report](schemas/ops-clean-report.schema.json) 加 LF，stderr 白話診斷。直接跑用執行者身分；tick 中用該 node inst 的 `user`。無自訂必填環境或身分切換。讀 node 的已提交工作／結果、消費與引用證據、必要 inbox 原件及設定；寫本 node 追蹤區的清理變動與設定的封存區，不清別的 node 或 submodule repo。

[ops-clean-config](schemas/ops-clean-config.schema.json) 只要求 `version:1`；`retention_ms` 預設 2592000000（30 日）、`batch_limit` 預設 64、`mode` 預設 `archive`，亦可明選 `delete`。`archive_dir` 只適用 archive，預設 node 內 ignored 的 `.archive/`；相對路徑依 `--node`。不自動改 `.gitignore`，該落點需事先配置為 ignored，或放 node repo 外。封存區不能指回被清理的日常資料或 inbox；無效設定回 2。

直接跑取得 B-602 同一把鎖，確認工作區乾淨後自己提交清理；不把別人的未提交修改順手 commit／還原。`--in-tick` 只供持鎖的 tick 呼叫，按 [node P-203](node.md) 核對繼承的 AOS_TICK_LOCK_FD，不能把旗標當成已持鎖或授權證據；它不另取鎖、不自行 commit，由所在 group 決定。〔使用者方向 2026-09-29〕無事不 commit；不為清理另開全域定時程序或叫醒冷 node，有權限者可直接清退役 node。

〔建議預設，未拍板〕結束碼 `0`＝本批成功或無可清項，`2`＝用法／設定錯且未開始，`125`＝自身前置失敗且尚未開始改動；`1`＝已開始後的執行、保存或提交失敗。候選不符合保留條件屬正常保留；若缺失資料使安全性無法判斷，保留並回報 `clean_blocked`，不能猜著清。訊號依 wait 狀態判定。

## P-606．清理、封存與回報〔使用者方向 2026-09-29〕

候選資格完全依 [B-404](../base/storage.md)／[B-503](../base/transport.md)，不重述終局、消費、引用與去重規則。每批最多 batch_limit 項；每次重新核對，通知 done 不免驗資格。〔建議預設，未拍板〕採用 run 從 run 終局起算，否則從工作終局起算，不用 mtime 猜。領域尚無可信遍歷契約時保留並報 clean_blocked，缺口收在 [P-008](README.md#p-008)，不能靠檔名推定可清。

archive 每項以 `archive_dir/<清理前_commit>/<node_相對路徑>` 保存，先以 P-003 寫完整副本並核對內容，再移除日常副本；已存在且相同可補做，不同則 `archive_failed`。保留原目錄關係及查找所需的既有識別／引用，不追隨 symlink 去清 node 外內容。歸檔索引可由原 commit 及相對路徑取得，不另造第二份工作狀態。delete 只省略封存步驟，其餘資格與提交規則相同。

追蹤區移除與引用更新一起隨本 repo 的 group 提交；封存區本身不受該 group 還原。中斷時可能留下多餘封存副本，補做先核對，不因已有封存檔就直接刪日常材料。滿碟、I/O 或 commit 失敗保留舊 commit 及未消費 inbox 原件，停止後續變動並照 B-404 恢復，不回成功。

回報 `outcome`：`staged`＝本次在 tick 內備好、尚待 group commit；`committed`＝直接執行已提交；`unchanged`＝無變動；`failed`＝失敗並帶共用 Error。`archived_items`／`deleted_items` 是本批備好或已提交的項數，依 outcome 解讀；failed 不得被當成移除已生效。`history_space_reclaimed` 固定 false：只承諾移出日常檔案與 context，封存可能仍在同碟，git 歷史仍占空間，不能把刪工作樹或普通 `git gc` 報成回收磁碟。

## P-607．schema 與最小範例〔建議預設，未拍板〕

JSON Schema 2020-12；共用型別只引用 [common.schema.json](schemas/common.schema.json)。每列一正一誤；解析層另驗 P-002 的 UTF-8、重複 key、非有限數與尾隨資料，schema 不替代它。授權、鎖、引用、確認與 commit 的驗收仍要實作後測。

| 格式 | 最小正例 | 主要錯誤例及原因 |
|---|---|---|
| 事項 | [valid](examples/ops/attention.minimal.valid.json) | [invalid](examples/ops/attention.executable.invalid.json)：通知夾帶 argv |
| 處理表 | [valid](examples/ops/handlers.minimal.valid.json) | [invalid](examples/ops/handlers.unknown_safe.invalid.json)：unknown 標為安全 |
| 動作紀錄 | [valid](examples/ops/action-record.minimal.valid.json) | [invalid](examples/ops/action-record.claimed_resolution.invalid.json)：動作自行宣稱 resolved |
| 清理設定 | [valid](examples/ops/clean-config.minimal.valid.json) | [invalid](examples/ops/clean-config.unbounded.invalid.json)：batch_limit 為 0 |
| 清理回報 | [valid](examples/ops/clean-report.minimal.valid.json) | [invalid](examples/ops/clean-report.reclaimed.invalid.json)：冒稱已回收歷史空間 |

## P-608．待決與跨篇

見 [README P-008](README.md#p-008)。
