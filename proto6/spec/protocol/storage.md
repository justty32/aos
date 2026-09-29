# 儲存協議：材料、待辦通知與有限清理

← [共用約定與分工](README.md)｜[儲存正本](../base/storage.md)｜[通訊 B-505](../base/transport.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)

## P-500．責任與讀法〔主編補〕

本篇只管材料保存與交付，不發 `accepted`、不提交 checkpoint、不派工、不自行解除屏障。控制 writer 仍是唯一 SQLite writer；adapter、`aos-clean` 與 attention 都不能變成第二份權威。C-01～C-06、B-401～B-404、B-505、A-303／A-506、S-404／S-405 及 09-29 裁定是行為來源；以下新增 argv、記錄名稱及 fd 編碼均為〔建議預設，未拍板〕，不表示已有實作。P-011 的八項整合暫定仍可被使用者推翻。

JSON、ID、未知欄位、原始 token 檢查與退出碼依 P-002／P-006～P-009。本文 schema 在 [schemas/](schemas/)，只以相對 `$ref` 引用 `control-common.schema.json#/$defs/ID`、`BlobRef`、`Error`；不複製共同型別。schema 中 `kind` 是本篇的訊息辨識，不是 Job.kind。所有 metadata 單封建議上限 256 KiB，解析前限 bytes；stderr／其他診斷最多 64 KiB。陣列的 256 件與 evidence 32 件是編碼上限，部署批次可以更小。整數、字元長度、JSON bytes 是不同限制。

驗收：Given import 回 BlobRef，When 尚未呼叫 agent.submit 或 checkpoint.commit，Then 沒有新 run、消費 ack、正式 output 或 checkpoint pointer 變動。

## P-501．非特權 adapter 怎麼叫起來〔建議預設，未拍板〕

呼叫者是 tick、一般已授權客戶端或控制服務；接收者是認證入口的 blob adapter，可與控制 daemon 同程序。機器 argv 為：

```json
["aos","blob-import","--channel-fd","4","--data-fd","3"]
```

```json
["aos","blob-export","--channel-fd","4","--data-fd","3"]
```

兩選項必填，值為已繼承且互不相同的十進位 fd（>=3）；未知選項拒絕。stdin 是一份 P-502／P-503 JSON 至 EOF，kind 必須對應所選 import／export 子命令，stdout 是一份結果 JSON 加 LF，stderr 是有界診斷，二進位只走 data fd。cwd 不參與引用解析。客戶端以呼叫者 UID 執行；服務端以有管理者授予內容庫存取權的非 root 控制服務 UID 執行。沒有 setuid adapter，root helper 不參與讀檔。

channel fd 是呼叫者自己連到可信部署端點的 Unix `SOCK_SEQPACKET` 連線；部署啟動器給定端點，JSON 不選路徑。服務端查 SO_PEERCRED 並核對登記 principal／UID、目標 agent 權限；客戶端核對對端為登記服務 UID。跨 UID 轉交連線不得把建立連線的管理者身分借給 agent：應在降權後建連線，或走另有可信 principal 綁定的專用入口。payload 的 agent_id 只選待驗證目標，不是授權。

每個 packet 是一份 UTF-8 JSON、不加 LF；上限含完整 packet，不允許分包冒充多次請求。import／export 請求各以 `SCM_RIGHTS` 附**恰一個** data fd；回覆不附 fd。禁止額外 fd，`MSG_TRUNC`／`MSG_CTRUNC` 視作交換失敗，關閉已收 fd、不處理半份訊息。發送者與接收者各關閉自己的副本；接收 fd 預設 close-on-exec，不能漏傳給工具。stdout 遺失或 socket 中斷不證明操作未發生。

本篇不讀任何 `AOS_*` 環境變數，沒有環境預設端點或 owner。啟動器清除 loader／憑證環境，僅給登記的 HOME、TMPDIR、固定 PATH 與 LANG；不產生子工具、不轉傳服務 key。完成合法協議結果（包含 `blob_error`）exit 0；argv／fd／啟動前 stdin 不合法 exit 2；無法完成交換或輸出 exit 125。信號由父程序 wait 判斷。

驗收：Given caller 自稱別人的 agent_id、傳入多餘 fd 或把二進位塞 stdout，When 驗入口，Then 不導入、不越權；合法錯誤可 exit 0，但呼叫者仍由 kind/error 判斷失敗。

## P-502．home 候選導入與重送〔建議預設，未拍板〕

[B-505](../base/transport.md) 的 `import_blob` 編碼見 [storage-blob-transfer.schema.json](schemas/storage-blob-transfer.schema.json) 的 `ImportRequest`／`ImportResult`／`ErrorResult`。最小完整交換（資料 fd 內容是零 bytes；此為真實空內容摘要）：

```json
{"version":1,"kind":"blob_import","request_id":"import_1","agent_id":"agent_a","expected_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","length":0}
```

```json
{"version":1,"kind":"blob_imported","request_id":"import_1","agent_id":"agent_a","ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0}}
```

caller 用自身權限、不跟隨 symlink 的方式開候選普通檔為唯讀 fd；完整路徑逐層拒絕 symlink，根來自登記，不由 root 代開。接收者 fstat 驗普通檔與唯讀權限，從 offset 0 有界讀取，不相信共享 offset 或一次 fstat 的大小；只接受恰好 length bytes 並驗 EOF，預設單 blob 最多 16 MiB。fd 本身無法證明當初開路徑是否跟過 symlink，因此路徑開啟檢查屬可信非特權入口；即使 caller 繞過自己的檢查，服務端也只能讀該 caller 已有權取得的 fd，不增加權限。

