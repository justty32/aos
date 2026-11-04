# astra-6 budget／step 驗收

A6-02 驗收通過。astra-5 原 50 案、loop6 6 案、本輪新增 6 組 budget 邊界、8 個 step／daemon 整合測試及 4 個 max_resends 真任務測試全部通過。未找到新的 B／G。沿用 astra-5 未改內容的獨立核帳器，127 份本輪新快照、460 筆轉移全部通過；5 個負對照全部抓紅。本線未修改既有程式、測試或文件，未用 LLM。

| 批次 | 結果 | 耗時 | 原始證據 |
|---|---:|---:|---|
| astra-5 主批 | 41／41 | 10.334 秒 | [results](crash/verified/results.json)、[log](crash/verified-run.log) |
| astra-5 補充（真 EACCES 修版期待值） | 9／9 | 1.707 秒 | [results](crash/extra/results.json)、[log](crash/extra-run.log) |
| loop6 自報探針獨立重跑 | 6／6 | 2.901 秒 | [results](crash/loop6/results.json)、[log](crash/loop6-run.log) |
| 本輪 budget 邊界 | 6／6 | 6.589 秒 | [results](crash/edges/results.json)、[log](crash/edges-run.log) |
| astra-5 時鐘／step／daemon | 5 組額外時鐘觀察＋8／8 unittest | 9.886 秒 | [results](integration/results.json)、[unittest log](integration/step-unittest.log) |
| max_resends 新邊界 | 4／4 | 2.528 秒 | [results](resends/results.json)、[log](resends/run.log) |

耗時為各批自身耗時；crash 四批是逐案耗時總和。不同批曾平行，不能把總和當整輪牆鐘耗時。integration 的 `own_probes` 雖有 6 列，其中真 daemon SIGKILL 案也列在 8 個 unittest，沒有重複計數。

## A6-02

- 原 EIO 探針確實命中 backend.json 讀取一次；`call` rc 3、stdout 一行 unknown JSON、stderr 空，預留和 intent 保留。恢復後同 K rc 0、used=1、accepted=1。見 [verified/results.json](crash/verified/results.json) 的 `eio-backend.json`。
- 原真 EACCES 探針用 UID 1000 將自己的 backend.json 暫時 chmod 000；rc 3、一行 unknown、stderr 空，故障期間檔案位元組不變。先前 seed 已用 1，故障 K 保留 inflight=1；恢復後總 used=2，代表故障 K 只新增一次效果。見 [extra/results.json](crash/extra/results.json) 的 `eacces-backend`。
- loop6 重播同一後端故障 3 組，每組 call→cancel→settle→call 都回 3；沒有終局假回條或退款。grant／ledger／gateway EIO 對照仍過。
- 本輪另測入口 `.lock` 真 EACCES（call／cancel）與 inbox 寫入權限故障（settle）：共同 unknown／rc 3／無 traceback，恢復後同 K 完成且只扣 1。這些是正常 X，不列新 B。

## §9／§10 邊界

| 契約 | 實測／判定 | 證據 |
|---|---|---|
| clock_hw：拒絕與重播也推高 | success@5→hw5；到期 denied@10→hw10；舊 K replay@12→hw12；回撥至6，新 K unknown，hw仍12，餘額/log不多扣 | [loop6/results](crash/loop6/results.json) `loop6-clock-hw` |
| 倒退仍高於已見水位 | c=5交易後，無請求期間升20再退10；hw仍5，因此新 K 成功。符合 §9.2 的明訂限制；違反「時鐘只往前」前置，分類 M | [edges/results](crash/edges/results.json) `rollback-above-hw-M` |
| 孤兒 3 回合寬限 | c6第一次掃到；c6／7／8保留、c9清掉；未結算 K 回條保留；重播回條除 `at` 外相同 | [loop6/results](crash/loop6/results.json) `loop6-orphans` |
| 孤兒 pause／帳重開 | c6先見，c8重開帳後重算寬限；牆鐘等待不清，c10仍在，c11清；只延後清理，不改帳 | [edges/results](crash/edges/results.json) `orphan-restart-pause` |
| 孤兒未知時鐘 | 本 node round.json 暫時真 EACCES：回條保留；權限恢復後，c8仍在、c9清 | [edges/results](crash/edges/results.json) `orphan-clock-unknown` |
| 保存至明確退役 | 30 K（ok/fail/reject/cancel混合）完成後，空跑13個合成 completed_tock；ledger、backend、gateway及鎖的 SHA-256 完全不變 | [edges/results](crash/edges/results.json) `preservation-30K` |
| 成長率 | 30 ops、60 log、30 gateway JSON＋30 lock；25 backend effects（5筆cancel無effect），accepted=20；inbox=0、receipts=0 | 同上 |
| 退役 | inflight=0後標退役，新 K denied、舊 K replay成功；marker讀不到時新 K unknown／舊K仍可重播；重開帳仍拒新 K，ledger全文不變 | [edges/results](crash/edges/results.json) `retired-EACCES-restart` |
| max_resends | 0→共1次；預設1→共2次；3→共4次，皆在額度耗盡時 halted unknown，再推3回合不偷重送。同一request、attempt遞增 | [resends/results](resends/results.json) |
| 人工續送 | max_resends=0耗盡後 `resume --resend`，同request以a2完成 | [manual result](resends/test_edge_manual_after_zero.json) |

