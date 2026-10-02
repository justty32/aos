# 標準任務表範本

← [通用 tick 核心](../tick.md)｜[tick 子篇入口](../tick/README.md)｜格式：[tick 協議](../protocol/tick.md)

> **這篇整篇在暫緩區**（2026-10-01 第十八批）〔使用者 2026-10-01 第十八批：「1. 都按你建議 2.好 3.對，我就不想了。」〕範本裡的系統級任務 `aos-mq get`、`aos-mq post`、`aos-clean` 都搬暫緩區（`aos-git` 與有 git 版第十七批已搬），範本只剩使用者任務，**現在沒有系統級任務要放**，B-629 整條暫緩。原檔 `tick/template.md` 整篇搬來，原文照留、條號保留不重用；第十七批搬到 tick 暫緩區的「有 git 版範本」併到本篇末。現行任務表就是使用者自己寫的 `tasks`（[B-620](../tick.md)），要在格的前後做事用 hooks（[B-635](../tick/hooks.md)）。

**狀態：待實作。範本裡的系統級任務（`aos-mq`、`aos-clean`）都還沒有程式（`aos-git` 與有 git 版範本第十七批搬暫緩區）（發摘要 `aos-publish` 2026-10-01 搬暫緩區、從範本拿掉）；`mq-get`／`mq-post` 要靠暫緩區的 daemon 通道。**條號不變，2026-10-01 從 [tick.md](../tick.md) 拆出。

## B-629：標準任務表範本

**標準任務表範本**＝預設的一組系統級任務，加上原本的 kernel／agent 任務。分兩版：

| 版 | 順序 |
|---|---|
| 沒有 git | `mq-get` → 使用者任務 → `mq-post` → 清理 |