取快照時另建受管暫存、限量寫入、重算 SHA-256，不能 hardlink／rename caller 可繼續寫的 inode 冒充不可變。並行改寫造成長度或摘要不符即拒絕；不承諾捕捉候選修改前某個瞬間。受管庫與 home 同 filesystem，啟 quota 才同 project 記帳；`quota_backend=none` 合法，不把 quota 說成安全硬上限。

材料耐久發布且 writer 登記引用及 import 收據後才回 BlobRef；仍不代表 C-04 accepted。重送鍵為 `(authenticated principal,agent_id,operation,request_id)`，digest 對本篇 versioned request 使用 RFC 8785，再含 import 的 expected_sha256／length（已在 request 內），不含 fd 數字／delivery_id。這是內部材料操作去重，不新增 B-502 method。相同鍵同內容回同 BlobRef；同鍵異內容 conflict。重送仍驗認證及權限；已知收據可直接回覆、不重讀 data fd。尚未持久的失敗可用原 ID 重試；不得用新 ID 猜上次沒成功。收據與未引用內容的保護期見 P-508。

完整結構化失敗例：

```json
{"version":1,"kind":"blob_error","request_id":"import_2","agent_id":"agent_a","operation":"import","error":{"code":"invalid_record","message":"普通檔案未提供宣告的完整 bytes","retryable":false},"bytes_written":0}
```

未讀完／超限是 invalid_record，摘要不符 conflict，EDQUOT 是 quota_exceeded，容量不足依 B-404 是 resource_exhausted；不確定原因用 internal_error，不猜 quota。任何失敗都不給部分 BlobRef。import 的 bytes_written 固定 0，表示沒有對外導出 bytes，不代表內部沒暫存。

驗收：Given 來源讀到一半截斷、改寫、指向特殊檔或容量不足，When 導入，Then 不回引用也不更新 pointer；Given 發布後回覆前崩潰，When 原 ID 重送，Then 由 P-505 修復後回原引用，不再造一個材料身份。

## P-503．導出、唯讀 fd 與引用壽命〔建議預設，未拍板〕

`ExportRequest`／`ExportResult` 是 B-505 的輸出 fd 形式：

```json
{"version":1,"kind":"blob_export","request_id":"export_1","agent_id":"agent_a","ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0}}
```

```json
{"version":1,"kind":"blob_exported","request_id":"export_1","agent_id":"agent_a","ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0},"bytes_written":0}
```

輸出 fd 必須可寫，caller 自己開普通暫存檔或有界消費的 pipe；服務不開 payload 路徑、不自動 truncate、seek 或 append。adapter 先驗讀權、owner、大小／摘要並 pin 材料，再寫完整 bytes；慢接收者受部署傳輸 deadline 限制。部分寫入後失敗回 blob_error 與實際 bytes_written，若連 metadata 都送不出則 exit 125；caller 不能把前綴當完整內容，須捨棄未完成目的檔。

export 是可重複讀取。同 ID 重送不代表略過資料流：每次都重新驗權限、從來源 offset 0 傳完整內容到**新的空輸出 fd**；不能把同 ID 當成外部 fd 的 exactly-once 寫入。相同 ID 改 ref 仍 conflict。重送時材料已合法回收則 gone，不能只憑舊成功收據宣稱 bytes 已寫進新的 fd。缺失／已回收回 gone，存在但 hash 壞回 integrity_error；若該材料仍有權威引用，另依 B-402 標完整性錯誤、停相關工作，不回退 pointer。

tick／其他篇需要已提交材料的唯讀 fd 時，用同一認證 channel 的 `ReadRequest`；這是內部 fd 交付，不另加公開 method／人用 CLI：

```json
{"version":1,"kind":"blob_read","request_id":"read_1","agent_id":"agent_a","ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0}}
```

```json
{"version":1,"kind":"blob_readable","request_id":"read_1","agent_id":"agent_a","ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0},"read_handle_id":"read_handle_1"}
```

read 請求不帶 fd，成功回覆恰帶一個 SCM_RIGHTS 的 O_RDONLY 普通檔 fd，從 offset 0 可讀、不可寫。其他篇可由可信啟動器把這個實際 fd 繼承進 child；JSON 的 read_handle_id 只對應 pin，不是 fd 數字或授權。接收者驗附帶 fd 的數量／唯讀性；關閉所有副本後才送：

```json
{"version":1,"kind":"blob_read_closed","request_id":"close_1","agent_id":"agent_a","read_handle_id":"read_handle_1"}
```

close 只是關閉通知，不採信 agent／工具自報已關完 fd。控制端還須取得 execution 對該交付所有受管接收者的清空證據，或可信控制服務接收者確實關閉自身全部 fd 的紀錄，才持久解除 pin 並回同一 close 記錄；證據未齊回 blob_error/conflict，保留 pin。同 ID 重送為冪等。read 原 ID 重送在 pin 活著時可重新交 fd，但不新增邏輯 pin，caller 須關完全部副本；已關閉的 handle 不復活，回 gone，另一次有意的讀取用新 request_id。認證連線斷開不能證明已收到的 fd 關了；由 execution 的受管程序清空證據確認無活接收者，才可收回 pin。首版 read 只給可追蹤這些生命週期證據的內部接收者，普通外部 caller 使用 export；日後外部 fd pin 方案見 P-512，不擅以 TTL 當程序死亡。

