# budget 併發、真 SIGKILL 與外部讀取故障

50 案有效探針全部完成觀測；48 案符合既有保證或記錄誤用下的保守表現，另 2 案重現**同一個 B：A6-02，後端讀不到時 call 把未知回成退出碼 1**。帳沒有損壞、沒有退款或重扣，恢復讀取後同 K 完成一次結算。這不是 50 案產品契約全過；原始 `results.json` 的 `ok` 僅指探針完成斷言，產品判定另列 [verdicts.json](verdicts.json)。

程式、測試、既有文件均未修改；無 LLM、無 commit/push、未碰 scratchpad。測試根均為自己的 `/tmp/astra5-budget-crash-*`，結尾逐 PID SIGKILL/wait，保存 ps 後刪除自建根。

| 組別 | 案數 | 實際觀測 |
|---|---:|---|
| 並行：同 K 40 個 call | 1 | 全成功；used=1、seq=2、後端受理 1 次 |
| 並行：異 K 60 個 call、額度 17 | 1 | 恰 17 受理、43 拒絕；available=0、inflight=0、used=17 |
| 並行：同 K 不同內容、各 20 個 call | 1 | 勝方內容受理 1 次；另一半 20 個 conflict；seq=2 |
| 並行：40 個 K，各一個 call 與 cancel | 1 | 每 K 恰為 accepted 或 cancelled；本輪 2 受理、38 取消、seq=80，晚到重播不新增效果 |
| spec §7 既有鉤子 | 9 | 全部真正退出 -9，`.crash` 消耗；中斷及恢復快照均保存 |
| os.replace 實際提交前／後 | 20 | reserve/settle 帳、gateway intent/done、backend、reserve/settle 回條與 inbox、call out；每案外掛命中紀錄 1 次、退出 -9 |
| 取消寫終局前／後 | 4 | 分別以 intent 無效果／backend 已有效果進入；恢復取消或查回原受理、晚到 run 不加效果 |
| init 寫帳前／後 | 2 | rename 前死亡可再 init；後死亡留下完整帳、第二次 init 拒絕，之後正常支用 |
| unknown → cancel → 晚到 run | 3 | reserve 後、intent 後、effect 後；前二取消退款，effect 後取消不成、用原效果結算 |
| 時鐘未知後恢復 | 1 | 預留保留、不永久拒絕；此案手寫壞鐘是 M fixture，不列 bug |
| 壞帳／缺帳 | 2 | 人手改壞或刪檔＝M；請求保留、error.json 留因、沒有自動開空帳；還原後只扣一次 |
| grant／ledger／gateway 的 EIO | 3 | 命中有記錄；皆保留狀態、call 回 3；恢復後完成 |
| backend EIO 與真 EACCES | 2 | **同一 A6-02 B**：call 回 1、stdout 空、stderr traceback；預留仍在、無新增效果 |
| **合計** | **50** | **48 個符合契約或 M 觀察；2 個同一 B 的獨立重現** |

[verified/results.json](verified/results.json) 的 41 案耗時合计 10.490 秒；[extra/results.json](extra/results.json) 的 9 案 1.652 秒（逐案 wall time 加總，非官方 suite 耗時）。既有 9 鉤子及外掛 26 個 rename 窗口都是作業系統 SIGKILL，並非丟例外代替。外掛僅攔截本次 subprocess 的 `os.replace`；在 rename 前讀已寫完的 temp 判定目標，或 rename 後殺目前 PID，不改包的原始碼。

## A6-02 — B：backend 讀取未知被包裝成失敗退出

契約：[README call 契約](../../../../packs/budget/README.md)（0 成功、1 已結算不成功或拒絕、3 未知），[spec §6.2](../../../../packs/budget/spec.md)（入口非終局回 3）、[component-contracts §3](../../../component-contracts.md) 與原則 9/10。輸入與持久資料有效，只有外部讀取 EIO/EACCES，屬 X 觸發；call 未兌現未知結果契約，故歸 B，不是 M。

