# 核心／控制／稽核與 F47 驗收

17 個探針全過，案例耗時合計 1.906 秒；本線沒有新 B／G 發現。A4-01、A4-02、A4-05 修好，A4-06 的去重有效期已由文件明定，舊現象在有效期外仍可發生，符合修補決策。

重跑：從 repo 根執行 `PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-4-infra-evidence/core/probe_core.py`。

| 項目 | 結果 | 契約與可觀察證據 |
|---|---|---|
| A4-01 | 修好；6／6 | 請求與 birth 各注入 EIO／EACCES／ESTALE；全部確有命中，請求留著、無回條、birth 位元組不變、任務仍活；round.json.mounts 記 unknown。解除故障後下一 tick 正常掛上。核心卡 2.3、spec §0／§4.5。 |
| A4-02 | 修好 | A 停在取表鎖前，B 同 req_id 完成 run 2；A 恢復回 once=done，表上沒有第二個 once，後續 tick 不起 run 3；外部執行紀錄僅 1、2。control 契約卡鎖內重讀 birth 保證。 |
| A4-05 | 修好 | 真 daemon 中途登記 a/nested，受 audit 包裝的既有 Python 任務其後寫入 nested/result.txt 得 ok=false，scan.bad 也找到；同時寫自己的 own.txt 得 ok=true。任務本身越界屬 M，audit 正確記錄，M 不列 bug。 |
| A4-06 | 修好（文件） | run 2 birth 尚帶 req_id 時重送回 done；keep 已換 run 3 後再送回 added。新契約明訂的期限就是如此，沒有新 G。 |
| §4.4(a) | 2／2 | 真 tick 在 after-birth 及 before-once-delete 自行 SIGKILL，rc=-9；當下 tasks 仍有 launch 而 birth 已存在。下一 tick 移項且不多起。after-birth 任務執行 0 次；before-once-delete 執行 1 次，均符合最多一次。 |
| §4.4(b)／§5.1 | 2／2 | 普通結束及 tock-after-finish SIGKILL 後重播：報結束的 tock 1 保留槽，tick 2 仍保留，tock 2 才刪。 |
| F47：history | 通過 | 真 history keep 先記 round 1，round 2 通知寫入 EIO：round.json 記 notify_errors；已關回合再 tock 與下一 tick 都未補送。round 3 正常通知後，歷史為 1、gap [2,2]、3。取樣缺號屬 X 後果，符合 modules/README 的明確界線。 |
| F47：同回合重播 | 通過 | 真 tock 在 tock-summary SIGKILL，重播補 tock.json；已提交 last-round 位元組不變。核心卡 2.4／spec §7。 |
| F47：once_retry 漏取樣 | 通過（界線內） | 真 retry keep 在 lost never_started 被報出的 round 4 收不到通知；round 5 正常通知時原槽已刪，未加回、外部執行次數 0。once_retry 契約卡明確不管取樣漏回合與槽已刪，退回最多一次；不列 B／G。 |
| F47：once_retry 已留 pending | 通過 | 在 lost 的總結以公開 scan API 取樣，但 tasks.json 注入 EIO，留下 pending；下一回合再次 scan 加回成功，只執行一次。此項隔離測公開 pending 機制，並非宣稱 keep 程序實際收到了被故障擋掉的通知。 |

證據：[探針](probe_core.py)、[17 項 JSON](results.json)、[執行紀錄](probe.log)、[清理證據](cleanup.json)。初版探針誤把 mounts 當 tick 回傳欄位、把 audit scan.bad tuple 當 dict；已修正探針，留 [探針校正說明](harness-corrections.json)，這兩項不是產品失敗。

測試只讀 production 與舊 astra-3 evidence；新探針延續 astra-3 core-probes.py 的加掛故障、probe_modules.py 的控制競爭／去重期限／動態登記排程。所有測試根在自己的 `/tmp/astra4-core-*`；每案先依 PID／PGID 收程序再刪自己的根，最後 /proc 身分掃描與 ps 均無殘留，全部暫存根已清掉。未使用 LLM、未改 scratchpad、未 commit／push。
