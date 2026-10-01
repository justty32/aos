# 執行器

← [基底](README.md)｜[inst](inst.md)｜[結果檔](work.md)

## B-201：啟動與交接

〔使用者方向 2026-09-29；第十九批改寫〕kernel 或 agent 派工。tick 誰開都行（[B-627](../settled/tick.md)）；daemon 是定期跑 `aos-tick` 的標準程式，不是 tick 存在的前提。經 daemon 開的 tick 與經通道掛上去的 once，由 daemon 管程序（[B-601](../settled/deferred/daemon/runtime.md)）。身分切換及解析順序依 [B-303](../settled/deferred/helper.md) 與 [inst](inst.md)。

〔建議預設，未拍板〕一次嘗試只用一個固定 attempt ID（識別見 [T-03](../terms.md)，材料見 [B-101](work.md)，結果見 [B-103](work.md)）。不確定是否已放行，不得再開同一嘗試。啟動失敗也要清空已開程序才歸還名額；根本沒跑與執行後失敗分開記，不能只看退出碼猜，見 [inst](inst.md)。

〔使用者方向 2026-09-29〕程序重啟見 [daemon](../settled/daemon/README.md)，檔案恢復見 [tick](../settled/tick.md)。

**驗收：**在建立程序前、切身分後與實際放行後各中斷一次；恢復不重開不明 attempt，舊程序未清空前不開同一 node 下一格。

## B-202：後代清空才算結束〔建議預設，未拍板〕

〔使用者方向 2026-09-30，第二十批追答 8；取代第十九批「本條是標準配備的 cgroup 框」〕cgroup 拆成兩塊：node 框、資源上限與一格結束後的收尾歸 daemon（[B-601](../settled/deferred/daemon/runtime.md)、[B-604](../settled/deferred/daemon/lifecycle.md)、[B-605](../settled/deferred/daemon/cgroup.md)）；每項任務一框是普通程式 `aos-cg`，要的任務才在 argv 包，行為正本在 [B-634](../settled/tick.md)。**放棄「沒包裝的任務一結束就清殘留」。**後代怎麼收以 daemon 那側的 B-601（runner 管名下整棵樹，有 cgroup 時框兜底）、B-604（收尾）為完整正本；本條其餘只補串流收完與結果發布。

執行器保存安全程序識別（例如 pidfd；跨重啟再核對 boot ID、PID、starttime），不拿可能重用的裸 PID 殺程序。cgroup 放在所屬 node 子樹；限制與計量只用已裝 module。

主程序退出後仍須清空後代、排空捕獲串流、完整發布結果，才能宣告正常完成。後代另開 session 也不能漏掉；有 cgroup 的受管範圍（daemon 的框、`aos-cg` 的框）用 cgroup 驗證全空（例如 `cgroup.events` 的 populated），強制清理用 `cgroup.kill`；不能只查主 PID 或 process group。兩種清法各有適用範圍：

- **一般 attempt、once 與整格 tick**（daemon 那側）：先 TERM、等寬限、再 KILL。寬限分兩種，不混用：runner 處理 inst 自己的逾時，照 [inst](inst.md) 的 2 秒；daemon 收尾（停機、解除登記、砍掉在跑的 once）用 `shutdown_grace_ms`，流程是 [B-604](../settled/deferred/daemon/lifecycle.md) 的「收尾」；一格正常結束後的殘留由 runner 直接清，本輪 daemon 重開清不掉舊程序（[B-601](../settled/deferred/daemon/runtime.md)、[B-603](../settled/deferred/daemon/lifecycle.md)）。
- **`aos-cg` 的 `task-*` 框**：行為正本在 [B-634](../settled/tick.md)（argv 見 [P-211](../settled/protocol/node.md)）。
- **沒包 `aos-cg` 的任務留下的後代**：核心不清，留下的程序一直留到這格結束；daemon 開的格由 daemon 在格後收尾（[B-601](../settled/deferred/daemon/runtime.md)）；人手或 cron 跑的沒人收，還握著鎖 fd 的會讓下一格回 75（[B-602](../settled/tick.md)）。

〔使用者方向 2026-09-30，第十八批〕「tick 與後代清空」只看 `tick` 與所有 `task-*`；node 在自己框下另開的子框怎麼處理，以 [B-605](../settled/deferred/daemon/cgroup.md) 為正本。

強制清理後代時記失敗，不以主程序 exit 0 冒稱成功。未確認清空就交待處理、不還名額；已裝 module 在移除空框前取必要計量。

**驗收：**工具 fork＋setsid 後主程序退出，後代仍被清掉；確認全空才釋放名額。清理權限不足時不能回報已完成。沒包 `aos-cg` 的任務留下的後代在 daemon 格後收尾時被清，人手跑的握著鎖 fd 時下一格回 75；包了 `aos-cg` 的驗收見 [B-634](../settled/tick.md)。

## B-203：取消與逾時〔建議預設，未拍板〕

