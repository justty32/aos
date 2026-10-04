# proto7-2 第四輪回歸（astra-4）：loop4 修補驗收

**loop4 的 A4-01～08 修補通過；全套三次各 280 項全綠，step 450 回合檔數沒有持續成長。但本輪不能判整體驗收通過：G3 壓力探針 10／10 都留下原有子任務，下一個子 daemon 超過兩回合仍未收掉，列為唯一新發現 A5-01〔B〕。** F47 的漏通知後果符合 history、step、once_retry 各自契約；沒有因此新增 B／G。A4-09 仍是按契約處理的 X，A4-10 仍是 M，不列 bug。

受測 HEAD：`b8568cdbf8122b1aaa11b9e67c49228e0e145d2c`，在指定 `8fc0e774` 之後。依[核心契約卡](../component-contracts.md)、各包 README 與[原則 9、10](../../../proto7/notes/principles.md)判定。本次只測 `proto7-2`，沒有呼叫任何 LLM；沿用舊探針時複製到本輪 evidence，沒有改舊 evidence、既有程式／測試／文件，沒有 commit／push，也沒有刪除或清空 scratchpad。

## 測試結果

從 repo 根執行 `python3 proto7-2/tests/run_all.py` 三次；耗時為程序實際經過秒數。

| 測試 | 結果 | 耗時／說明 |
|---|---|---|
| 全套第 1 次 | 280／280，rc 0 | 81.911 秒 |
| 全套第 2 次 | 280／280，rc 0 | 83.082 秒 |
| 全套第 3 次 | 280／280，rc 0 | 84.376 秒 |
| 核心、control、audit、F47 | 17／17 | 案例合計 1.906 秒 |
| step 原反例與 F47 | 通過 | 型別、選項、耐性、結果保存、停點 |
| §4.4 新保證 | 4／4 | birth／移項中斷 2 案、刪槽時點 2 案 |
| G3 並行壓力 | **0／10** | 每案都與全套重疊，均違反兩回合門檻 |
| step 長跑 | 450 已關回合 | 25.124 秒，112 次工作完成 |
| 契約一致性 | grep 0 筆 | 核心 35 組保證、七包靜態核對；subd 有動態反例 |

三次全套皆無 failure、error 或 skip，**未觀察到全套不穩定案**；G3 是額外探針穩定重現的失敗。[全套／壓力結果](2026-10-04-astra-4-infra-evidence/stress/results.json)、[核心摘要](2026-10-04-astra-4-infra-evidence/core/summary.md)、[step 摘要](2026-10-04-astra-4-infra-evidence/step/summary.md)。

## A4 驗收表

| 舊項目 | 判定 | 修後實測 |
|---|---|---|
| A4-01 加掛讀不到當空值 | 修好 | 請求／birth 各注入 EIO、EACCES、ESTALE，共 6 案：請求保留、無回條、birth 不變；解除後正常掛上。 |
| A4-02 control 並行重複起 | 修好 | A 等表鎖、B 同 id 完成 run 2；A 恢復回 done，沒有第二個 once／run 3。 |
| A4-03 初始 wait 耐性 | 修好 | r1 的 since=1；patience=2，在 r4 進 timeout。 |
| A4-04 checker 型別／繼承 | 修好 | start／ok／result.ok 為陣列皆 rc 1、JSON 診斷、無 traceback；全域 kill 搭 wait 被拒。 |
| A4-05 audit 登記邊界 | 修好 | 任務已啟動後登記巢狀 node；後續越界寫入記 ok:false，scan.bad 找到，自有路徑仍為 true。 |
| A4-06 control 去重期限 | 修好（文件） | 目前 birth 帶 id 時回 done；keep 換 run 後回 added，符合新寫明的期限。 |
| A4-07 step 選項／停點 | 修好 | run 步 wake:true 通過；timeout kill 帶正確 run，halt.kind=timeout，與 spec 一致。 |
| A4-08 契約卡過時 | 修好 | 舊核心責任已移除，非一般 daemon 請求例外、packs 測試入口皆同步。 |
| A4-09 外部故障 | 仍在（X） | 意圖後中斷、延後恢復停 unknown；連續未知最多重送一次，未違反保證。 |
| A4-10 手改 frame | 仍在（M） | 缺 pc 仍會 KeyError；spec §7 已補誤用界線，不算修掉例外，也不列 bug。 |

證據：[核心 17 案](2026-10-04-astra-4-infra-evidence/core/results.json)、[step 原探針](2026-10-04-astra-4-infra-evidence/step/step-probes.json)、[契約檢查](2026-10-04-astra-4-infra-evidence/contracts/checks.json)。

## F47 與新保證

F47 確實只記 `notify_errors`：已關回合再 tock、下一個 tick 都不補舊通知；**同回合因 SIGKILL 重播仍補寫**，已提交總結不變。

history 漏 r2 後得到 `1、gap [2,2]、3`。once_retry 漏掉報 lost 的那回合，下一回合槽已刪，沒有重派；這正是其卡片排除的取樣漏失，退回最多一次。另以公開 scan API 驗證已留 pending：表讀取故障解除後能加回，只執行一次；這項不冒稱 keep 收過失敗通知。[證據](2026-10-04-astra-4-infra-evidence/core/results.json)。