驗收：Given blob 被 GC 選中與新 export 競爭，When writer 決定先後，Then 活 pin 保護資料；回收 fence 先取得則新讀取被拒，不回可用 fd。Given pipe 收到前綴後斷線，When caller 重送，Then 新目的 fd 收到完整資料或明確錯誤，不拼接前綴。

## P-504．檔案布局與發布索引〔建議預設，未拍板〕

管理者配置每 agent 的 `managed_root`，與 home 同 filesystem；控制區另有受保護 `storage_index_root`。不能讓輸入 ID 選根，ID 也不直接變任意 host 路徑。受管 key 經受控索引解析，只在該 owner 分區內定位。以下均是相對根的布局，不是新增使用者目錄參數：

```text
<managed_root>/.tmp/<publication_id>.tmp
<managed_root>/blobs/<key>
<storage_index_root>/publications/<publication_id>.json
<storage_index_root>/handoffs/<handoff_id>.json
<storage_index_root>/repairs/<repair_id>.json
<storage_index_root>/exports/<read_handle_id>.json
```

索引只有控制服務可寫（根 0700、檔 0600；跨 UID 只經受控 fd／ACL）；原收件 spool 仍按 P-003 的每 channel requests／responses 配對。本篇索引是可重建／核對的材料，不暴露 SQLite 全庫、run／ready／cursor，也不能由 agent 發一份索引就認可內容。跨 filesystem 時先在目的端重做完整耐久發布，不能直接 rename。

[storage-index.schema.json](schemas/storage-index.schema.json) `Publication` 保存導入原件的認證 channel、delivery_id、request_id、預期摘要與長度；ref 由可信 importer 預先分配 key、帶 expected_sha256／length；staged 的 ref 只用來對帳，尚不可交給 caller。published／indexed 仍須驗真檔。先持久 staged 索引與穩定分配的 key，再發布 blob，最後 writer 登記材料／收據並更新投影 indexed。schema 的 stage 不是 DB 提交證明，重啟必須核對真檔及交易紀錄。

```json
{"version":1,"kind":"publication","publication_id":"pub_1","channel_id":"channel_a","delivery_id":"delivery_1","agent_id":"agent_a","request_id":"import_1","operation":"blob_import","expected_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","length":0,"ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0},"stage":"published","updated_at_ms":1790640000000}
```

`Handoff` 是原收件材料的定位索引，record_ref 指受控快照，record_type 指該篇 schema；不擁有 RPC／Proposal／ExecResult／LLM 結果的內容規格。原認證通道與來源快照需一起留存，不能只靠出站 outbox 推測收件。`ExportPin` 對應 P-503 的可信交付引用：

```json
{"version":1,"kind":"handoff","handoff_id":"handoff_1","channel_id":"channel_a","delivery_id":"delivery_2","record_type":"proposal","record_ref":{"key":"proposal_1","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":500},"stage":"spooled","updated_at_ms":1790640000000}
```

```json
{"version":1,"kind":"export_pin","read_handle_id":"read_handle_1","agent_id":"agent_a","ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0},"recipient_channel_id":"channel_a","state":"open","created_at_ms":1790640000000,"closed_at_ms":null}
```

發布沿 B-402：同 filesystem 暫存、完整寫入、fsync 檔、不覆蓋 rename、fsync 父目錄；跨目錄同步兩端。同正式名同內容是重送，異內容 conflict，不能用 mtime 選勝者。更新可信投影可原子替換舊版，但須由單一 owner 查同 identity／更後控制事實，不適用於不可變 blob 或 sender 新投件。

驗收：Given 半份暫存與同名異內容，When 接收／重啟，Then 半份不作正式輸入、撞名不覆蓋；Given 真正 DB 尚未登記而 stage 寫 indexed，Then 不以索引宣稱已提交。

## P-505．崩潰修復與不完整材料〔建議預設，未拍板〕

啟動、overflow 與持久游標補查沿 B-504／S-202，由控制 writer 分批核對原收件快照、發布索引、DB 與回覆；不掃全 home、不叫醒冷 agent。修復記錄 `Repair` 完整例：

```json
{"version":1,"kind":"repair","repair_id":"repair_1","source_id":"pub_1","agent_id":"agent_a","observed_at_ms":1790640000000,"finding":"file_without_index","action":"reconcile_original","error":null}
```

| 中斷位置 | 恢復動作 |
|---|---|
| 暫存未完成，無活 importer | 仍無成功引用；未接納暫存可領候選回收 |
| blob 已發布、DB 未登記 | 用原 spool／publication 身分重驗 bytes、hash、owner，補原登記／收據；找不到可信原件就保留孤立候選，不造 run |
| DB 已提交、回覆未發布 | 重播原收據；不再提交 Proposal 或結算結果 |
| DB 引用缺 blob 或 hash 壞 | integrity_error、停相關工作並保留原 pointer／cursor；不得改指較舊狀態 |
| 結果只存到前綴 | 保存原 execution／LLM 篇的可信不完整證據，storage_blocked；不能生成完整 BlobRef 冒充全文 |
| 控制 ENOSPC／EIO，連 attention 寫不出 | 停新准入、不確認新件；用 B-404 保留容量盡力保存最小證據，恢復後補通知；無證據的在途結果為 unknown |