重現流程：開帳並起單一 ledger；以 `gateway-after-intent` 把 call 殺在 intent 之後；讓該 call 讀 `backend.json` 得 EIO，再以同 K call。實際退出碼 1、stdout 無 JSON，stderr 是 `aos7_fs.Unknown` traceback。另一次先用 seed 建合法 backend，再準備 r 的 intent，把自己 `/tmp` 的 backend 權限暫設 `000`，不用 injector 重現真 PermissionError；恢復原 mode 後確認 backend bytes 完全未變，再 call r 成功，沒有重扣。

- EIO 證據：[verified/results.json](verified/results.json) 的 `eio-backend.json`，`hits` 記 1 次命中，`unknown_exit_contract: false`；故障快照（verified/snapshots/eio-backend.json-interrupted/ledger.json，已打包進 [verified/snapshots.tar.gz](verified/snapshots.tar.gz)）、恢復快照（verified/snapshots/eio-backend.json-final/ledger.json，同上已打包）。
- 真 EACCES 證據：[extra/results.json](extra/results.json) 的 `eacces-backend`，`real_EACCES: true`、uid=1000，故障時 available=98/inflight=1/used=1（seed 已結算）；`settle(r)` 仍回 3；故障 ledger（extra/snapshots/eacces-backend-interrupted/ledger.json，已打包進 [extra/snapshots.tar.gz](extra/snapshots.tar.gz)）、恢復 ledger（extra/snapshots/eacces-backend-final/ledger.json，同上已打包）。
- 對照：`eio-ledger.json`、`eio-grant.json`、`eio-gateway/519457d6f54d32335539.json` 都回 3；同類讀取故障只在 backend 呼叫路徑漏接。
- 實作位置：[aos7_budget_gate.py](../../../../packs/budget/aos7_budget_gate.py) 第 40 行 `edit_json` 丟出 Unknown，第 174 行 `call → run` 沒轉成 pending。
- 建議修法一行：在 budget 入口／call 的共同外部故障邊界把 Unknown／讀取 OSError 轉成既有非終局 unknown 與退出碼 3，保留 intent／預留，沿同 K 重送。

目前實測沒有帳損；影響是上層依 1/3 分流時把待重試當已失敗。是否導致 step 不重試需依 step 的實際接法判斷，這裡不擴大宣稱。

## 核帳與證據範圍

[verified/snapshots.json](verified/snapshots.json) 有 72 份完整預算快照（41 final、31 interrupted）；[extra/snapshots.json](extra/snapshots.json) 有 16 份（9 final、7 interrupted）。根包含原樣 `grant.json`、`ledger.json`、有產生才有的 `backend.json`、`gateway/*.json`，也保存 inbox/receipts/tmp；沒有 backend 表示從未提交效果。中斷快照允許 inflight，final 要全部終局。這 88 份已交給 budget_integration 線用不 import 包的程式獨立核帳，核帳結果以該線報告為準。

最初 [results.json](results.json) 另外保留未修正 injector 的先行結果：其中 2 個 EIO 案攔了 Python open，未命中核心 os.open，不能當成產品失敗。修正只在證據腳本，完整重跑到 verified；先行快照不納入本表或獨立核帳。此處不刪先行證據。

可重跑（從 repo 根）：

```sh
QA_OUTPUT=/tmp/astra5-budget-probe-output python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/budget-crash/run_probes.py
QA_OUTPUT=/tmp/astra5-budget-extra-output python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/budget-crash/run_extra.py
```

輸出資料夾需使用新名字；腳本不覆寫既有快照。輸出根由重跑者保存或清除，測試程序自己的暫存根會自動清理。

清理：先行、verified、extra 各自 [cleanup.json](cleanup.json)、[verified/cleanup.json](verified/cleanup.json)、[extra/cleanup.json](extra/cleanup.json)，皆 `all_waited=true`、`remaining_mentions=[]`、`root_removed=true`；verified 475 個、extra 49 個追蹤 subprocess 均已 wait。對應完整 ps 存各目錄的 cleanup-ps.txt。
