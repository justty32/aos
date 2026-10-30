# 2026-10-30 使用者看現況地圖後的想法：plan 9 式檔案串流、round 的定位、外部 agent 平級、aos-hub 通用化、掛 daemon 的指令、kernel 與 gate 改名

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜相關：[10-28 agent-round](2026-10-28-agent-round.md)（`parts.json` 在 [§ 1 佈局](2026-10-28-agent-round.md#1-佈局)、round 在 [§ 2](2026-10-28-agent-round.md#2-round一輪本身)）、[10-30 agent-lifecycle](2026-10-30-agent-lifecycle.md)、[10-28 hub-kernel](2026-10-28-hub-kernel.md)

規矩見 [thinking/README](README.md)。10-30 早頂層做了一份「aos 現況地圖」網頁給使用者（在他桌面、不在 git），他看完講了下面五點，說「好了我還在看」，接著又回第 4、5 點、再講第 6～9 點，說「剩下的我覺得之後有遇到再說」，再補第 10、11 點。本檔只放原文與已定／開著的標記；頂層的回答之後補成結論。

## 使用者原文（10-30，逐字）

1. 「1.程式之間說話的方式，感覺還有一種，就是純粹的寫檔案、讀檔案，途中可以設置串流，這就是plan 9那種方式。這一塊我們aos好像沒有用到，之後可以考慮。不過這個感覺只能一對一？多對一的話就得用上鎖了。」
   - **開著**（概念，之後考慮；跟 [10-28 medium](2026-10-28-medium.md) 決定 12～14「檔案串流不進標準」的關係待看）。
2. 「2.關於一隻agent長怎樣，其中的agent資料夾中的round那是啥？我原本以為他是一個可用於aos agent的語法糖，也就是開啟aos loop跑fsm，直到fsm停在idle且沒有新訊息的時候，就停掉aos loop。用在其他coding agent上的時候也不用多做啥，就是claude -p就好，他跑完會自己結束(只是說後續可能會有在他跑的期間push新訊息的需求)，喔等等我看到了，他是先前那套pseudo code的顯化...emmm，是可以啦，不過他能否待在aos-loop/fsm的框架下去實現？假如先暫不考慮claude code cli那些外部coding agent的話。」
   - 問題，**頂層已答**（round 現況）；「能否待在 aos-loop／fsm 框架下」**開著**、隊長查中。
3. 「3.關於"腦用claude -p"，這也是可以啦，不過我一直以為claude code cli這類外部agent，它本質上是可以用來代替aos agent的，兩者是平級的關係，但你要把它當成aos agent brain...有點....。然後其中討論的"射後有理"、"訊息queue"等機制，我建議是分成兩塊看與比較，也就是在aos agent體系下這怎麼做、外部agent下怎麼做，然後找出共同點，以aos agent為主，做成通用介面如aos-say/listen。」
   - 方向（外部 agent 與 aos agent 平級、不是腦；射後有理／queue 分兩塊比較再做通用介面）→ **已通知實作隊長 [agent-lifecycle](2026-10-30-agent-lifecycle.md) 實作第 6、9 步暫停**。
4. 「4.然後格與格之間的通訊錄...這是啥？parts.json是啥？」
   - 問題，**頂層已答**（見 [agent-round § 1](2026-10-28-agent-round.md#1-佈局)）→ **已定**，見 [§ 決定（10-30）](#決定10-30)。
5. 「5.aos-hub感覺是個很通用的東西，他不該只拿來管外部coding agent。或許可以改個名字？也就是我們先把一些通用的東西摘出來，然後弄一個aos-eca-hub(aos-extern-coding-agent-hub)，也就是基於通用aos-hub進行擴展，弄出aos-eca-hub...除此之外還有aos-eca XXX這類的指令。」
   - 方向（aos-hub 通用化、拆出 aos-eca-hub／aos-eca 指令）→ 名字**已定**，見 [§ 決定（10-30）](#決定10-30)；怎麼改名開著，實作第 6 步暫停。

最後一句：「...好了我還在看」

接著回（頂層答第 4 點：`parts.json` 是 agent 自己的器官清單、腦看不到；答第 5 點：aos-hub 通用那層（常駐 kernel、add／stop 實例、信箱收題、pause）跟 aos-daemon 信箱模式幾乎重疊，摘出來可能就是 daemon）：

「好，parts我覺得OK。aos-hub既然摘出來就是daemon，那就不做aos-hub，而是aos-eca-hub。aos-hub這個名字保留到以後使用」

再接著講（同一段話，逐字照順序切成 6～9 點）：

6. 「我發現我們得弄一個指令。就是說，我們現在跑aos-exec XXX，等同於把這個proc掛到linux這個原生proc管理器上。假如我們想要掛在daemon上呢？或許是aos-daemon-ctl add XXX這樣，然後會自動識別XXX是否為loop，不是的話就max:1這樣？」
   - 方向**已定**（見 [§ 決定（10-30）](#決定10-30)）；名字與細節是使用者的「或許」，轉給實作隊長代定、可翻案。
7. 「然後關於aos-post/aos-lock，感覺他這個還沒完善，要不要弄一些aos-post/get, aos-lock/unlock？不用的話也OK。」
   - 頂層已答現況（aos-post 已有 `send`／`claim`／`claim-all`／`check`／`finish`／`init`；aos-lock 已有 `acquire`／`release`／`show`）；**開著**、不急。
8. 「aos-ai是啥？aos-gate又是啥？」
   - 問題，**頂層已答**。
9. 「aos-kernel-llm是否可以換成aos-llm-kernel？也就是他是屬於llm這個領域下的kernel功能，和"屬於kernel領域下的llm特種"比起來，我其實更prefer前者，因為以後會有一大堆領域，而kernel作為基底，他就是算...lib？」
   - **已定**，見 [§ 決定（10-30）](#決定10-30)。

最後一句：「剩下的我覺得之後有遇到再說」——使用者看地圖這輪到此。

再接著回（同一段話，逐字；前段「好，我覺得OK。」、後段「然後簡單跟我說說wait user那些」是問題、頂層已答、不記內容）：

「好，我覺得OK。關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。然後aos-gate這個名字不太直觀，換個名字吧。然後簡單跟我說說wait user那些」

10. （接第 6 點）「關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。」
    - **已定**，見 [§ 決定（10-30）](#決定10-30)。
11. 「然後aos-gate這個名字不太直觀，換個名字吧。」
    - **已定要改**，名字是頂層建議，見 [§ 決定（10-30）](#決定10-30)。

## 決定（10-30）

- **第 4 點已定**：`parts.json` 的設計 OK，[10-28 agent-round](2026-10-28-agent-round.md) 決定 16 那套維持。
- **第 5 點已定**：不再叫 aos-hub；**現有的 aos-hub 改名 aos-eca-hub**（extern coding agent hub），通用的那層就是 aos-daemon；**`aos-hub` 這個名字保留到以後用**。
  - **開著**：怎麼改名、哪些跟著改（`AOS_HUB` 環境變數、`aos-say`／`aos-listen` 裡的 hub 用語、`cli_hub` 資料夾名、N-63 實例、hub-kernel／hub-adapter thinking 的名字），交 fable 規劃、連第 3 點一起。
- 第 1、2、3 點狀態不變。
- **第 6 點方向已定**：要一個把 proc 掛到 aos-daemon 的指令（像 `aos-daemon-ctl add XXX`），自動識別 XXX 是不是 loop、不是就包成 `max: 1`。名字與細節由實作隊長代定、可翻案（[agent-lifecycle](2026-10-30-agent-lifecycle.md) 第 7 步 `execs` 的命令列面）。
- **第 9 點已定**：**aos-kernel-llm 改名 aos-llm-kernel**——領域在前、kernel 是基底（像 lib），以後會有很多領域。排在 agent-lifecycle 實作十步之後做。
  - **開著**（頂層推論，非使用者原話）：這等於一條命名慣例「`aos-<領域>-<功能>`」，要不要寫成條文。
- **第 10 點已定**（接第 6 點）：掛到 daemon 的指令靠**環境變數＋argv** 決定用哪個 daemon（daemon home）。變數名、argv 蓋過環境變數等細節交實作隊長照 N-63 代定、可翻案。
- **第 11 點已定要改名**：aos-gate 換名字。名字照頂層建議用 **`aos-llm-send`**（備選 `aos-llm-call`；照 `aos-<領域>-<功能>`、與 aos-llm-kernel 成對），使用者未反對即採用——**頂層建議、代定可翻案**。排在改名那步，跟第 9 點 kernel 改名同一批。
- 第 7 點（aos-post／aos-lock 要不要補 `get`／`unlock`）開著、不急；第 8 點已答。