〔使用者方向 2026-09-29，第十七批〕有權限者可要求**取消指定工作**，人與 agent 走同一入口：檔案請求 `work.cancel`（格式見 [work P-411](../protocol/work.md)），投到持有那件工作的 node，以原請求的 RPC id 定位；取消涵蓋那件工作的所有 attempt。〔第二十批〕once 是任務自己經通道呼叫的事務（[B-613](../settled/deferred/daemon/channel.md)），不是任務表上的項。〔使用者方向 2026-09-30，第十八批〕本條只適用 **once**（kernel 替成員跑的工具工作）；LLM 請求、agent 自開 once，以及 kernel／agent／custom 類任務的取消延後（[P-008](../protocol/README.md#p-008)）。

**核權**〔使用者方向 2026-09-30，第十八批〕：取消請求檔的擁有 UID 等於下列任一就收，都不是就回 `cancel_not_authorized` 並丟掉這份取消：

1. 原請求檔的擁有 UID（接件時記下）；
2. node 根目錄的擁有 UID；
3. 該 node inst 的執行帳號 UID，**接件時記下**（接件那格 tick 的有效 UID；〔暫定；第二十批改寫〕處理這件的任務包了 `aos-as` 換帳號時，記它換成的那個帳號的 UID），存進該工作的狀態，之後核權看這筆，不當場重解 inst。

2、3 是 node 的兩種主人，兩者不同時都算；once 自己 inst 的 `user` 不算主人。在[投件權就是執行權](../terms.md)（T-08）之下，這只是防手滑，不是安全界線。

**排隊中**（還沒建 launch-started 標記）：直接拿掉，原請求回 canceled、`started:false`，不開 once。

**在跑**：分兩格。本格只記 `canceling` 並提交；下一格才經通道請 daemon 砍掉那個掛上去的 once（`node.kill`，[B-613](../settled/deferred/daemon/channel.md)），daemon 對它的框做[收尾](../settled/daemon/README.md)（B-604：TERM→`shutdown_grace_ms`→`cgroup.kill`→確認全空），那一格可同步等到全空，上限 `shutdown_grace_ms`；〔暫定〕超過上限還等不到就記 unknown、保留實際占用。

**三個窗口**：

- (a) 請 daemon 砍掉時回 `not_registered`（once 已自己結束），要有 [S-401](../scheduling/operations.md) 的可信「從未開始」證據（marker、`.err`、結果檔）才回 canceled，否則記 unknown；不靠會被淘汰的 once 診斷紀錄。
- (b) 記 `canceling` 與請 daemon 砍掉分在兩格，不在同一格做。
- (c) **取消的判界只有這一套**〔第十九批依 astra 第 15 項統一〕：以「記 `canceling` 那格的提交」為界，之前已有完整結果的照原結果回；之後自己正常結束、完整發布的也照原結果——**收到收尾的 TERM 後自己正常結束（不論結束碼）並完整發布的，照原結果**；只有被收尾的訊號結束（TERM 或 KILL）、因而寫出 signal 結果的才記 canceled。

已結束或已回過結果的不動。接下取消要求不等於已取消，只有確認程序全空才可報 canceled；取消不承諾撤銷外部效果。

**逾時**〔暫定，第二十批疑-11 未答，照 a：工作的 `timeout_ms` 保留毫秒，程序在格外跑、由 runner 量〕：用 monotonic 經過時間，從放行起算，不含排隊；重啟照全殺與 unknown 規則，不重新給一次 timeout。逾時先處理的，收尾後即使取得 exit 0 也記 timeout。取消、逾時與完成的競態由負責該工作的執行器串行處理，只發布一次最終結果：已有完整結果檔就回已結束；取消照上面 (c) 判定。結果檔一旦完整發布就不被後來的取消覆寫；發布前崩潰且結果不明則按 unknown。kernel 下格收結果，不以全域交易排序。

**驗收：**交錯取消、逾時、exit 0 與結果發布，每個 attempt 只有一個結果；重送取消不重複釋放名額。node 根目錄擁有者與 inst 執行帳號不同時，兩者各送一次都收；其他帳號（含只是 once 自己 inst 的 `user`）送的回 `cancel_not_authorized`，原工作照跑。記 `canceling` 那格不收尾；`not_registered` 又沒有可信證據時記 unknown。取消的收尾送出 TERM 後，程序自己 exit 0 並完整發布結果，回的是原結果，不是 canceled。

## B-204：資源造成的失敗〔建議預設，未拍板〕

OOM 證據要有 cgroup 框：daemon 的 node 框、掛載行程的框，或 `aos-cg` 開的 `task-*` 框；沒有框的（沒包 `aos-cg` 的任務、沒 cgroup 時）沒有 OOM 證據，一律不標 OOM，只留訊號。記憶體 module 啟用時才讀相應 cgroup 的 OOM 證據；有可信 oom_kill 增量且工作失敗才能標 OOM，不能只看 SIGKILL 猜。父域 OOM 波及多件工作時附父域證據，不能歸因就保留訊號與診斷。pids／fork／exec 失敗保留 EAGAIN、ENOMEM 等原 errno；module 沒裝就不假裝量過或施加過限制。

〔第十八批改寫〕tick 與 `task-*` 都在 node 的上限內，任務把記憶體吃滿時 tick 自己也可能被 OOM 殺掉；經 daemon 跑的，這時由 daemon 依 [B-603](../settled/deferred/daemon/lifecycle.md)／[B-605](../settled/deferred/daemon/cgroup.md) 收尾 `tick` 與所有 `task-*`；沒被收掉的舊 `task-*` 由 daemon 格後與重啟時收（[B-601](../settled/deferred/daemon/runtime.md)、[B-603](../settled/deferred/daemon/lifecycle.md)）。daemon 與 helper 在成員額度之外，所以成員耗盡資源仍能收尾；容量與結果保存失敗見[儲存](storage.md)。

**驗收：**已裝 memory／pids module 分別耗盡一次，另測程式不存在；失敗原因可分辨，收尾仍能完成，不自動重試；任務吃滿 node 記憶體、tick 被 OOM 殺掉後，daemon 仍能把 `tick` 與 `task-*` 清空。未裝 module 的部署不要求通過該資源 probe。
