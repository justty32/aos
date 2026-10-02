# schema、範例與 Python 文件 審查（astra，2026-10-02）

## 一段話結論

有必修。schema 會拒絕程式已支援的寫法，驗證器會誤判正常紀錄，也漏掉一種錯誤紀錄。文件另有過時流程、功能清單和跑不起來的範例。暫緩區的引用大多標示清楚，但現行 hooks 範例仍使用已暫緩指令。以下只列有程式證據的問題。

## 必修

1. **schema 不接受已支援的 `id`／`kind` 指示詞。**  
   [tick-tasks.schema.json:483](/home/guanyu/projs/aos/proto6/spec/protocol/schemas/tick-tasks.schema.json:483) 兩欄只收字串。但[程式:183](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick_table.py:183)會展開它們，[測試:70](/home/guanyu/projs/aos/proto6/src/py/tests/test_tick_kind.py:70)也直接使用 `kind:{"$env":"AOSTEST_KIND"}`。  
   **改法：**兩欄加入 `ValueDirective` 分支，補對應正例。

2. **紀錄驗證器的位置檢查會誤擋，也會漏擋。**  
   [validate.py:53](/home/guanyu/projs/aos/proto6/spec/protocol/examples/messages/validate.py:53) 不分是否完成，都用 `ran＋skipped筆數` 限制任務與 hook 位置。但 [before_kind 先於任務執行](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick.py:177)，所以正常可出現 `ran:0、task_index:0`；[skipped 又只在收尾落盤](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick_record.py:140)，格中也可能被誤判。反過來，完成紀錄的 `skipped.index` 沒查上界，`ran:0、skipped:[{id:"a",index:99}]` 仍可通過。  
   **改法：**完成後才查位置上界，並同時檢查 `tasks`、`skipped` 與相關 hooks；補格中正例及真正超界的 skipped 反例。

3. **現行 hooks 範例呼叫已暫緩指令。**  
   [tasks.hooks.valid.json:15](/home/guanyu/projs/aos/proto6/spec/protocol/examples/tick/tasks.hooks.valid.json:15) 使用 `aos-tick-check-task`；[現行協議:95](/home/guanyu/projs/aos/proto6/spec/protocol/tick.md:95)明確標為暫緩。  
   **改法：**換成普通腳本，讓範例只示範 hooks。

4. **指示詞展開時機仍寫成舊版。**  
   [docs/tick.md:59](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:59)、[spec/daemon/core.md:14](/home/guanyu/projs/aos/proto6/spec/daemon/core.md:14)及 [tick-tasks.schema.json:5](/home/guanyu/projs/aos/proto6/spec/protocol/schemas/tick-tasks.schema.json:5) 還有「只展一層、跑到任務才展開」的說法。schema 還說 `#/…` 指合併後的單項。實際是開格展開，引用整份表；[測試:200](/home/guanyu/projs/aos/proto6/src/py/tests/test_tick_table.py:200)明確驗證前項改檔，後項仍用開格時的值。  
   **改法：**刪掉舊說法，統一指向現行讀表程式與測試。

5. **紀錄 schema 的說明與實際輸出矛盾。**  
   [tick-record.schema.json:265](/home/guanyu/projs/aos/proto6/spec/protocol/schemas/tick-record.schema.json:265) 說只有 `after_all` 且 `ended:true` 才有 hooks；[第 76 行](/home/guanyu/projs/aos/proto6/spec/protocol/schemas/tick-record.schema.json:76)說空陣列收尾才建。實際[開格就建立各掛點紀錄](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick_record.py:105)。另外[第 48 行](/home/guanyu/projs/aos/proto6/spec/protocol/schemas/tick-record.schema.json:48)把 `blocked_before` 說成位置 `ran`，漏算已跳過的項。  
   **改法：**更新建立時機；`blocked_before` 只寫「被全部擋下的第一項 id」，避免重述算式。

6. **功能清單漏掉已完成的功能。**  
   [docs/tick.md:34](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:34) 說沒有模組，[docs/daemon.md:37](/home/guanyu/projs/aos/proto6/src/py/docs/daemon.md:37)說只有 control；但已有 [tasks-blocked](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick.py:164)及其他 daemon 模組。[docs/ctl.md:29](/home/guanyu/projs/aos/proto6/src/py/docs/ctl.md:29)、[README:81](/home/guanyu/projs/aos/proto6/src/py/README.md:81)也少列 `kill`、`restart`，而[程式清單已有六個指令](/home/guanyu/projs/aos/proto6/src/py/lib/aos_ctl.py:18)。  
   **改法：**移除「目前只有／沒有」，補齊指令；細節連到既有分篇。schema 第 5 行的「只開 after_all」一併更新。

7. **tasks-blocked 的刪除時機寫反。**  
   [docs/tick.md:61](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:61) 寫「換紀錄→刪停格檔→照表跑」，實際[收尾後才刪](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick.py:186)。照文件理解，會誤以為開格前放的擋板無效。  
   **改法：**把刪除步驟移到整格最後。

8. **tick 最小範例換目錄後找不到執行檔。**  
   [docs/tick.md:15](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:15) 執行 `cd /tmp/n` 後，仍用 repo 相對路徑呼叫程式；下一行也受影響。  
   **改法：**先記下執行檔絕對路徑，用 `(cd /tmp/n && "$tick_bin")` 示範省略目標。

9. **輸出文件仍說全部收齊。**  
   [docs/daemon.md:60](/home/guanyu/projs/aos/proto6/src/py/docs/daemon.md:60)、[docs/cgroup.md:20](/home/guanyu/projs/aos/proto6/src/py/docs/cgroup.md:20) 說輸出收齊；實際 [drain():54](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_output.py:54) 超過上限就丟掉最早的 bytes。  
   **改法：**改成「讀到結束，只保留上限內的尾段」，連到輸出上限說明。

## 建議

- **把歷史範例分清楚。** [validate.py:92](/home/guanyu/projs/aos/proto6/spec/protocol/examples/messages/validate.py:92) 跳過九份舊 mq 範例，但檔名仍標一般正反例。建議加入口說明或移到封存。`tasks.template*`、`tasks.as`、`tasks.methods*` 已在[協議:67](/home/guanyu/projs/aos/proto6/spec/protocol/tick.md:67)標明歷史用途，因此不列必修。
- **清掉未使用的舊協議定義。** [common.schema.json:114](/home/guanyu/projs/aos/proto6/spec/protocol/schemas/common.schema.json:114) 還留 JSON-RPC／FileRpc，現行 schema 沒用到。可移到封存。
- **修正舊正本指向。** [inst.schema.json:5](/home/guanyu/projs/aos/proto6/spec/protocol/schemas/inst.schema.json:5) 還說以 `base/inst.md` 為正本。建議改成現行入口，或直接刪掉這句。

## 疑問

沒有需要另定方向的題目。以上都能沿用現行程式與測試修正，不必增加 POC 的邊緣處理。

## 看過的範圍

全部 8 份 schema、tick／daemon JSON 範例、完整 `messages/validate.py`、Python README 與全部 10 份 docs。對讀相關 JSON 讀寫程式與測試，並檢查現行 spec 對 deferred 的引用與標示。

全程只讀。未改檔、未 commit、未執行測試或驗證器。