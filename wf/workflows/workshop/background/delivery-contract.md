# 名詞表：投遞契約與收據
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### Publish（發布／commit／bundle）

**白話**：先在旁邊把新東西寫完，最後一次換上去，讀者只會看到完整舊版或完整新版。
**嚴格**：對同一檔案系統上的 file/directory 以 temp/source＋單次 `rename` 形成可見性原子提交，可選再定義 write/fsync/directory-fsync 的耐久承諾。
**在 aos 裡具體是什麼**：可見性的 temp＋rename 做法已散存於彙整／取件；公開 `aos publish` 或 `aos core publish` 目前不存在，是被[回頭審視](../records/step-back-review.md)延後的提案。
**為什麼會冒出這個詞**：[agent loop 場](../records/agent-loop-architecture.md) 想統一 event、cursor、Deliver 與 Effect 的完整可見邊界；後來四位都收回近期公開 API。

### Deliver（投遞／enqueue／handoff）

**白話**：把一批已檢查的指令完整放進待辦區，放好就結束，不順便執行。
**嚴格**：驗證 instruction object/array，以唯一同目錄 temp 寫入，再原子 rename 為 `.aos/inst.tempd/*.json` 的 queue publication 原語；它不 aggregate、claim 或 exec。
**在 aos 裡具體是什麼**：三步協定的「投遞」是已定規格，但公開 API/CLI 尚不存在；`aos deliver ...` 是 roadmap T5 前的候選缺口，參數正是待答題。
**為什麼會冒出這個詞**：[早期 core 場](../records/pre-agent-loop-core.md)、[agent loop 場](../records/agent-loop-architecture.md)、[回頭審視](../records/step-back-review.md)、[工具協作場](../records/tool-interop.md) 都指向同一個現存漏洞：生產者目前得自己寫 temp＋rename。

### correlation ID（串接編號／request ID）

**白話**：只是把一路上的請求、結果和記錄串成同一件事的號碼，不保證事情只做一次。
**嚴格**：用於 tracing/correlation 的不透明識別子，讓 request、attempt、result、receipt 可被關聯；它不需要去重語意，也不自動是 provider 可查詢的 ID。
**在 aos 裡具體是什麼**：目前沒有公開格式；Deliver key 若不做去重，就可以僅作 correlation，放進檔名或回傳 JSON 供 driver 串接。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 想讓 job 升格後的結果還能與原工作對得起來；[工具協作場](../records/tool-interop.md) 又把它與真正冪等保證分開。

### receipt（收據／completion record）

**白話**：做完一步後留下的可查憑據，告訴後面的人「哪一件事、得到什麼、何時算完成」。
**嚴格**：不可變或原子提交的 completion evidence，至少關聯 request/delivery identity、state 與 result/hash；它是單次操作的證據，不等同保存所有歷史的 ledger。
**在 aos 裡具體是什麼**：目前沒有共同 receipt schema；Deliver 成功 JSON、Effect 結果、子工作完成事件都曾被叫 receipt，待答題正在要求把它們分清。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 需要對齊外部處理器與父工作；[agent loop 場](../records/agent-loop-architecture.md) 需要 crash 後判斷下一次 Deliver 是否已做。

### no-replace／`renameat2(RENAME_NOREPLACE)`（禁止覆蓋式發布）

**白話**：兩個人同時把包裹放進同一格，只准先到的人成功；後到的人會明確收到「這格已有人」，不能悄悄把前一份換掉。
**嚴格**：以單一步驟完成「target 不存在才 rename」，避免先檢查、後搬移之間被另一 writer 插入；Linux 可用 `renameat2(..., RENAME_NOREPLACE)`，其他平台需另定等價契約。
**在 aos 裡具體是什麼**：現行公開命令沒有這項保證；第 2 輪 `core-scope` 黑客松的四份私有原型分別用 Linux `renameat2` 或 hard link 試作，尚未進 `core/inst/`。
**為什麼會冒出這個詞**：[core scope 黑客松第 2 輪](../../hackathon/records/core-scope/README.md)實測兩個 producer 同 target 時，先 test 再 `mv` 會讓後寫者無聲覆蓋前寫者。

### consumer acknowledgment（收件者確認）

**白話**：包裹被櫃台拿走後，櫃台還要留一張「我確實收走了」的存根；不然寄件格空了，只看現場分不出是送達還是根本沒寄。
**嚴格**：consumer／aggregate 在 claim 或刪除 delivery 後提交的耐久證據，讓同一 key 重開時仍能機械判定已消費，而不靠 producer target 或操作員證言。
**在 aos 裡具體是什麼**：目前不存在，是第 2 輪 `core-scope` 黑客松提出、預留給下一輪驗證的方案；現行 `core/inst/src/handoff.cpp` 發布彙整結果後只刪 delivery，沒有 ack。
**為什麼會冒出這個詞**：[core scope 黑客松第 2 輪](../../hackathon/records/core-scope/README.md)打出 target 已被 aggregate 取走、producer receipt 又尚未落盤的窗口，證明 Deliver 自己留收據可能來不及。

### TOCTOU（先檢查、後使用的競爭窗）

**白話**：你看座位還空著，轉身去拿包包時別人已坐下；回來仍照剛才的判斷放東西，就會撞人或蓋掉他的東西。
**嚴格**：time-of-check to time-of-use race；存在性檢查與建立／rename 分成兩步時，另一個 writer 可在兩步之間改變現場。
**在 aos 裡具體是什麼**：不是 aos 的公開名詞或命令；第 2 輪私有原型在 transaction directory 的 `mkdir` 與 Publish v1 的 test＋`mv` 各撞到一次，現行正式契約尚未補上通用解法。
**為什麼會冒出這個詞**：[core scope 黑客松第 2 輪](../../hackathon/records/core-scope/README.md)第一次雙 producer 測試直接重現 `FileExistsError`，另一份測試則重現後寫者無聲覆蓋。
