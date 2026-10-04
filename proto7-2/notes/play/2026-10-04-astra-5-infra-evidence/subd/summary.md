# subd 第五輪獨立回歸

A5-01 的「新代起前回收前代」通過：正式並行 G3 10／10 全過，延長至 r7 的加驗也無活前代。本線確認一項新 B：**A6-01，允許 stop 的停止紀錄提交被 SIGKILL 中斷後，重開會回收本應接回的任務。** 未改產品程式、測試、既有文件；只新增本 evidence、自建／清除 /tmp，沒有使用 scratchpad 或 LLM。

## 結果

| 測項 | 結果 | 證據 |
|---|---|---|
| 正式 G3 並行壓力 | 10／10；每案確有前代殘留，首次觀察到新 daemon 時原任務均不在 | [完整時間序列](stress-parallel.json)、[可重跑腳本](run_stress_parallel.py) |
| G3 延長 r7 | 已關 r7：三個舊 task gone；三個舊 runner 已退出（subreaper 尚未 waitpid，暫為 Z），收場已全部 waitpid | [r7 結果](g3-r7.json)、[腳本](confirm_g3_r7.py) |
| 回收邊界 | 同根／巢狀任務被收；sibling、同名前綴 a/sub2、純 cwd 在子根的非 aos 程序保留 | [edges](edges.json) |
| subd 中斷／子 daemon 自崩 | 6 個起 argv 前窗口均可接續；2 個 argv 已起窗口因 daemon.lock 拒绝再起；子 daemon SIGKILL 後重開回收原任務 | [edges](edges.json)、[腳本](probe_subd.py) |
| 正常 allow-stop | 初探通過；另 3／3 重複對照保留原 PID 與 starttime | [確認](confirm-stop.json) |
| allow-stop 提交中斷 | tmp:stopped.json 與 tmp:subd-life.json 第 3 次，各初探 1／1＋確認 3／3 重現 A6-01 | [確認](confirm-stop.json)、[腳本](confirm_stop.py) |

正式 G3 合計 26.236 秒，每案 2.613～2.656 秒；送 kill 到首次看到替代 daemon 約 2.240～2.280 秒。前 8 案與全套第 2 次 PID 579181 重疊、後 2 案與第 3 次 PID 587022 重疊，各案開始與結束均有全套在跑。不是預設的 4＋3＋3 分布。另保留較早 10 次預跑，[results.json](results.json)：全部通過，但僅第 9 案尾端及第 10 案與第 1 次全套重疊，未混入正式並行統計。

## A6-01〔B／subd〕允許 stop 的紀錄提交中斷，重開錯收應接回的任務

- 契約：[subd README](../../../../modules/subd/README.md) 契約卡「被允許的 stop 之後不回收」、規則「被允許的 stop 不回收」承諾：不帶 --kill 的 stop 留下任務，刪 stopped.json 再起照核心接回。契約卡另承諾允許 stop 留 stopped.json 擋 keep 重起。
- 重現：合法包裝 argv、--allow-stop、子 node 一個正常保留身分且忽略 TERM 的 keep 任務；向子 daemon 下 stop（無 --kill），確認成功回條與 status.stopped=true。自有測試 hook 只計數既有 test_point 並對自己的 wrapper PID 真 SIGKILL，沒有改產品、沒有手改 life。兩窗口：① stopped.json 暫存檔写完未 rename；② stopped 已提交，但第 3 次 life 暫存檔（state=stopped）未 rename。
- 結果：① stopped 不存在，直接正常重開；② stopped 已在，先驗證它會擋重開，再依 README 刪除它並重開。兩者 life 正本仍為 running，wrapper 收掉原任務，新 daemon 起 run 2；原任務在 stop 後皆為 S 且身分完整，重開後 gone，不是拿 zombie 或重用 PID 充當反例。各窗口獨立確認 3／3 重現；正常對照 3／3 在重開前後 PID/starttime 相同。
- 歸類：前置條件都成立；SIGKILL 是 X 注入，但恢復路徑違反「允許 stop 後不回收」、造成破壞性回收，依 [component-contracts §3](../../../component-contracts.md) 與 [原則 9／10](../../../../../proto7/notes/principles.md) 歸 subd B。窗口②刪 stopped 是文件明訂操作，非手改 owner/life 的 M；窗口①連 stopped 都未刪。
- 原因：`aos7-subd` 第 235、237 行分別提交 stopped.json／life=stopped，重開只拿 life 判是否回收，無法接續合法 stop 的未完成提交。
- 建議修法：由 subd 統一「允許 stop 已完成」的持久化判定與恢復，能依既有核心停止事實接續提交；不能僅對調兩次寫入而漏掉更早窗口。
- 證據：[confirm-stop.json](confirm-stop.json) 保存成功 stop 回條、stopped 狀態、命中 hook、暫存 life=stopped、舊 PID/starttime/AOS7 身分、重開結果；[confirm-stop.log](confirm-stop.log)；[原始初探](edges.json)。

## 回收範圍與中斷分類

| 情境 | 實際結果 | 分類依據 |
|---|---|---|
| sibling a/other、前綴 a/sub2 | 皆活著 | 符合 `/` 邊界保證，无 B／G |
| 巢狀 a/sub/n1/nested 的任務 | 被收 | README 明列巢狀也在回收範圍，非誤殺 |
| 人手起非 aos 程序，cwd 在子根、無 AOS7 身分 | 活著 | 只看 cwd 不會納入，沒有誤殺 |
| 人手起非 aos 程序，測試刻意構造子 node 的 AOS7_NODE/TID | 被收 | 按身分回收符合界線，不列 B／G；若是合法任務繼承身分，本來就在 Q1 範圍，屬正常。僅人手冒用任務身分造成錯收才可討論 M，不能因「非 aos 執行檔」本身判 M |
| recovering 暫存、回收中、回收完、running 暫存、argv 前、guard 暫存 SIGKILL | hook 全命中，rc -9；重開後原任務不在才起新代 | X，恢復符合保證 |
| owner 暫存、wrapper 已起 daemon 後 SIGKILL | daemon/task 存活，重開 rc 1；不回收現役 daemon | X，daemon.lock 持有時拒絕起是明訂契約，无新 G |
| 子 daemon 自己遭 SIGKILL，非父 kill | wrapper rc 137、life=running，重開回收原任務再起新代 | X，符合保證 |
| 正常 stop 無 kill | stopped 擋重開；刪 marker 後原任務接回 | 正常行為 |
| stop 記錄提交中斷 | 見 A6-01 | B，不把恢復失守淡化成單純 X |

## 收場

所有自身暫存根皆已清除。只對自行追蹤的 PID 送訊號；沒有 pkill。每案保留清理前 PID、清理後清單、ps 輸出與存活檢查。最終全域 ps 依所有測試根比對為空；[cleanup.json](cleanup.json) 彙整五份結果，每份 `final_proc_remaining=[]`、每案 known live 為空。產品程式與測試均未變更。