截斷結果仍由 execution／llm 的 Outcome owner 記錄，storage 不造另一份 Outcome。範例 `blob-export.truncated.valid.json` 是傳輸錯誤（前綴 2 bytes），`clean-report.unknown.valid.json` 是清理效果未確認；兩者不是工具成功。收到相同 attempt 結果仍按 C-03 去重／晚到證據規則。

驗收：Given 在 fsync、rename、DB commit、回覆及通知間逐點崩潰，When 重啟，Then 已確認材料可恢復，未確認者可用原 ID 對帳；清出空間不使丟失 bytes 再出現，不自動重跑工具找回結果。

## P-506．attention open／done〔使用者方向 2026-09-29；編碼依 P-011 暫定，未拍板〕

控制 writer 投影 S-405 的所有待人處理事項，給管理者及 `aos-attend` 讀。路徑採暫定第 5、8 項，**優先於尚未同步的 P-003／S-405 舊路徑**：

```text
<attention_dir>/open/agents/<agent_id>/<item_id>.json
<attention_dir>/open/control/<item_id>.json
<attention_dir>/done/agents/<agent_id>/<item_id>.json
<attention_dir>/done/control/<item_id>.json
```

agent_id=`_control` 合法，放 `agents/_control/`，不撞控制事項。控制事項 agent_id/run_id 均 null，不帶 job_id／attempt_id；run 事項 owner 與所有 job／attempt 都必須一致。item_id 由控制端為一次屏障分配、重建沿用；解除後新一輪屏障另配 ID，不按 code 或檔名時間推論同件。

[storage-attention.schema.json](schemas/storage-attention.schema.json) `Open`／`Done`：

```json
{"version":1,"kind":"attention_open","item_id":"attention_1","agent_id":"agent_a","run_id":"run_1","code":"storage_blocked","message":"結果保存空間不足，需清理後重新核對","since_at_ms":1790640000000,"actions":["aos-clean"]}
```

```json
{"version":1,"kind":"attention_done","item_id":"attention_1","agent_id":"agent_a","run_id":"run_1","code":"storage_blocked","message":"結果保存空間不足，需清理後重新核對","since_at_ms":1790640000000,"actions":[],"resolved_at_ms":1790640060000,"resolution":{"action":"run.resume","actor":"admin_local","request_id":"resolve_1"}}
```

actions 只列控制端當下實際支援且適用的 `run.resume|run.cancel|run.resolve|aos-clean`；可空，控制事項無 run 時不可列 run 方法。evidence 可省，本版選 BlobRef 陣列；查詢提示用既有 run_id／attempt_id 給 attend 組成已定 RPC，不塞 shell 字串。resolution.action 是實際已完成的處置或控制端重新驗證動作名稱，不是任意可呼叫 method；actor 是可信認證結果的顯示識別，request_id 對應處置稽核，內部恢復由控制端先配持久操作 ID。done 的 actions 必須為空，resolved_at_ms 不早於 since_at_ms。

open 更新、done 發布都先在目標目錄寫完暫存後 fsync／rename／同步目錄。解除先持久記帳及 resolution，發布帶解除欄位的 done，再刪 open 並同步；不能只把舊 open 原封搬過去。中斷可能暫有兩份，讀者查帳本決定，不自行解除／再做危險處置。重啟補缺 open、清過時 open、補 done；純刪檔不消屏障。權限只給控制端／管理者，不給 agent。滿碟可能當下沒有檔，恢復後依持久證據補。

驗收：Given agent 名為 _control 且另有控制滿碟事件，When 發通知，Then 兩個命名空間互不覆蓋；Given 人刪 open、或解除後只寫完 done 就崩潰，When 重建，Then 從帳本恢復正確集合，沒有重複處置。control done 僅可由管理者明確 scope=control 清理。

## P-507．aos-clean 啟動與可信通道〔使用者方向 2026-09-29；編碼為建議預設，未拍板〕

兩個機器模式均是獨立短命程式，由控制服務 UID 執行（非 root），不繼承 agent 權限、不能直接連 SQLite：

```json
["aos","clean","--mode","request","--channel-fd","3"]
```

```json
["aos","clean","--mode","system-post","--channel-fd","3"]
```

mode、channel-fd 必填；其餘 argv 不收。request 模式 stdin 是 [storage-clean-request.schema.json](schemas/storage-clean-request.schema.json) `Acquire`。管理入口先以操作者認證、核對清理政策授權，再由可信服務啟動，不靠 JSON trigger 冒認管理者；可供 control 篇的 aos-attend 呼叫，不設人用選項。原 UID 的機器 client 使用下列 clean-submit，不自行變成控制 UID。system-post 模式 stdin 是另一作者 `agent-hook-input.schema.json`，必須 when=post，hook_run_id 綁本次 claim，owner 與 run／attempt 由控制端核對；aos-clean 送出下列 `HookAcquire`；request_id 固定沿用 hook_run_id，writer 從已授權啟動紀錄取 policy／批次上限，內部展開 Acquire（scope 只能該 agent，trigger=system_post），回同一 Batch 或 AcquireError。不能把 HookInput 當 Acquire，也不能要求掛勾作者改 stdin。

