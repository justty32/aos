# astra-6：adapt 獨立 QA

adapt 主矩陣 38／38 通過；另確認 **A7-01：`scale.round` 的實際取整是 ties-to-even，與 spec §2「四捨五入」不符（B，低嚴重）**。這個落差不破壞誤差界，不涉及核心、帳務或資料刪除。藍圖 §3.3 的 `800`／`799` 門檻範例則是藍圖錯，實作遵守區間公式。無其他新增 B／G。未修改既有程式、測試、文件，未 commit／push，未使用 LLM、未碰 scratchpad。

## 方法與結果

[probe.py](probe.py) 是本輪自行撰寫的 fixture／發布者／控制器，未呼叫作者的測試案例。可控矩陣直接呼叫未修改的核心 `tick`／`tock`，透過真 runner 啟動真 adapt／step 子程序；流速、pause／resume、daemon 重開使用真 daemon 與 CLI 控制檔。沒有偽寫生命週期檔來假裝跑了回合。故障都在自建 `/tmp/astra6-adapt-*`，真 EACCES 用 UID 1000 下的 chmod 000，確實捕獲 `PermissionError`。

| 測項 | 結果與證據 |
|---|---|
| 可控矩陣 | 29／29；6.427 秒。[matrix-results.json](matrix-results.json)、[matrix.log](matrix.log) |
| 真 daemon 流速與控制 | 9／9；35.340 秒。[flows-results.json](flows-results.json)、[flows.log](flows.log) |
| 獨立核算 | 617 份依據 sha、605 次 Decimal 誤差帶／門檻核對；除已標示的取整文字落差外皆過。[audit.py](audit.py)、[audit-results.json](audit-results.json) |
| 取整補充重現 | check rc 0／`[]`；正负 10 個 tie 輸入，保留完整 basis／trace／value。[rounding_probe.py](rounding_probe.py)、[rounding-results.json](rounding-results.json) |

## adapt 驗收表

| 面向 | 觀察 | 判定 |
|---|---|---|
| 20 ms／200 ms | 12 份暫存器，skipped 增 36；最大來源年齡 1 | 過 |
| 200 ms／20 ms | 45 份，34 對相鄰值重複；skipped 不增、最大年齡 0 | 過；慢不是壞 |
| 50 ms／50 ms | 20 份全部 ok、最大年齡 0 | 過 |
| 10 ms／2 s | 6 份，skipped 增 287、最大年齡 0 | 過；只取最新、不補取樣 |
| 2 s／10 ms | 100 份，98 對相鄰值重複、最大年齡 0 | 過；極慢來源仍 ok |
| 來源 pause／resume | 來源鐘凍結後 sha／年齡不變、state ok、stalled；resume 後恢復 advancing | 過 |
| stall 3 | 停鐘後自己的第 1～3 回合 ok，第 4 回合 unknown／stalled、last 保留 | 過 |
| daemon SIGKILL 重開 | 只殺本 fixture daemon PID；原回合續走、8 份觀察無 reset | 過；兩 node 共用同一 daemon，重開涵蓋來源及消費端 |
| 來源重建 | 來源已停、無發布者，重建其 `.aos`；舊 publication 留著，reset／void_basis／last.void；新值恢復 ok | 過；合法停止後重建 fixture，不是工作中手改鐘 |
| 來源檔半寫、缺 round、缺 select、bool 型別 | 前 2 回合撐舊值、held 1／2；第 3 回合 unknown，last 不丟；修復下一回合 ok | 過；半寫屬 M，其他為不知道分支驗收，不硬列 bug |
| 真 EACCES | chmod 000 且讀取確實 PermissionError；同一耐性分支 | 過，X |
| 檔案換資料夾 | 不崩潰，先撐後 unknown，再恢復 | 過，M，不列 bug |
| 來源檔不存在 | 立即 absent，last 保留，不走耐性 | 過 |
| 工作中改鏈 | chain_changed／unknown；改回原宣告恢復 | 過，M，不列 bug |
| adapt 任務 SIGKILL | 只殺 task PID；keep run 前進，since／basis／skipped 續接 | 過，X |
| dst pause | 等 pause 完成後，0.7 秒內暫存器內容、mtime、框架不變；resume 後繼續 | 過 |
| max_age 2 | 年齡 1／2 仍 ok，3／4 為 expired | 過 |
| ge／gt／le／lt | 每個算子各測 x=79／79.5／80／80.5／81，err=.5，共 20 個精確端點；整段真／假或交界 unknown 與獨立判定一致 | 過 |
| step num | 790／799 不成立；800 為 unknown，step 保持 w；801 恢復 ok 後 step ended／ok | 過 |
| 長跑 | 真正 320 個新增、已關 dst 回合，1 → 321；321 份暫存器均 ok | 過 |

