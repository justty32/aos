# astra 唯讀審查任務書：停車＋喚醒實作（2026-09-24）

你是唯讀審查者。**不要改任何檔**，只輸出報告（繁體中文、白話）。

## 背景

使用者裁決照提案 `proto5-2/notes/2026-09-24-idle-wait/plan-b.md` 做方案 (b)：agent 在「批在途、這格什麼都沒收到、什麼都沒寫」與「idle 沒輸入」時退 **102＝停車**；
kernel 在它等的回音出貨時叫醒它，`aos-agent say` 投完話另投一張 `wake` 單叫醒它；保底 `park_ms` 預設 300000。
proto5 的 kernel 已是池式（`ready`／`delayed` 堆積、四個提交點，見 `proto5/spec/kernel/tick.md`、`ledger.md`）。

## 要審的東西

- 報告：`proto5/notes/2026-09-24-idle-wait-impl/README.md`
- 程式（`git diff main -- proto5/lib` 看得到全部改動）：
  - kernel：`proto5/lib/aos_kernel_info.py`（`classify` 的 102、`PARK_MS`、`FEATURES`、`park_ms` 讀驗）、`aos_kernel_ledger.py`（`wake`、`_wake_of`、`_reply`、`_add`、`apply_syscall` 的 `wake` method、`flush_outboxes` 出貨後叫醒、`features`）、
    `aos_kernel_engine.py`（`dispatch` 清 `parked`）、`aos_kernel_ls.py`（`parked`）、`aos_kernel_cli.py`（`wake` 子命令、`--park-ms`）
  - agent：`proto5/lib/aos_agent.py`（`_park`、`_compatible`）、`aos_agent_batch.py`（`send` 帶 `wake`）、`aos_agent_say.py`（`deliver`／`drop_new` 投完叫醒）、新檔 `aos_agent_wake.py`
- 規範（`git diff main -- proto5/spec`）：kernel 的 syscall、echo、tick、ledger、info、cli、cli-ls；aos-agent 的 tick、send、register、collect、idle、gate、cli-talk
- 測試：`proto5/lib/test/test_park_wake.py`、`test_park_crash.py`，以及被改成 102 的舊測試

## 請特別看

1. **會不會漏叫醒**：逐一找反例——agent 停車之後，除了 `park_ms` 保底，有沒有哪種交錯讓它等不到叫醒？
   照 kernel 一格的真實順序（第 4 步出貨、第 5 步收單、第 6 步收回音、第 8 步派工、第 10 步出貨、四個提交點）與 agent tick 的順序（鎖、暫停、門、收回、ack、結清、idle 收輸入、自動壓縮）。
   特別看：同一格裡回音出貨與 agent 的 102 判定的先後；`woken` 在各種判定列（stopped、error、kind=aos、done_exit）之後有沒有清乾淨；
   `wake_gen` 對同名重登記；`discard`；act 批多件；`once` 的 `Removed`／`Stopping`／收單就退件；`wake` syscall 與 `deletes` 去重；`stale` 計數。
2. **崩潰窗口**：每個「崩在哪兩步之間」是不是都有測試、測試真的測到那個窗口（不是碰巧過）？還有沒測到的窗口？
3. **會不會把不該停的停掉**：agent 在哪些情況退 102 是錯的（例如其實寫了東西、門關著、鎖被佔、自動壓縮做了事、`intake` 收到一半）？
   `aos-agent start` 的相容檢查（`done_exit` 102、帳本 `features`）有沒有誤擋或漏擋？舊 kernel／舊帳本／還沒 boot 的 K 各會怎樣？
4. **規範與程式一致嗎**：改過的規範句子跟程式行為對不對得上；有沒有該改沒改的句子（例如別處還寫「在等＝101」）。
5. 其他：`ls` 的 `parked` 欄與 `--json` 版本承諾、`aos-kernel wake` CLI、對效能的影響（每格多做了什麼）。

## 輸出格式

每條：編號、〔必修〕或〔建議〕、位置（檔:行）、現象、依據（規範或程式的檔:行）、建議改法。最後一段總評三五句。