管理端 client argv（與 service worker 分開）：

```json
["aos","clean-submit","--channel-fd","3"]
```

client 以操作者原 UID 執行，stdin 是 Acquire，stdout 是 worker 最終 Receipt／AcquireError／ReportError，stderr／env／退出碼沿本節。channel-fd 必填，為 client 自己連向可信管理 adapter 的專用 SOCK_SEQPACKET 連線，雙方查 SO_PEERCRED；管理 adapter 認證本人與 scope／policy 授權後，持久記原 principal、request_id 與啟動意圖，建立另一條**不傳給 client**的 worker 通道，以控制服務 UID exec request 模式 clean，將已驗 Acquire 放 stdin。client 不收到候選 fd；管理 adapter 只回完成收據或結構化錯誤，worker 未確認時保留原 request_id 查詢／重送。這是 P-011 暫定 7 的可信管理內部通道，不加入 B-502 公開 methods。相同管理請求不啟第二個 worker；原 worker 失聯須先清空／對帳，再按 P-509 新領批身份恢復候選，保留原外層 client 請求及其最終收據關聯。

channel 是控制 writer 與 clean 的專用 Unix SOCK_SEQPACKET 連線，幀／限長／SCM_RIGHTS 截斷檢查同 P-501；只允許可信啟動器建立、control service UID 使用。writer 另核對持久的此次啟動授權（管理者已准許 scope，或 hook_run_id 綁 agent），clean 不能擴大 scope。request 模式不容 trigger=system_post／hook_run_id；system-post 轉換的請求必有 hook_run_id。所有候選／完成回報只在這條內部通道，不增加公開 RPC。

環境與退出碼同 P-501：沒有 AOS_* 配置、stdin 一份 JSON、stdout 一份摘要、stderr <=64 KiB。request 模式 stdout 為 `clean_receipt` 或 `clean_acquire_error|clean_report_error`；system-post 為 `HookReceipt`，讓掛勾執行層保存診斷，但不是 agent-hook-result 的替代品、不進 history。合法 partial/error 交換可 exit 0，父層須讀 status/error；無完整輸出 exit 125，啟動前錯誤 exit 2。掛勾 deadline、清空與重啟全殺沿 A-506／P-011／execution；不因清理延長 claim，也不把重啟後恢復候選當作補跑舊 hook 成功。

```json
{"version":1,"kind":"clean_acquire","request_id":"clean_1","scope":{"kind":"agent","agent_id":"agent_a"},"trigger":"administrator","policy_id":"retention_1","max_items":32,"max_bytes":16777216,"max_elapsed_ms":30000}
```

```json
{"version":1,"kind":"clean_hook_result","hook_run_id":"hook_1","request_id":"hook_1","batch_id":"batch_1","status":"completed","error":null}
```

system-post 的第一則內部請求（不另要求未定的 bootstrap 呼叫）：

```json
{"version":1,"kind":"clean_hook_acquire","request_id":"hook_1","hook_run_id":"hook_1","agent_id":"agent_a"}
```

Batch.limits 回 writer 採用的有效 max_items／max_bytes／max_elapsed_ms，system-post 也由此取得上限；writer 的可信啟動器另強制程序 deadline。request max_items／max_bytes／max_elapsed_ms 僅可縮小政策限制，writer 取更小值；一次只領一批，時間到剩餘候選保持未完成，不在同次迴圈追掃更多頁。all_agents 也是全次總額限制、writer 游標分批，不是每 agent 各得上限；不含 control。post 只處理本 agent，沒有 tick 就不啟動 clean，不新增全域定時工作。

驗收：Given 普通 agent 把 trigger 寫 administrator、post scope 改 all_agents，When 領候選，Then unauthorized 且不給 fd；Given 沒有 tick 的一萬個 agent，Then 不因本篇起清理或喚醒程序。

## P-508．政策、可清集合及封存／tombstone〔建議預設，未拍板〕

[storage-retention.schema.json](schemas/storage-retention.schema.json) `Policy` 是管理者部署材料，透過 P-011 管理 adapter 生效，不是普通 agent 可改的請求。retention_days 可省預設 30，retention_mode 可省預設 archive；其餘必填，archive 模式 archive_id 非 null，delete 模式可 null。archive_id 解析管理者登記的目的地，不接受請求自帶 host 路徑；archive 容量也須在 B-304 全局容量政策內。

```json
{"version":1,"kind":"retention_policy","policy_id":"retention_1","effective_at_ms":1790640000000,"retention_days":30,"retention_mode":"archive","max_items":32,"max_bytes":16777216,"max_elapsed_ms":30000,"archive_id":"archive_main"}
```

writer 依 B-404／S-404 檢查：終態結果已語意消費，至少到 run 終局後保留期；無 run 的維護材料從終态算。pending、unknown、未結清外部副作用、非終態 run、目前 checkpoint／continuation／history 來源鏈、在途程序、活 importer／export pin 引用都保護。summary 的 source_refs 不能因摘要已產生就當垃圾。資料老舊不是已消費；讀過 RPC 回覆也不是 ack。attention open 永不列候選，done 從解除時間及相關 run 終局時間較晚者計；保護中的 owner/run 證據仍不清。control done 只允許管理者 scope=control。

