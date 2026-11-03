# 第 2 輪紀錄 — 坑的總表

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/pits.md)｜[R3 →](../round-3/pits.md)

私有原型（`/tmp` 裡的 Python／shell）解掉哪些、哪些還在；現行 aos 本身沒改。

## 2. 坑的總表

**無 query／idempotency 的 provider 在 effect 與本機 result 之間被砍，本機仍只能留下 unknown（四位）。** 能做到的是把它變成可明示 `abandon`／`retry`／`adopt` 的狀態與命令；accepted 後明示 retry 讓 provider ledger 1→2，abandon 則兩案都寫 `unknown_abandoned`。no-aos 鏈同命令重開在 SIGINT、SIGKILL 兩案都把 effect 做兩次。

**target 的可見提交，不等於 aggregate 消費後仍有發布歷史（四位）。** queue 還沒被吃掉時，no-replace＋stable key 能回 Already／Conflict；aggregate 刪檔後同 key 會再被 enqueue（回 `"state":"published"`）。target 已發布、receipt 尚未提交、consumer 又已取件的窗口，重開時 target、temp、receipt 都可能不在，只能留下操作員證言 `"durability":"operator-attested-after-ambiguous-consumption"`。→ 第 3 輪由 consumer ack 解（合作 consumer）。

**兩個 producer 是 writer contention，不是第二個 logical work（三位）。**

- transaction directory 先看再 `mkdir` 有 TOCTOU：`FileExistsError: [Errno 17] File exists`。
- 共用本地序號時，2×1,000 件中 32 件明確失敗、968 件 helper 回成功卻覆蓋既有 ready，共遺失 1,000 件；改用全域唯一 ID 後 2,000 件全數執行，遺失、重複、覆蓋都是 0。
- 不同 target 各 1,000 件：全數處理。

**test 再 `mv` 有覆蓋競爭，要用 no-replace 原語。** Publish v1 強迫競爭時兩方都 exit 0、B 無聲覆蓋 A；`renameat2(RENAME_NOREPLACE)` 版同內容 published／already、異內容 published／conflict（exit 73）。`mv -n` 跳過時仍可能成功退出，不能當 no-replace；hard link 可做窄版但會留下 crash temp。`renameat2` 是 Linux-only，尚無可攜契約。

**rename 前要人搬 `.temp` 的坑，可由可重入 Publish 解掉。** 私有恢復路徑的人工 rename、shell `mv`、手造半批 instruction 都是 0；舊 helper 第一次已把來源搬走，用原參數重跑失敗（`mv: cannot stat '.../source'`）。

**`.runi` 擋住重開，只能用具名恢復命令處理，不是 instruction program counter。** 例：先驗 Effect done 與 continuation receipt，再保存 forensic `.runi` 並解鎖，不人工重造 schedule。

**錯名 silent stall 在私有 Deliver 解掉，現有 aos 行為未改。** `name.part.json`、`.json`、`name.json.temp`、無副檔名都 `aos_exit=0`、stderr 空白、檔留在 inbox；壞 JSON 才會被取走並印 `JsonSyntax`。由 Deliver 自己產生合法檔名、壞 key／JSON／schema／world 一律 exit 65 回 rejected，才可見。

**量測時要注意**：把收據文字混進應為純 JSON 的 stdout，三次 `aos exec` 都回 0 但 final JSON 壞掉；dash 的內建 `kill` 不吃負的 process group 編號（`kill: Illegal number: -`），改用 `/bin/kill`；背景 SIGINT 無效，用前景 `timeout --preserve-status --signal=INT` 才拿到 130；`rg -h` 不是 no-filename，要用 `--no-filename`。

**沒有真實 power-cut 證據。** 多數原型只承諾 visibility atomicity；有跑 file／directory fsync 的那份也沒測真實斷電、NFS、虛擬磁碟或裝置快取。

**辦場的坑**：原場地被沙盒拒寫（`patch rejected: writing outside of the project; rejected by user approval settings`），成果改放 `/tmp`，第 3 輪時已全數消失（見 [hackathon gotchas](../../../../gotchas.md)）。