〔使用者 2026-10-01 第十七批〕「git這塊先不要進範本。」原本的「有 git 版」（git 開格 → `mq-get` → 存檔點 → 使用者任務 → 存檔點 → 清理 → git 收尾 → `mq-post`）隨 `aos-git` 搬到[暫緩區](template.md#暫緩b-629-有-git-版範本)；範本只留沒有 git 的這份。要用 git，見 [B-635 的範例](../tick/hooks/03-B-635-範例hook加git.md#範例用-hook-加普通-git-指令管版本)。

〔使用者 2026-10-01 第五批〕原本兩版都有「發摘要」（id `summary`，`aos-publish`），隨 `aos-publish` 搬到[暫緩區](tick/03-B-624與B-621.md#暫緩b-624-發布摘要aos-publish)拿掉。

### 沒有 git 版

〔建議預設，未拍板；`id`〕

| # | `id` | `kind` | argv | 做什麼 | 正本 |
|---|---|---|---|---|---|
| 1 | `mq-get` | system | `aos-mq get` | 用 `node.take` 取出本工作資料夾佇列裡的訊息；取出後怎麼分派 aos 不管 | B-623 |
| … | 使用者任務 | kernel／agent／custom | 各自的程式；要換帳號的拆成 daemon 的另一項（帳號模組；`aos-as` 暫緩），要前置的〔暫緩，第十六批〕原本在它前面加一項 `aos-tick-check-task <前置 id…>`，要每項一框的包 `aos-cg --`。檔案收件、檔案投件也是這裡的普通任務，aos 不管 | 各自 | [B-303](helper.md)、B-621、B-634、B-623、B-624 |
| n-1 | `mq-post` | system | `aos-mq post` | 把 `.aos/mq/post/` 裡的訊息用 `node.send` 送出 | B-624 |
| n | `clean` | system | `aos-clean --config config/clean.json` | 過了保留期的清理 | [B-404](../../base/storage.md) |

### 共通

- **範本只是預設**（[T-10](../terms.md)）：任務表可以拿掉任何一項，拿掉了那一項的保證就沒有。例如沒掛 `mq-get`，佇列裡的訊息就沒人取；沒掛 `mq-post`，要送的訊息就一直留著；（`aos-git` 第十七批暫緩，範本不放。）
- 預設 kernel 範本（[P-814](../../protocol/kernel-tasks.md)）與 agent 範本（[P-715](../../protocol/agent-tasks.md)）都照沒有 git 版的順序：頭一項 `mq-get`，中間是原本的任務，尾兩項 `mq-post`、`clean`（原本還有 `summary`，2026-10-01 隨 `aos-publish` 搬暫緩區拿掉）。〔那兩份範本還沒改，也還沒有有 git 版，見 README 疑點〕
- **不在範本上的**：once 是任務自己呼叫的通道事務（[B-613](daemon/channel.md)）；重啟、格後收尾、排空、helper 歸 daemon（[B-601](daemon/runtime.md)、[B-603～605](daemon/README.md)、[B-609](daemon/helper-actions.md)；daemon 那側在暫緩區）。
- **通道**：daemon 開 tick 時給的通道（環境變數、憑證、事務）以 [B-612～614](daemon/README.md) 為正本（daemon 那側在暫緩區）。任務會繼承這些環境變數，在投件權就是執行權（[T-08](../../terms.md)）之下這是預期行為。沒有通道（不是舊 daemon 開的格；現行 daemon 跑的格也沒有通道〔astra 報告必修 1〕）只算功能受限：`aos-mq`、`aos-as`、once 用不了，其他照常。

依據：第二十批追答 8、9（推翻第十九批「標準配備：必須全掛、不能拆、跟核心同一支 `aos-tick`」「功能受限不算沒掛」「有備援就算全掛」）；第二十批進行順序、疑點裁定 3、4（存檔點、git 收尾之後才送）；astra 審整理區裁定（系統訊息佇列 `aos-mq` 取代收件與投件，順序照原位置）；aos-git 分工（系統級任務之間夾存檔點，範本自帶）；使用者 2026-10-01 第五批（拿掉發摘要；前置改用 `aos-tick-check-task`）。

**驗收：**沒有 git 版在沒有 git、沒有 cgroup 的機器上照常跑完；拿掉 `mq-post` 後 `.aos/mq/post/` 的訊息不送、其餘照常；拿掉 `mq-get` 後別的 tick 送來的訊息留在 daemon、其餘照常。

## 暫緩：B-629 有 git 版範本

> **暫緩**（2026-10-01 第十七批）〔使用者 2026-10-01 第十七批〕「git這塊先不要進範本。」隨 `aos-git`（[暫緩區 git](git.md)）搬來；範本只留沒有 git 的那份（[B-629](template.md)）。原文照留。

〔使用者方向 2026-09-30，aos-git 分工；`id` 與第二個存檔點的位置：使用者 2026-09-30 同意照暫定〕

| # | `id` | `kind` | argv | 做什麼 | 正本 |
|---|---|---|---|---|---|
| 1 | `git-open` | system | `aos-git open` | 上一格沒正常收尾就還原；打本格第一個存檔點 | B-630 |
| 2 | `mq-get` | system | `aos-mq get` | 同上 | B-623 |
| 3 | `mark-get` | system | `aos-git mark` | 存下 `mq-get` 這一段 | B-630 |
| … | 使用者任務 | kernel／agent／custom | 同上。要自己的存檔點，就在中間加 `aos-git mark` 項，或在程式裡呼叫 | 各自 | B-630 |
| n-3 | `mark-user` | system | `aos-git mark` | 把使用者任務這一段跟清理隔開 | B-630 |
| n-2 | `clean` | system | 同上 | 移到 git 收尾前，讓清理的變動當格提交 | [B-404](../../base/storage.md) |
| n-1 | `git-close` | system | `aos-git close` | 處理最後一段（清理）、提交 | B-630 |
| n | `mq-post` | system | 同上 | 排在提交之後：送的都是已提交的 | B-624 |

- **存檔點各占一項**，不另設包裝寫法（納入 cgroup 與 git 疑-12）。系統級任務之間的存檔點由範本自帶；其他 kind 的任務範本不替它們插，要就自己加（B-630）。
- 〔使用者 2026-09-30 同意照暫定〕使用者給的順序是「使用者任務 → 清理 → 存檔點 → git 收尾」。這裡把第二個存檔點移到清理**之前**：git 收尾本來就會處理最後一段，放在清理前才能讓清理自成一段，被認成「系統級任務動到的檔」（B-630），清理失敗也不會連帶還原使用者任務那段寫的訊息。存檔點總數不變。