有效政策以 policy_id／effective_at_ms 留證；縮短保留期不縮掉已承諾的去重／收據期限。writer 保存每項 eligible_at_ms 與承諾期限，不用 mtime／檔名排序；牆鐘回退不得提早回收。孤立未接納暫存確認無活導入者可提早回收；已回 BlobRef 而尚未引用的材料，其最短保護期未在正本定義，見 P-512，首版保守不列一般候選。

封存清單 Manifest 與 Tombstone 是 writer 認可後發布的有界材料，不讓 clean 自行改帳本。summary 保留記錄 ID、類型、run、已知終態及內容摘要；blob_ref 僅適用實際 blob，archive 座標是 archive_id＋entry_id，查詢 gone 時附此座標，不洩漏任意 host 路徑。

```json
{"version":1,"kind":"archive_manifest","manifest_id":"manifest_1","batch_id":"batch_1","candidate_id":"candidate_1","scope":{"kind":"agent","agent_id":"agent_a"},"archive":{"archive_id":"archive_main","entry_id":"entry_1"},"archived_at_ms":1790640000000,"summary":{"record_type":"blob","record_id":"blob_empty","run_id":"run_old","outcome_status":"succeeded","finished_at_ms":1780000000000,"content_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","content_bytes":0},"blob_ref":{"key":"blob_empty","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","bytes":0}}
```

```json
{"version":1,"kind":"tombstone","tombstone_id":"tombstone_1","scope":{"kind":"agent","agent_id":"agent_a"},"summary":{"record_type":"blob","record_id":"blob_empty","run_id":"run_old","outcome_status":"succeeded","finished_at_ms":1780000000000,"content_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","content_bytes":0},"removed_at_ms":1790640000000,"dedup_until_at_ms":1790640000000,"dedup_key_ref":null,"archive":{"archive_id":"archive_main","entry_id":"entry_1"},"error":{"code":"gone","message":"內容已封存","retryable":false}}
```

dedup_key_ref 指 writer 內既有認證鍵／digest／原收據記錄，不把 principal 或整個帳本輸出；查詢回原摘要或 gone，不能建立新工作。dedup_until_at_ms 是承諾下限，不是准許刪掉所有身份證據的命令。本輪不新增 tombstone 清除流程；更久保留策略見 P-512。

驗收：Given 某結果已 60 天但尚未消費、仍為 unknown 或被摘要來源引用，When 清理，Then 不列候選；Given 政策縮短且舊 request 重送，Then 保留期內仍回原收據／摘要，不建第二 run。

## P-509．有限候選與引用競態〔建議預設，未拍板〕

Acquire 同 `(可信呼叫者,scope,request_id)` 同內容只在原授權、仍存活的同一 clean 執行實例回原 batch，不領新批；異內容 conflict。重送附帶的重複 fd 由同一程序關閉並按 candidate_id 去重，不能啟兩次檔案動作。另一 worker 不可借原 ID 領 fd，回 conflict；原 worker 已死／batch 已被接手時同 ID 回 clean_acquire_error/conflict，details 附原 batch_id 與要求恢復的原因，不回可執行的舊 fence。這是內部領批的執行授權限制，外層 clean-submit 仍沿原請求回原最終收據。回覆用 [storage-clean-candidates.schema.json](schemas/storage-clean-candidates.schema.json) `Batch`。writer 在短交易中查保護引用、政策和授權，配 candidate_id 與 fence，標記回收中、保存穩定來源／目的 identity；此後新 Proposal 引用／import 重送取回／export／read 必須經 writer 檢查，不能在刪檔窗口重新掛上引用。不能一邊把候選發出去一邊准許新引用。已有 pin 不列候選。

```json
{"version":1,"kind":"clean_candidates","request_id":"clean_1","batch_id":"batch_1","scope":{"kind":"agent","agent_id":"agent_a"},"policy_id":"retention_1","issued_at_ms":1790640000000,"candidates":[{"candidate_id":"candidate_1","record_type":"blob","record_id":"blob_empty","agent_id":"agent_a","run_id":"run_old","action":"archive","source_slot":0,"archive_slot":1,"eligible_at_ms":1782592000000,"expected_bytes":0,"expected_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","fence":1,"source_name":"blob_empty","archive":{"archive_id":"archive_main","entry_id":"entry_1","manifest_id":"manifest_1"},"summary":{"record_type":"blob","record_id":"blob_empty","run_id":"run_old","outcome_status":"succeeded","finished_at_ms":1780000000000,"content_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","content_bytes":0},"source_device":"2050","source_inode":"1234"}],"more":false,"limits":{"max_items":32,"max_bytes":16777216,"max_elapsed_ms":30000}}
```

source_slot／archive_slot 是此回覆 SCM_RIGHTS 陣列的零起算索引，不是 host fd。兩者各指控制服務開好的受管**目錄 fd**；來源是 source_slot 下的 source_name，目的為 archive_slot 下的 archive.entry_id，manifest 為同目錄的 `<manifest_id>.json`。source_name 是 writer 從受保護索引取得的單一 basename（無斜線、不允許 .／..），不是 caller 路徑；writer 在候選意圖另保存來源 identity，並在候選帶 source_device／source_inode（stat 的裝置／inode 非負值，以無多餘前導零的十進位字串表示，避免超過 JSON 安全整數）；clean 以不跟隨 symlink 的目錄相對操作核對這兩值、普通檔型及 bytes/hash。受管目錄只有可信控制服務可寫，fence 阻止其他操作改同一來源，不能只用 record_id 猜檔名。archive 槽只給此批受控封存子目錄，不給封存根的任意寫權。

