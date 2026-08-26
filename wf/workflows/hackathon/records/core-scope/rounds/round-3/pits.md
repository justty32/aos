# 第 3 輪紀錄 — 坑的總表

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/pits.md)

這一輪撞到的坑，含上一輪哪些窄缺口被補上、哪些仍未解，每條都附現場原文與錯誤訊息。

## 2. 坑的總表

**四位獨立地都撞到上一輪 `/tmp` 現場已被清除，而且原指定場地仍不可寫。** Carmack persona 實測 `r2_present=no`；Armstrong persona 找不到 `/tmp/aos-p2-round2.kTrhIV`；Cantrill persona 找不到 `/tmp/p3-core-scope-round2`；Thompson persona 記下：

~~~text
round1=present round2=missing
~~~

四位因此都在新的 `/tmp` 重建。Carmack persona 用 R1 baseline 做 continuity gate：

~~~text
baseline_commits=8
baseline_provider_ledger=1
c1dd00e199be4cb62a8db6833ed1fe3b5e6d6352566590184aa2d33d31f6a6ac  .../round3/worlds/baseline/agent/final.json
c1dd00e199be4cb62a8db6833ed1fe3b5e6d6352566590184aa2d33d31f6a6ac  .../core-scope-r1/worlds/baseline/agent/final.json
continuity_cmp_exit=0
~~~

Cantrill persona 復原的兩支 v2 腳本 SHA-256 與上一輪 manifest 相同；Armstrong、Thompson persona 則明寫本輪是重建現場，沒有把 `/tmp` 當成永久保存。上一輪已發生「原場地不可寫、成果改放 `/tmp`」，這輪沒有解掉；四份 R2 暫存證據反而都已遺失。

**三位獨立地實測 consumer acknowledgment，撞到同一條分界：target 被 consumer 取走後，producer 自己的 receipt 不能回答以前是否完成。** Armstrong persona 把 ack 放到 consumer／aggregate 一側；四個合作 consumer 案在第一個 recover 後都有 ack，後兩次只讀既有 ack，兩次 `aos exec` 後 ledger 仍各一筆：

~~~text
MATRIX_RESULTS
fault_point=after-target victim_pid=13 victim_exit=137
case=after-target first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
fault_point=after-claim victim_pid=30 victim_exit=137
case=after-claim first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
fault_point=after-delete victim_pid=47 victim_exit=137
case=after-delete first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
fault_point=after-ack victim_pid=64 victim_exit=137
case=after-ack first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
~~~

Thompson persona 做出兩段不同歷史、但 producer 可見 manifest 完全相同的現場；同一條 Deliver 重試都只能回 Unknown：

~~~text
diff_exit=0
beeffff3aa93323b4c0df0666353a22f54de40afa7099a70405d11598aefa899  /tmp/p4-round3-fixed/never.manifest
beeffff3aa93323b4c0df0666353a22f54de40afa7099a70405d11598aefa899  /tmp/p4-round3-fixed/consumed.manifest
never_published_exit=5 output=Unknown key=K evidence=temp-without-target-or-ack
consumed_no_ack_exit=5 output=Unknown key=K evidence=temp-without-target-or-ack
~~~

加入由 claimed payload 算出的 consumer ack 後，同一分類器才改回：

~~~text
Already key=K evidence=consumer-ack
retry_with_ack_exit=0
~~~

Cantrill persona 沒另開 ack 原型，但重跑後仍記到 Publish receipt 在 aggregate 刪除 target 後失去發布歷史，並指出現有 `aggregate_instructions()` 沒有 ack commit。Carmack persona 本輪沒有測 consumer acknowledgment。上一輪的 consumed-before-receipt 坑，**對遵守 ack 協定的 consumer 已解**：completion 由 consumer 留下，重開可機械取得既有 ack，不再 `adopt-consumed`；**對不合作 consumer 仍未解**。Armstrong persona 的反例原文是：

~~~text
{"ack":false,"aggregate":false,"aggregate_receipt":false,"claim":false,"command":"status","key":"key-rogue-evidence","ledger_lines":0,"payload":true,"publish_receipt":true,"ready":false}
{"command":"recover","error":"unknown-consumer-history: producer published, but ready, claim, and ack are absent","state":"stopped"}
rogue_recover_exit=1
~~~

