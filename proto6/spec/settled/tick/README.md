# 通用 tick：hooks、tick 模組與普通程式

← [通用 tick 核心](../tick.md)｜[整理區](../README.md)

2026-10-01 把 [tick.md](../tick.md) 拆成兩層：已實作的核心（B-626、B-602、B-620、B-633、B-627）留在 tick.md；範本與各系統級任務、普通程式移到這裡，一篇一個主題。條號不變。同日加外掛掛點（hooks.md，B-635）。tick 這層（含各子篇）講的是**工作資料夾**（`aos-tick` 這一格的 cwd），原本寫 node 的地方 2026-10-01 已改；暫緩區講上下層的「上層 node／下層 node」與舊 RPC 名稱（`node.take`、`node.send`…）照舊〔使用者 2026-10-01〕。

**閱讀順序**：先讀 [tick.md](../tick.md) 的核心；再讀 [template.md](../deferred/template.md) 看範本把各系統級任務排成什麼順序；之後照需要讀各篇，git 那篇最長，放最後。

| 篇 | 條號 | 狀態 |
|---|---|---|
| [tasks-blocked.md](tasks-blocked.md) | B-636 | **已實作**（2026-10-01 第十六批）。tick 模組 `modules["tasks-blocked"]`：某一項之前發現 tasks-blocked 時先跑一串 inst、跑完再看一次，檔被刪就放行；碼不記。 |
| [hooks.md](hooks.md) | B-635 | **已實作**（2026-10-01）。外掛掛點：任務表頂層鍵 `hooks`（跟 `tasks` 同層，不是模組），四個掛點 `before_all`、`after_task`、`after_every_task`（第十七批）、`after_all`，碼記進紀錄 `hooks.<掛點>`。 |
| [暫緩區 template.md](../deferred/template.md) | B-629 | **暫緩**〔使用者 2026-10-01 第十八批〕。範本裡的系統級任務全部搬暫緩區，範本只剩使用者任務、現在沒有系統級任務要放；原檔整篇搬到暫緩區。 |
| [暫緩區 B-621](../deferred/tick/03-B-624與B-621.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task) | B-621 | **暫緩**〔使用者 2026-10-01 第十六批〕。普通程式 `aos-tick-check-task`（2026-10-01 由 `aos-needs` 改寫），從沒寫過程式；原檔 `check-task.md` 整篇搬到 tick 暫緩區。 |
| [暫緩區 cg.md](../deferred/cg.md) | B-631、B-634 | **暫緩**〔使用者 2026-10-02 第二十三批：「aos-cg搬進暫緩區。」〕。普通程式 `aos-cg` 從沒寫過程式，每項一框現在由 daemon 收屍模組做（[B-644](../daemon/cgroup.md)）；原檔整篇搬到暫緩區。 |
| [暫緩區 mq.md](../deferred/mq.md) | B-623、B-624 | **暫緩**〔使用者 2026-10-01 第十八批〕。系統級任務 `aos-mq get`／`post` 要靠暫緩區的 daemon 通道，用途已被 daemon 訊息模組（[B-645](../daemon/mq.md)，`aos-mq send`／`take`）取代；原檔整篇搬到暫緩區。 |
| [暫緩區 git.md](../deferred/git.md) | B-630、B-622、B-632 | **暫緩**〔使用者 2026-10-01 第十七批〕。`aos-git` 三項從沒寫過程式；整篇搬到暫緩區，改用 hooks 加普通 git 指令（[B-635 範例](hooks/03-B-635-範例hook加git.md#範例用-hook-加普通-git-指令管版本)）。 |
| [recovery.md](../deferred/tick/05-B-625-當機恢復設定與清理.md) | B-625 | 待實作。恢復前驗證的工具還沒有程式（`aos-config-add` 2026-10-01 搬到[暫緩區](../deferred/tick/02-B-633落盤與B-625.md#暫緩b-625-加入普通設定aos-config-add)）；暫停與恢復現行用 `aos-ctl`（[B-641](../daemon/control.md)），舊 daemon 的 `node.pause`／`node.resume` 那套在暫緩區。 |
