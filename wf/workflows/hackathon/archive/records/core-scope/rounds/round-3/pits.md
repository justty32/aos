# 第 3 輪紀錄 — 坑的總表

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/pits.md)

## 2. 坑的總表

**target 被 consumer 取走後，producer 自己的 receipt 不能回答以前是否完成；要由 consumer 留 ack（三位）。**

- 合作 consumer：在 target、claim、delete、ack 之後各砍一刀（`victim_exit=137`），四案都由一個 recover 收斂到 ack；重跑 recover 兩次、`aos exec` 兩次後 `ledger_lines=1`。不再需要 `adopt-consumed`、人工搬檔或重造半批 instruction。
- producer-only receipt：兩段不同歷史（publish 前被殺／已消費、ack 前被殺）做出完全相同的 producer 可見 manifest（`diff_exit=0`），同一條 Deliver 重試都只能回 `Unknown key=K evidence=temp-without-target-or-ack`；加入由 claimed payload 算出的 consumer ack 後才回 `Already key=K evidence=consumer-ack`。
- 不合作 consumer（直接刪 ready、不寫 claim／ack）仍未解，recover 停住：`unknown-consumer-history: producer published, but ready, claim, and ack are absent`，`rogue_recover_exit=1`。
- 現有 `aggregate_instructions()` 發布後直接刪 deliveries，沒有 ack commit。

**Effect 的兩個 terminal 窗口：已有耐久證據時，resolve 只投影 done、不再叫 provider。** response 已 commit／done 未 commit：`effect.sh resolve EFFECT adopt-ready-response` 第一次補 done，第二次 `commit_delta=0`、`ledger_delta=0`，final hash 與 baseline 相同。decision 已 commit／done 未 commit：兩次 `abandon` 同樣零 delta，final 保留 `unknown_abandoned`。provider acceptance 到 committed response 之間的 unknown 不因此消除。

**私有 validator 與 canonical object parser 已分叉；現有 C ABI 沒有 batch parser。** 16 案：3 共同接受、4 共同拒絕、4 私有接受但 canonical 拒絕（unknown key、錯型別欄位）、2 私有拒絕但 canonical 接受（`argv` 的 `$env` directive、duplicate `argv` key），3 案 array 得到 `3:NotAnObject`（C ABI 只收 single object）。

**量測時要注意**：殺 child 前要先寫好 PID／PGID 檔再發布 marker，否則 `cat: .../child.pgid: No such file or directory` 讓 `/bin/kill` 拿到空值；instruction exit 檔在 world 根、不在 `.aos/`；證明「兩種歷史不可區分」時別用 `mv`／hard link，`st_nlink=2` 會洩漏歷史，改用 copy＋unlink 並確認 `links=1`。

**沒有真實 power-cut 或跨平台證據。** `renameat2(RENAME_NOREPLACE)` 仍是 Linux-only；NFS、磁碟滿、部分 fsync 失敗、非 Linux、receipt／ack 清理與 retention 都未測。

**辦場的坑**：上一輪放在 `/tmp` 的現場全數被清掉（`round1=present round2=missing`），原場地仍不可寫；場地不要放 `/tmp`。