step 連漏 r2～r5 四次通知，子槽已刪，r6 仍靠槽外結果接回原 request／attempt，兩步各只起一次。wait 漏 r2～r4，r5 恢復後照原 since 計算 timeout；檢查延後但耐性沒有重設。7 次 EIO 均確認命中，未出現契約外行為。[證據](2026-10-04-astra-4-infra-evidence/step/f47-step.json)。

§4.4(a)：真 tick 在 birth 後、移項前兩個點 SIGKILL，當下表上仍有 launch、birth 已存在；下一 tick 移項而不多起，執行次數分別為 0、1，符合最多一次。§4.4(b)：正常及 tock 中斷重播兩案都在報結束的 tock 1 保留槽，tick 2 仍在，tock 2 才刪。[核心探針](2026-10-04-astra-4-infra-evidence/core/probe_core.py)。

## 發現清單

### A5-01〔B／subd〕父 kill 未完成的子任務，新 daemon 不會依承諾收尾

- **契約**：[subd 契約卡與界線](../../modules/subd/README.md)第 22、55 行承諾父 kill 收子任務，寬限內未收完由下一個子 daemon 身分掃描收；本輪驗收門檻為重開後兩回合內。
- **重現**：父 node 的 keep 經 subd 起子 daemon；子 node 起 3 個保留正常身分、忽略 SIGTERM 的任務。全套並行時，透過帶 run 的槽 kill 收父任務，等 keep 重開子 daemon，再追蹤原 PID／starttime 與已關回合。
- **結果**：10／10 均有 3 個原任務超過兩回合仍活；父 kill 回條卻是 ok:true。加驗追到新 daemon gen 2、r7 已關，原三程序仍是同一 starttime、狀態 S，總結仍列 alive。不是 zombie、PID 重用或任務刻意脫離身分。
- **歸屬**：subd 的收尾保證沒有兌現。核心 §5.4 只對「疑似 lost」掃描；原任務／runner 還活會判活，不能直接推導成重開必殺。這不是 M，也不把所有 daemon 重開都改成殺任務。
- **證據**：[10 案結果](2026-10-04-astra-4-infra-evidence/stress/results.json)、[身分與 r7 快照](2026-10-04-astra-4-infra-evidence/stress/confirm/identity.json)、[重跑腳本](2026-10-04-astra-4-infra-evidence/stress/run_stress.py)。
- **建議修法**：由 subd 辨識並回收前一代未完成 stop 的殘留；也可依藍圖評估 `kill_grace_s` 或併行收槽，但須用同探針確認效果，不能只補文件或假定延長寬限就能根治。

## G3 壓力結果

10 案分布在三次全套期間，每案開始與結束時全套程序都仍在跑。送出父槽 kill 後約 1.15～1.18 秒看見替代 daemon；它繼續關回合，三個原任務卻未回收，**10 案全部失敗**。額外身分確認案不併入 ×10 統計；它延長觀察到 r7，確認相同現象。[精簡結果與完整時間序列](2026-10-04-astra-4-infra-evidence/stress/results.json)。

## 450 回合長跑與收場

真 daemon 跑 CSV convert→stats→end，`restart_on_end:true`、`wake:false`、interval 20ms。450 是已關回合數；完成 112 次工作，112 份報表列數／request 都正確，每步 attempt 都是 1，halt／error 為 0。每次 ended 的工作目錄固定 **10 檔**、4,381～4,397 bytes；全階段工作／node／root 檔數範圍為 4～11／7～27／8～34。以相同階段比較，沒有持續累積；結論限本次 450 回合。[長跑證據](2026-10-04-astra-4-infra-evidence/step/longrun.json)。

指定 grep 為 0 筆（rc 1 代表無匹配）；核心卡 35 組保證的 spec 節號對得上，七包已做靜態程式對照，但不能蓋過 subd 的動態反例。[契約詳核](2026-10-04-astra-4-infra-evidence/contracts/summary.md)。

探針初版曾讀錯 tick 回傳欄位、audit tuple，以及使用不支援的故障掛點；已校正，只採修正後確有注入命中的結果，不列產品失敗。各線已依 PID 清理自己的 /tmp 根並以 ps 核對；既有來源雜湊與最終殘留核對另見[收場稽核](2026-10-04-astra-4-infra-evidence/final-audit.json)。

## account 草稿意見

以下只審草稿，不算發現、不實作。單 node、通用包、核心零新增符合 r1／r6；`reserve→run→settle` 可用 step 的 run／wait 與槽外回條接，但介面尚未定稿。[詳細對照與行號](2026-10-04-astra-4-infra-evidence/contracts/summary.md#account-草稿意見不算發現)。

1. grant、ledger 有四欄；gateway 缺前置條件，需交代請求人、id 作用域與 grant／預留／使用者的對應。
2. 明確失敗、step `ok:false` 或核心 `never_started` 都不等於資源沒花；全退應靠入口未支用證據，未知繼續預留。
3. 同 id 永遠回同結論若包含 unknown，後續證據便難更新；「未知不退」也和待定的逾時自動退款衝突，需先統一。
4. reserve／settle 是不同操作，去重鍵要接上 step 的 request／attempt；帳與去重證據須活過 step close，不能只靠會被清掉的結果。
5. grant「可再分」尚缺子不超父、分出後不能原地再花的保證；`[from,until)` 與核心 `until_round` 含上界不同，不能直接照抄數值。時鐘邊界也要明列。

## 最該修的三條

只有 **A5-01：父 kill 後子空間任務的收尾**。本輪沒有第二、第三條已確認的新 B／G，不湊數；account 保留為草稿意見。
