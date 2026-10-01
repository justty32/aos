# 通用 tick：系統級任務與普通程式

← [通用 tick 核心](../tick.md)｜[整理區](../README.md)

2026-10-01 把 [tick.md](../tick.md) 拆成兩層：已實作的核心（B-626、B-602、B-620、B-633、B-627）留在 tick.md；範本與各系統級任務、普通程式移到這裡，一篇一個主題。條號不變。tick 這層（含各子篇）講的是**工作資料夾**（`aos-tick` 這一格的 cwd），原本寫 node 的地方 2026-10-01 已改；暫緩區講上下層的「上層 node／下層 node」與舊 RPC 名稱（`node.take`、`node.send`…）照舊〔使用者 2026-10-01〕。

**閱讀順序**：先讀 [tick.md](../tick.md) 的核心；再讀 [template.md](template.md) 看範本把各系統級任務排成什麼順序；之後照需要讀各篇，git 那篇最長，放最後。

| 篇 | 條號 | 狀態 |
|---|---|---|
| [template.md](template.md) | B-629 | 待實作。範本裡的系統級任務（`aos-mq`、`aos-git`、`aos-clean`）都還沒有程式（`aos-publish` 2026-10-01 搬暫緩區、從範本拿掉）；`mq-get`／`mq-post` 要靠暫緩區的 daemon 通道。 |
| [check-task.md](check-task.md) | B-621 | 待實作。普通程式 `aos-tick-check-task`（2026-10-01 由 `aos-needs` 改寫），不依賴暫緩區。 |
| [cg.md](cg.md) | B-631、B-634 | 待實作。普通程式；工作資料夾的框與資源上限（daemon 那側）在暫緩區。 |
| [mq.md](mq.md) | B-623、B-624 | 待實作，依賴暫緩。`aos-mq` 要靠暫緩區的 daemon 通道；發摘要 `aos-publish` 2026-10-01 搬到[暫緩區](../deferred/tick.md#暫緩b-624-發布摘要aos-publish)。 |
| [git.md](git.md) | B-630、B-622、B-632 | 待實作。`aos-git` 三項還沒有程式。主體不依賴暫緩區；只有「在不在 tick 內」的核對（要等「鎖 fd 傳給任務」）與巢狀排除的判準（要等上下層判定）在暫緩區。 |
| [recovery.md](recovery.md) | B-625 | 待實作。恢復前驗證的工具還沒有程式（`aos-config-add` 2026-10-01 搬到[暫緩區](../deferred/tick.md#暫緩b-625-加入普通設定aos-config-add)）；暫停與恢復現行用 `aos-ctl`（[B-641](../daemon/control.md)），舊 daemon 的 `node.pause`／`node.resume` 那套在暫緩區。 |
