# 2026-10-30 使用者看現況地圖後的想法：plan 9 式檔案串流、round 的定位、外部 agent 平級、aos-hub 通用化

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜相關：[10-28 agent-round](2026-10-28-agent-round.md)（`parts.json` 在 [§ 1 佈局](2026-10-28-agent-round.md#1-佈局)、round 在 [§ 2](2026-10-28-agent-round.md#2-round一輪本身)）、[10-30 agent-lifecycle](2026-10-30-agent-lifecycle.md)、[10-28 hub-kernel](2026-10-28-hub-kernel.md)

規矩見 [thinking/README](README.md)。10-30 早頂層做了一份「aos 現況地圖」網頁給使用者（在他桌面、不在 git），他看完講了下面五點，最後說「好了我還在看」——之後還會再講，接著補進本檔。本檔只放原文與已定／開著的標記；頂層的回答之後補成結論。

## 使用者原文（10-30，逐字）

1. 「1.程式之間說話的方式，感覺還有一種，就是純粹的寫檔案、讀檔案，途中可以設置串流，這就是plan 9那種方式。這一塊我們aos好像沒有用到，之後可以考慮。不過這個感覺只能一對一？多對一的話就得用上鎖了。」
   - **開著**（概念，之後考慮；跟 [10-28 medium](2026-10-28-medium.md) 決定 12～14「檔案串流不進標準」的關係待看）。
2. 「2.關於一隻agent長怎樣，其中的agent資料夾中的round那是啥？我原本以為他是一個可用於aos agent的語法糖，也就是開啟aos loop跑fsm，直到fsm停在idle且沒有新訊息的時候，就停掉aos loop。用在其他coding agent上的時候也不用多做啥，就是claude -p就好，他跑完會自己結束(只是說後續可能會有在他跑的期間push新訊息的需求)，喔等等我看到了，他是先前那套pseudo code的顯化...emmm，是可以啦，不過他能否待在aos-loop/fsm的框架下去實現？假如先暫不考慮claude code cli那些外部coding agent的話。」
   - 問題，**頂層已答**（round 現況）；「能否待在 aos-loop／fsm 框架下」**開著**、隊長查中。
3. 「3.關於"腦用claude -p"，這也是可以啦，不過我一直以為claude code cli這類外部agent，它本質上是可以用來代替aos agent的，兩者是平級的關係，但你要把它當成aos agent brain...有點....。然後其中討論的"射後有理"、"訊息queue"等機制，我建議是分成兩塊看與比較，也就是在aos agent體系下這怎麼做、外部agent下怎麼做，然後找出共同點，以aos agent為主，做成通用介面如aos-say/listen。」
   - 方向（外部 agent 與 aos agent 平級、不是腦；射後有理／queue 分兩塊比較再做通用介面）→ **已通知實作隊長 [agent-lifecycle](2026-10-30-agent-lifecycle.md) 實作第 6、9 步暫停**。
4. 「4.然後格與格之間的通訊錄...這是啥？parts.json是啥？」
   - 問題，**頂層已答**（見 [agent-round § 1](2026-10-28-agent-round.md#1-佈局)）。
5. 「5.aos-hub感覺是個很通用的東西，他不該只拿來管外部coding agent。或許可以改個名字？也就是我們先把一些通用的東西摘出來，然後弄一個aos-eca-hub(aos-extern-coding-agent-hub)，也就是基於通用aos-hub進行擴展，弄出aos-eca-hub...除此之外還有aos-eca XXX這類的指令。」
   - 方向（aos-hub 通用化、拆出 aos-eca-hub／aos-eca 指令）**開著**；實作第 6 步暫停。

最後一句：「...好了我還在看」