§9 五條已有明確歸屬：取消僅保證可查回假後端；水位以外的回撥為 M；歷史保存與全檔重寫成長為明訂 v1 界線；holder 自報屬合作式部署前置；重送上限用完停等人是規格行為。沒有把「理論上可以更穩」升格為 B／G，也不建議本輪新增壓縮、身份驗證或無限重試。

## 獨立核帳

[audit.py](integration/audit.py) 與 astra-5 原件 SHA-256 相同：`7182a4c49b345407b4843912905653c4db2cad5a18b97dc0c049c993b1093392`。只用標準函式庫，不 import budget／測試。核對逐筆守恆、非負、K 去重、ops/log、入口結算 SHA、後端效果及 accepted 計數。

| 快照批次 | 份數 | 轉移 |
|---|---:|---:|
| astra-5 主批重跑 | 72 | 229 |
| astra-5 補充重跑 | 16 | 29 |
| loop6 重跑 | 10 | 20 |
| 新 budget 邊界 | 8 | 133 |
| step／daemon／時鐘 | 21 | 49 |
| 合計 | 127／127 | 460 |

全部原始核帳：[audits.json](audits.json)、[audit-summary.json](audit-summary.json)。[負對照](negative-controls.json) 5／5：加後端計數、破壞log餘額、重複reserve、改結算雜湊、移除ops；都是複製到自己 /tmp 的快照後才改，未碰受測原件。

## 範圍與重跑

新增邊界是 CLI／檔案協定探針，不 import budget；時鐘邊界用自己臨時 node 的合成 round.json 控制條件，不能冒稱真 daemon 已跑13回合。真 daemon 的 pause／重開／SIGKILL、step close／槽刪／request重送由 integration 8案涵蓋。max_resends 4案使用現有fixture，實際起 keep直譯器與once子任務，沒有替換產品邏輯。30 K 用於核對保存成長率，未宣稱 budget 做300回合長跑；使用者的300+回合要求屬adapt線。

可重跑腳本：[原41案](crash/run_probes.py)、[原9案](crash/run_extra.py)、[loop6](crash/run_loop6.py)、[本輪6邊界](crash/run_edges.py)、[integration](integration/run_probes.py)、[max_resends](run_resends.py)、[全快照核帳](audit_all.py)。原探針僅調整repo尋路；run_extra再把舊版EACCES的「期待B」斷言改成修版契約。

從repo根執行，例如：

```sh
PYTHONDONTWRITEBYTECODE=1 QA_OUTPUT=/tmp/astra6-budget-rerun-new python3 proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/budget/crash/run_probes.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/budget/run_resends.py
```

127份快照分裝 [verified](crash/verified/snapshots.tar.gz)、[extra](crash/extra/snapshots.tar.gz)、[loop6](crash/loop6/snapshots.tar.gz)、[edges](crash/edges/snapshots.tar.gz)、[integration](integration/snapshots.tar.gz)。要重跑 `audit_all.py`，先在各壓縮檔所在目錄解壓 `snapshots.tar.gz`。

## 清理與最該修的三條

[cleanup-final.json](cleanup-final.json) 與 [final-ps.txt](final-ps.txt)：直接追蹤638個子程序均已不在；fixture額外檢查12個真任務測試空間，live_pids全空；17個自己建立的測試根全已刪，ps無這些root。沒有碰scratchpad。大量快照只封存本線自身產生的副本。

最該修的三條：沒有。A6-02與本線loop6契約收口皆驗收過。
