aos-eca-frontend 的工作筆記：使用者給這份工作的規矩（逐字附日期）、使用者對全景頁／frontend 說過的話，以及做這份工作學到、下一個人該照做的事。

← [我的地盤](README.md)｜[地盤規矩](../../README.md)

## 使用者給這份工作的規矩

（目前沒有使用者直接訂給 aos-eca-frontend 的規矩；職責未定，只做 eca-aos 派來的事。）

- 2026-11-22，使用者剛掛上我時：「再給你自己掛一個aos-eca-frontend，先不用讓他做事」（出處：`wf/HANDOFF.md` 11-22 上午那版，commit `c6a3751aa`）。
- 2026-11-22，eca-aos 轉述：使用者後來同意「小工作室試跑」，所以開始給我小件（第一件是線 `aos-eca-frontend-1122-first`）。這是轉述，不是原話。

## 使用者對全景頁／frontend 說過的話（逐字，附出處）

依時間排。全景頁 11-17 以前叫 aos-view，之後改名 aos-frontend。

- **11-14**，全景的起點（[user-advice/20261114.md](../../../../proto8/thinking/user-advice/20261114.md) 第 7～17 行）：
  - 「讓我掌握全景這塊，我這邊還有個餿主意：就像是管理公司一樣，要讓我這個董事長掌握狀況，所以就是分部門這樣」
  - 「就是說，我們人類使用者，比較擅長3d/2d空間的縮放移動，我可以拉高視角看到各部門，也可以點進去看到各部門內部各員工的狀況(這個比較麻煩，未必一定要做)。」「然後這可以嵌套」
  - 「啊，要看員工狀況，就是用bot模型，他現在處在啥狀態，他過去幹了啥，說了啥。」「對，就是這個意思。普通的proc，或許...也可以看到狀況？」
- **11-14**，新 UI（同檔第 39 行；[view-1114/01c](../../../../proto8/thinking/2026-11/14/view-1114/01c-備料-新UI.md)）：「然後目前的全景已經很好用了。希望能把版本獨立成一套。然後接下來的公司部門那個概念，可以的話需要重新規劃一整套UI，後端邏輯倒是應該還好。」另有「對，就是前端的使用者體驗這塊」「先不用手機」（[view-1114/01d](../../../../proto8/thinking/2026-11/14/view-1114/01d-備料-UX重規劃.md) 第 15 行）。
- **11-14 午**（同檔第 101 行）：「問我的問題你直接放全景網頁，我現在大多在看那邊。」
- **11-15**，意見（[session-log-瘦身留底/05](../../../../proto8/thinking/2026-11/17/session-log-瘦身留底/05-第39到42條.md) 第 12、26 行）：
  - 「我現在都在用aos-view這東西來管理了，啊我沒辦法compact，這太蠢了」
  - 「aos-view我昨天就給了一堆意見，啊結果昨天他一直掛掉，導致現在的aos-view v2仍然難用，之後要去查查看他爲何這麼容易掛掉，並且催促他趕快勤快更新」
  - 「aos-view這個名字我覺得不好，應該換個名字，因爲aos-view以後我覺得會有更重要的功能使用這個名字」
  - 派工時：「不要耦合太深，記住，aos-view之後會改名」
- **11-17 下午**，改名（[proto8/thinking/README.md](../../../../proto8/thinking/README.md) 第 13 行）：「aos-view確實應該是選配的網頁外掛」「那就改名為aos-frontend吧」。
- **11-17**：前端「之後整個大修大重構」（只有轉述，見 `wf/progress.json` 的 `later-1115`，沒找到逐字原文）。
- **11-18**：PATH 多一段 `frontend/bin` 怎麼辦 →「照留，等前端大修 (Recommended)」（[cpp-py-改名/08](../../../../proto8/thinking/2026-11/17/cpp-py-改名/08-要裁的題.md) 第 151 行）。
- **11-18 晚**：「前端的三個小毛病這塊都還好，，先留着。」（`wf/progress.json` 的 `overview-page`；三個小毛病＝起前端要自設 AOS_DAEMON、去 `~/aos-home/ws/tools` 找 aos-user、首頁轉到已刪的 v1 路徑）。同一晚 HANDOFF 記「前端相關先不動」（commit `4bdf62e59`、`eefead8a4`，在頂層轉述的一段話裡）。
- **11-21 15:00**（[frontend-備妥-1121](../../../../proto8/thinking/2026-11/21/frontend-備妥-1121.md) 第 7 行）：「然後aos frontend也幫我準備好，能先動工的就先動工。」
- **11-21 夜**：eca-aos 看到 `run_json` 丟掉子程式的 stderr，使用者「兩個都記下來」（`wf/progress.json` 的 `overview-page`）。
- **11-22 上午**，對 eca-aos 說（eca-aos 對話紀錄；前半「frontend真的應該大修了」也在 `wf/HANDOFF.md` 11-22 上午那版，commit `c6a3751aa`，現行版已沒有）：「frontend真的應該大修了，這設定檔/名字前綴/規則，這是剛入行的初級軟體工程師才設計的出來的醜陋架構。」他嫌的就是 `proto8/frontend/bin/aos-frontend` 的 `parents()`（約 377～419 行）。

## 做這份工作學到的（給下一個人）

- frontend 存檔就生效（活的全景頁立刻用新檔），改檔要一次寫完整份；只在 `proto8/frontend/` 裡動，超出先問 eca-aos。
- 不對活 daemon 下指令（`aos-agent ctl ls` 也不跑）；要看資料就讀 `proto8/frontend/tests/` 的 fixture。
- 活樹的前端設定在 `~/.aos/view/config.json`（只讀）；今天裡面還有 `ok-*`、`xiaosi` → `repo-aos` 兩條規則，`repo-aos` 是舊頂層的名字。
- 大修盤點 14 項在 [frontend-備妥-1121](../../../../proto8/thinking/2026-11/21/frontend-備妥-1121.md)；部門怎麼認的提案在 [部門來源-提案-1122](部門來源-提案-1122.md)。