候選 summary 由 writer 提供，引用 `storage-retention.schema.json#/$defs/Summary`；clean 用它與固定 archive 座標產生 Manifest，完成時間由實際耐久發布時填入。manifest_id、entry_id 與 candidate_id 的關係已在 writer 意圖中固定，回報不能換目的。writer 核對 manifest 本體及目的資料後才登記。

空批次 candidates=[] 不帶 fd；delete 的 archive_slot=null。非空批次須同時符合部署 fd 傳送上限與 packet bytes 上限，不足就減少候選、more=true；fd 數量須等於 slot 覆蓋範圍、不可有洞或額外 fd，各 slot 指定角色核對；action=archive 須 archive_slot 非 null，預期 bytes/hash 必須符合 writer 鎖定的單檔內容。本版候選一次對一份普通檔，不做遞迴目錄刪除；多檔紀錄由 writer 分解並保存關聯，不以第一檔刪除即完成整項結果。

回收中狀態不以租約時間自動解除；逾時／斷線／重啟後先確認舊 clean 已清空並對帳實際檔案，再由新 Acquire request_id／新 batch_id 領未完成佇列中的同 candidate_id／新 fence；新批沿用原 action、來源／目的 identity 及已發布 manifest_id，不重作已完成步驟；已耐久的 manifest 保留原 batch_id，writer 用原批與接手批的持久關聯核驗，不覆寫同 manifest_id。舊 fence 報告不接受；相同已完成 fence 同內容回原收據。writer 不在 SQLite 交易內等待搬檔。候選被新保護事實阻擋時跳過且解除 fence；不能讓 clean 自己憑 cached 引用數決定安全。

驗收：Given 領候選後另一 tick 提交同 blob 引用，When 交易排序，Then 引用先成立就不領候選、fence 先成立就拒新引用；Given clean 崩潰，Then 不靠 timeout 放任第二程序與舊程序同時刪檔。

## P-510．清理回報、封存及重跑〔建議預設，未拍板〕

clean → writer 使用 [storage-clean-result.schema.json](schemas/storage-clean-result.schema.json) `Report`，writer → clean 回 `Receipt`／`Error`。報告 request_id 與 Acquire 分開（例 clean_report_1），同鍵同內容回原收據；同鍵異內容 conflict。不同進度用新的報告 ID，candidate_id／fence 保持不變。每份 items ≤原批次上限，candidate_id 不重複且屬本批、數量／bytes／elapsed 不能藉拆報告放大；只記所報候選，未報留 pending。

```json
{"version":1,"kind":"clean_report","request_id":"clean_report_1","batch_id":"batch_1","items":[{"candidate_id":"candidate_1","fence":1,"status":"archived","manifest_ref":"manifest_1","error":null}]}
```

```json
{"version":1,"kind":"clean_receipt","request_id":"clean_report_1","batch_id":"batch_1","recorded_candidate_ids":["candidate_1"],"pending_candidate_ids":[],"recorded_at_ms":1790640000000}
```

archived／deleted／already_done 為本次材料效果，不能代表 run 成功；failed／unknown 必填 Error，skipped 附原因 Error、維持候選可查。archived 必須有 manifest_ref，deleted 必須 null；already_done 由原動作決定是否有 manifest。writer 必須核對持久完成證據，不相信 stdout／單純 ENOENT；同候選已記效果才能回 already_done。Receipt.recorded_candidate_ids 包含已記錄回報（也可能 failed），pending 列尚待完成者，因此兩陣列可重疊。

刪除：先保存候選／fence 及刪除意圖，再核對來源 identity 與 bytes/hash，unlink 固定檔、fsync 父目錄，再回報。ENOENT 只有同候選可驗證原始刪除意圖且排除被其他人改掉時可恢復為完成；缺證據記 unknown，不能猜成功。

封存：先保存目的 archive_id／entry_id 與動作意圖；目的同卷可不覆蓋 rename 並同步兩目錄，跨卷必須先 copy 到目的暫存、核 bytes/hash、fsync、不覆蓋發布、fsync 目的目錄並耐久保存 manifest，才 unlink 來源並同步。崩在 copy 中只留未完成暫存；目的已耐久而來源還在，只補刪來源；來源不在且目的摘要正確、原意圖吻合，只補回報。目的異內容 conflict，不覆蓋。writer 在核驗後同交易標 gone、保存摘要/tombstone 及原收據；查詢在回收中不能回可用內容。對同一候選重跑只補缺步驟，不再算一份清理成果。

unknown 例（只是清理回報，並非 Outcome）：

```json
{"version":1,"kind":"clean_report","request_id":"clean_report_2","batch_id":"batch_1","items":[{"candidate_id":"candidate_1","fence":1,"status":"unknown","manifest_ref":null,"error":{"code":"result_unknown","message":"中斷後尚未核對封存目的與來源","retryable":false}}]}
```

候選恢復只修檔案交接，不重新執行工具、不重啟舊 hook、不清除 agent 的 storage_blocked。清完還須控制層 probe／重新驗證及管理者授權的既有處置；aos-attend 的危險動作確認歸 control 篇，本篇不提供略過確認參數。

