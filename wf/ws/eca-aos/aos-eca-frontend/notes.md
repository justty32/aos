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
- **11-22**，部門來源提案的三題（eca-aos 轉來的原話）：「我人還在外面玩，總之先按推薦做」。裁定照推薦：1＝乙現在做、丙以後接；2＝a，不是用 subagent 掛的平鋪在最上層；3＝a，`aide.json` 那條先留（[提案](部門來源-提案-1122.md#要使用者選的題)）。施工線 `aos-eca-frontend-1122-parents-b`。
- **11-22 上午**，對 eca-aos 說（eca-aos 對話紀錄；前半「frontend真的應該大修了」也在 `wf/HANDOFF.md` 11-22 上午那版，commit `c6a3751aa`，現行版已沒有）：「frontend真的應該大修了，這設定檔/名字前綴/規則，這是剛入行的初級軟體工程師才設計的出來的醜陋架構。」他嫌的就是 `proto8/frontend/bin/aos-frontend` 的 `parents()`（約 377～419 行）。

## 做這份工作學到的（給下一個人）

- frontend 存檔就生效（活的全景頁立刻用新檔），改檔要一次寫完整份；只在 `proto8/frontend/` 裡動，超出先問 eca-aos。
- 不對活 daemon 下指令（`aos-agent ctl ls` 也不跑）；要看資料就讀 `proto8/frontend/tests/` 的 fixture。
- 活樹的前端設定在 `~/.aos/view/config.json`（只讀）；裡面的 `parents`、`parent_rules` 兩個鍵 11-22 起程式不再讀，留著無害。
- 頁上的樹（11-22 起）只看兩種紀錄：daemon 的 subagent 紀錄、隊長的 `aide.json`；沒紀錄的平鋪在最上層。測試的 fixture（`VIEW_LS_FIXTURE`）每列可帶 `"subagents": [...]` 來造上下級。
- 施工流程：`git archive` 抄到 `~/.aos/scratch/<線名>/repo`、在那份跑 `install.py`、改那份、跑 `tests/run.sh`（設 `VIEW_TEST_TMP`；要跑 test_phase1 就設 `VIEW_TOOLS`＝抄來的 aos-user 夾，`~/.aos/scratch/top-1121-frontend/tools/` 有一份）；再用 `templates/start-api` 起暫存樹，掛 agent 後以「冒充那隻 agent 的環境」跑 `aos-tools call subagent` 造 subagent，起前端用 18767／18768（避開 8767／8768），最後才用「寫暫存檔再 mv」換進 repo。
- 起前端的 `serve.pid` 若是 setsid 那層，真正的行程 pid 在 serve 印的那行 `pid N`；收尾要殺那個。
- **aos-user 的施工（11-23 代班，逐題留言＋公告）**：`git archive HEAD proto8/frontend | tar -x -C <scratch>` 抄一份就能跑 aos-user 全部測試，不用 `install.py`；跑測試的 bash 腳本先 unset 全部 `AOS_*`、設假的 `AOS_STACK`／`AOS_USER_ZONE`、`TMPDIR` 指到 scratch、PATH 前面放 repo 的 `proto8/bin`（要 `aos-post`、`aos-mailbox`），`python3 -m unittest discover -s tests`。寫回前 `git diff --quiet HEAD -- 檔`、寫回用同目錄暫存檔再 `mv`、`cmp`，然後跑只讀的 `aos-user where`／`ls`／`door`／`announce`（`ls` 沒信退 10、`announce` 沒公告退 10 都正常）；煙霧測試設 `PYTHONDONTWRITEBYTECODE=1`，免得動到 repo 裡的 `__pycache__`。
- 網頁沒有瀏覽器也驗得了一半：`test_zone.py` 的 `test_10_web`／`test_16_web_comment_and_announce` 在行程裡起 `web.make_handler`，用 urllib 帶 cookie＋表單 token 送 POST；頁上的 script 抽出來用 `node --check` 驗語法。畫面長相沒驗過。
- 專區的 `door.json`、`schema/letter.json` 是 `init` 照 `zone.py` 的 `DOOR`／`SCHEMA` 產的，**已有的不蓋**；改了樣板，已建好的專區不會跟上（要不要動真專區的檔，問 eca-aos）。`door.json` 只有 `door --mode` 與 `announce` 會改寫，兩者都是讀整份、改一鍵、原子寫回，其他鍵不動。
- 全景頁（`aos-frontend` 的 `do_answer`）替使用者答題時只送 `id:key`，不知道逐題留言；`answer` 的寫法要相容這種舊寫法。
- 大修盤點 14 項在 [frontend-備妥-1121](../../../../proto8/thinking/2026-11/21/frontend-備妥-1121.md)；部門怎麼認的提案在 [部門來源-提案-1122](部門來源-提案-1122.md)。