速率是 timeline 設定，不宣稱 Linux 排程的實際間隔等於設定；本輪沒有採用「每一回合一定取到來源的某個固定增量」這種契約沒有保證的斷言。所有流速採固定 801，避免把刻意進入誤差帶的輸入誤判為 flaky。

## 發現

### A7-01 — B／adapt／低嚴重：scale.round 未兌現四捨五入文字契約

- 契約：[adapt spec §2](../../../../packs/adapt/spec.md)：「有 `round` 就四捨五入到小數 `round` 位」。README 前置皆成立：合法 JSON、整數來源 round、原子發布、單一 keep／max_live 1、鏈不動、所有權正確。
- 重現：合法宣告 `select value.x → scale {mul:1,q:0.5,round:0,as:"c"}`，check 回 0／`[]`；發布 `x:2.5`。真任務回 `state:ok, value.c:2.0, err.c:0.5`，trace 亦為 2.0；按四捨五入應為 3。`0.5→0`、`4.5→4` 同樣；`1.5→2`、`3.5→4` 是對照。負值亦附證據，但不靠負值語意判定。
- 證據：[rounding-results.json](rounding-results.json)、[rounding-registers.json](rounding-registers.json)、[rounding-snapshot.tar.gz](rounding-snapshot.tar.gz)，可重跑 [rounding_probe.py](rounding_probe.py)。根因是程式直接用 Python `round()` 的 ties-to-even。
- 建議修法（一行）：決定照既有文字做四捨五入，或把 spec 明定為 ties-to-even 並補正 tie 範例；不需要核心新增保護。
- 影響界線：兩種結果都在宣告誤差界內，可重算性仍成立；這是產出值與文字承諾不符，不是來源故障、不屬 M。

### 藍圖 §3.3 門檻勘誤（不另列 B／G）

實作／spec 正確。`mul=.1,q=.05,round=1,ge=80` 時：800 → 80.0，區間 `[79.95,80.05]` 跨門檻，應 `hot:null`／unknown；799 → 79.9，區間 `[79.85,79.95]` 全低於 80，應 false／ok；790 → `[78.95,79.05]` false／ok。藍圖寫 800 true、799 null 的兩項應修改。程式不該為了符合錯誤範例而偏離誤差公式。[matrix-results.json](matrix-results.json) 的 `blueprint_formula` 留有真任務完整版本。

## 長跑、證據與清理

長跑耗時 3.304 秒（in-process 核心 tick/tock，真 task）；起終 `round.json` 均 `open:false`，新增恰 320 回合。`dst/in` 1 檔、`dst/adapt` 1 檔、adapt 槽 5 檔、`src/out` 1 檔，前後**檔名集合**相同，連隱藏檔都列入掃描。每圈等對應 `my_round` 寫出才進下一圈，不以回合號跳躍充數。[long320-registers.json](long320-registers.json)、[long320-snapshot.tar.gz](long320-snapshot.tar.gz)。

大量 fixture 快照已壓成各案 `*-snapshot.tar.gz`；逐回合暫存器另存 `*-registers.json`，便於直接核對。共 15 個最終 fixture 全部清除；[final-cleanup.json](final-cleanup.json) 確認各 root 不存在、所屬 live PID 0；[final-ps.txt](final-ps.txt) 保存完整程序核對。只依 PID 終止自有程序，未使用 `pkill -f`。取整探針曾補增負值後重跑，前一次也走同樣 finally 清理。

補充：題目提到的 loop6 adapt `evidence/summary.md` 不在此 checkout；搜尋只找到 loop6 subd／budget 的 summary。此線直接依現有 README／spec／藍圖／problems 判定，不把缺少作者自報證據當產品 bug。

重跑（repo 根）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/adapt/probe.py matrix
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/adapt/probe.py flows
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/adapt/rounding_probe.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/adapt/audit.py
```