驗收：Given 在目的 fsync、來源 unlink、DB 完成交易、回覆間各自中斷，When 下一次合法 clean 領回原候選，Then 只補缺步驟、保留可查摘要；未知結果不被說成清理完成，舊 fence 不覆寫新回報。

## P-511．範例、驗證與 proto5 差異〔主編補〕

完整例在 [examples/storage/](examples/storage/)，正文 JSON 均有對應範例，訊息 kind 對應各 schema 的明名 `$defs`，額外有同 ID 重送、quota 失敗、導出截斷、清理 unknown／失敗。invalid 檔故意保留作拒件驗收：`blob-import.bad-length` 是負長度；`attention.extra-owner` 多了一個可冒名欄位；`clean-candidates.bad-fence` 為 0；`clean-report.unknown-without-error` 缺 unknown 必要 Error。其餘負例分別拒絕 archive 缺目的、post 缺 hook／範圍過大、closed pin 缺時間、failed hook 無錯誤、import 謊報已導出 bytes、control 通知帶 run 操作。每份 JSON 先用 `python3 -c 'import json,sys;json.load(open(sys.argv[1]))' 檔名` 解析，schema 用 Draft202012Validator.check_schema，範例再以離線跨檔 resolver 驗。JSON Schema 不能替代原始重複 key／bool／整數 token 檢查、授權、SHA 核對、時序與崩潰測試。

沿用 [proto5 cpu layout](../../../proto5/spec/cpu/layout.md)／[messages](../../../proto5/spec/cpu/messages.md) 的主人管理、requests／responses 配對、先寫完再公布、門鈴只提示；沿用 [aos-exec exit](../../../proto5/spec/aos-exec/exit.md) 的 125／2 自身失敗區分。差異：link→unlink 公布改為 B-402 rename＋fsync；原 ack 讀走即刪改為 C-05 語意消費＋B-404 保留；[inst-posix](../../../proto5/spec/inst-posix/fields.md) 的未知欄位忽略、指示詞／路徑 redirect、疊加環境不搬入，避免特權代讀與隱式配置；控制區不再對任何讀者開放，按 owner 交受控 fd。常駐 cpu、可省 id notification、孤兒接續也不搬入。本篇沒有新 LLM/provider 協議。

本輪靜態驗證：7 份 schema 逐檔通過指定的 JSON 解析與 Draft 2020-12 檢查；33 個正例通過、11 個反例被拒絕，使用已存在的共用 schema 離線解相對引用；24 個正文 JSON 物件均有同內容範例。尚未有本協議實作，以下 runtime／崩潰驗收是後續實作的測試要求，不能由 schema 通過代稱完成。

驗收：Given 所有正例／負例，When 分別做 JSON/schema、owner／狀態語意、fsync／DB crash 三層驗證，Then 正例只證明第一層；跨 owner、活引用、已關閉 handle 或不完整持久證據仍須拒絕。

## P-512．待決與整合交界〔建議預設，未拍板〕

| 未定處 | 建議與本版邊界 |
|---|---|
| 已回 BlobRef、尚未綁 run 的 import 收據／孤立 blob 最短保護期 | 正本只明說未接納孤立 blob 可較早清；建議新增有限 import 保護期與可續接導入身份。未裁定前保守保留，不能假設成功 import 可立刻 GC。 |
| 外部非受管 caller 的唯讀 fd pin 遺失 | 建議外部 caller 只用 export，read 限有程序生命週期證據的內部接收者；不靠斷線或 TTL 假裝 fd 關閉。 |
| tombstone 更久保留／最終回收 | C-06 只有承諾下限；建議之後以新獨立政策處理，本輪不新增按時間釋放 ID 的入口。 |
| 容量、傳輸 timeout、archive backend | 值由部署決定；沿既有可配置預設，傳輸超時不發完整成功，封存區也要容量上限。 |

整合者需同步：control-rpc 的 aos-attend 段須改呼叫 P-507 clean-submit（本人 UID→管理 adapter 認證→服務建立私有通道並以控制服務 UID 跑 clean），區分操作者與 worker；不能把管理者建立的 socket 直接借給 agent。P-003／S-405 的 attention 路徑及 done 欄位；S-405 evidence 本版採 BlobRef 陣列、actions 的 aos-clean 是角色名而非新增 RPC；P-009 可列本篇 ReadRequest／ReadResult／ReadClose 的公共 `$defs`；B-404 補引用 fence、export pin 與跨卷封存順序（是安全落實，不改已定留存方向）。P-500 的檔案交付不替其他四份新增 SQLite layout。

交界假設：control 提供共用型別、管理者認證／啟動授權、唯一 writer、注意事項處置稽核；execution 提供程序清空／重啟證據，不能只報 PID；agent-state 提供 HookInput 與 checkpoint.commit、檢查所有遞迴 blob 引用；llm／execution 各自保存原結果與截斷證據，透過本篇材料交付，不由 storage 改 Outcome。其他篇用相對 `$ref` 指本篇 schema 的明名 `$defs`，fd 必須真的繼承或 SCM_RIGHTS 傳遞。

驗收：Given 另一篇把 import 當 accepted、把 clean stdout 當 hook 權威結果或把原始 fd 數字放 JSON，When 整合審查，Then 退回該交界，不以新增公開 method 或放寬權限補洞。