**Carmack persona 上一輪未測的兩個 Effect terminal 窗口已解。** response 已 commit 時，resolve 只補 done；第一次由 4 commits 變 5，第二次 commit delta 0、ledger delta 0，最後 hash 與 baseline 相同：

~~~text
RESOLVE_COMMAND=effect.sh resolve EFFECT adopt-ready-response
{"request_id":"request-7","state":"done","outcome":"success"}
{"request_id":"request-7","state":"done","outcome":"success"}

resolve_first exit=0 commits=5 provider_ledger=1
resolve_second exit=0 commits=5 commit_delta=0 provider_ledger=1 ledger_delta=0
final_cmp_baseline_exit=0
~~~

decision 已 commit 時，兩次 `abandon` 同樣不增加 commit 或 provider ledger，final 保留 `unknown_abandoned`：

~~~text
RESOLVE_COMMAND=effect.sh resolve EFFECT abandon
{"request_id":"request-7","state":"done","outcome":"unknown_abandoned"}
{"request_id":"request-7","state":"done","outcome":"unknown_abandoned"}

resolve_first exit=0 commits=5 provider_ledger=1
resolve_second exit=0 commits=5 commit_delta=0 provider_ledger=1 ledger_delta=0
~~~

這只補上「response／decision 已有耐久證據，done 尚未 commit」的投影；provider acceptance 到 committed response 之間的 unknown 沒有被這兩案消除。

**Cantrill persona 實測私有 validator 與 canonical object parser 已分叉，且現有 C ABI 沒有 batch parser。** 16 案統計為 3 個共同接受、4 個共同拒絕、4 個私有接受但 canonical 拒絕、2 個私有拒絕但 canonical 接受，另有 3 個 batch C ABI 缺口：

~~~text
      3 AGREE_ACCEPT
      4 AGREE_REJECT
      3 CAPI_BATCH_GAP
      4 PRIVATE_ACCEPTS_CANONICAL_REJECTS
      2 PRIVATE_REJECTS_CANONICAL_ACCEPTS
~~~

實際差異包含 unknown key 與錯型別欄位被私有 validator 放行，`argv` 的 `$env` directive 與 duplicate `argv` key 則被私有 validator 擋下、canonical 接受。array 三案得到 `3:NotAnObject`，只對應 C ABI 只收 single object，沒有完成 object／array 全契約。上一輪「私有 validator 可能長出第二套 schema」的坑，這輪已量出逐案差異；沒有公開 batch C ABI 的缺口未解。

**本輪三個 harness／量測錯誤都保留了原文，修正後才重跑。** Carmack persona 第一個 response-window 案在 marker 已出現、PGID 檔尚未建立時就動手殺，卡在：

~~~text
cat: .../child.pgid: No such file or directory
/bin/kill: failed to parse argument: '-'
~~~

該案作廢；改成先寫 PID／PGID、最後發布 marker，再用新 world 重跑。Armstrong persona 第一次 audit 把 instruction exit 找在 `.aos/`，四案都數成 0；檢查目錄樹後改查 world 根，重跑為每案恰好一個內容 `0` 的 exit 檔。Thompson persona 第一版用 `mv target claimed`，publish 的 hard link 使 temp `st_nlink=2`，兩段歷史其實可分；該案作廢，改成 copy＋unlink 後兩邊都得到：

~~~text
never_temp_meta=mode=81a4 size=11 links=1
consumed_temp_meta=mode=81a4 size=11 links=1
~~~

**四份原型仍都沒有真實 power-cut 或跨平台證據。** Armstrong persona 的共用 `immutable_publish()` 做了 file fsync 與 directory fsync；Carmack、Cantrill、Thompson persona 都只把結果限定在 visibility。`renameat2(RENAME_NOREPLACE)` 仍是 Linux-only；NFS、磁碟滿、部分 fsync 失敗、非 Linux、receipt／ack 清理與 retention 都未測。四位都沒有改 C++、沒有 build、沒有 ctest。
