# 檔案、收件與清理

← [基底](README.md)｜[共用契約](../contracts.md)｜[通用 tick](../tick.md)

## B-401：資料夾就是狀態〔使用者方向 2026-09-29〕

node 的狀態就是裡面的檔案；git repo、group 提交與恢復，以 [通用 tick](../tick.md) 為正本。

布局以[協議 node](../protocol/node.md)為正本：

- `.aos/` 是系統區：追蹤 `.aos/inst.json`、`.aos/tasks.json`、給上層讀的 `.aos/summary/` 及待送 `.aos/outbox/`；kernel 替成員跑工具／LLM 的 once 放 ignored `.aos/jobs/<id>/`；node 事項放 ignored `.aos/attention/`，不隨 group 還原；投件鬧鐘的待查紀錄放 ignored `.aos/alarms/`（[P-206](../protocol/node.md)）。
- `requests/`、`responses/` 是 ignored 收件，group 還原不碰；已消費內容與工作狀態移入追蹤區。
- `work/` 是 ignored 任務暫存進度；`public/` 是可供其他 node 存取的共用空間；設定在追蹤的 `config/`。

設定手改、匯入與生效時機見 [A-102](../agent/configuration.md)；追蹤區寫者協調、避免大量 commit 與 submodule 的邊界見 [通用 tick](../tick.md)。

## B-402：完整發布與收件消費〔使用者方向 2026-09-29〕

收件者只讀完整發布的檔案。〔建議預設，未拍板〕發布採同一檔案系統的暫存檔→完整寫入→rename 成正式名，不覆蓋既有同 ID 檔；需要確認已耐久收件時，先同步檔案與父目錄，成功後才回覆。臨時檔不算收件成功；發布失敗就報錯，不能留下半份正式檔。

收件消費與對外派送的提交順序以 [tick 的 Q1／Q2](../tick.md) 為正本；同 ID 衝突見 [B-503](transport.md)。發布完整收件不等於已消費，也不代表外部工作完成。

**驗收**：半份檔不成為正式收件；發布失敗不回成功，也不覆蓋既有同 ID 原件。消費與派送中斷場景見 tick。

## B-403：checkpoint 提案交易

（09-29 重寫：已刪；由[通用 tick 的 group／git](../tick.md)取代。）

## B-404：滿碟、保留與清理〔使用者方向 2026-09-29〕

寫檔或 git commit 遇到滿碟、I/O 錯誤時，不宣稱已收件、已消費或已提交；保留舊 commit 與尚未消費的收件原件。該 node 先處理失敗並完成必要恢復，不能直接開下一格覆寫現場；可行的取消與程序收尾仍要做。缺可信結果就標 `unknown`，不自動重跑找結果。結果只保存一部分時須明說不完整，不能冒充完整結果；resume 也不會讓遺失的內容長回來。磁碟記帳是否啟用見 [身分與資源](identity-resources.md)。

**`aos-clean` 是 node 任務表的一項**，預設 agent、kernel 範本都加上，由 tick 呼叫；有權限的人或 agent 也可直接跑。它自己記上次清理時間，未到期直接回 0；間隔放清理設定，預設一天。任務表不加間隔欄位，不為清理另開定時程序或叫醒冷 node。

只清自己認得的資料（預設 agent／kernel 任務產生的）；不認得的不碰、不回報，自訂任務自己清。unknown 依 [S-401](../scheduling/operations.md) 放著，到期清理。其他內容須已終局、已消費、超過保留期且無引用；在途工作、未消費收件、未結清副作用與仍有引用的材料保留。node 退役不自動刪資料。kernel 的持久序號檔 `state/kernel/sequence.json` 永遠不清（排隊先後靠它，[S-204](../scheduling/admission.md)）。

保留期預設 30 日，起算點：unknown 從首次把該狀態提交到 git 的 commit 時間起算，不用 mtime 猜；採用 run 的從 run 終局起算，其餘從工作終局起算。〔第十八批〕只記錄、不建立 input 的訊息（帶 `in_reply_to` 的回話、kernel 收的 `agent.say`）從接件確認提交的時間起算，套一般保留期，還有引用就保留，不另建 input。本地動作的 `.stdout` 檔（[B-103](work.md)）跟它那份請求副本一起清。每批預設最多 64 件，清不完下次再做；預設封存，也可設定刪除。去重期內的請求證據不能先清；已消費原件仍在，先補清相符原件再清證據，同 ID 衝突就保留。清理持同一把 node 鎖並依 group 提交；封存先存妥副本才移除日常檔案，中斷可補做。

〔使用者方向 2026-09-30，第十八批〕**壞掉的收件原件**（[B-623](../tick.md) 報過一次的那種）留在 `requests/`，從那件事項記下的首次回報時間（`reported_at_ms`，[P-601](../protocol/ops.md)）起過了保留期，由 `aos-clean` 刪掉；刪之前不必等人把事項標完成。事項檔不見了就當不認得，不碰。

git 歷史回收延後（[P-008](../protocol/README.md#p-008)）；同 ID 重送要補投的原回應就是從 git 歷史撈（[B-503](transport.md)），所以回收以前要先顧到這點。

**驗收**：滿碟不回假成功、不刪收件原件；未到清理間隔回 0。壞收件原件過了保留期被刪，期內留著。到期 unknown 可清，其他未結、有引用及保留期內的內容保留；不認得的資料原樣留下且不回報。中斷可繼續，清理不造成收件重吃。

以上是新規格，尚未實作；目錄與格式見[協議篇](../protocol/node.md)。
