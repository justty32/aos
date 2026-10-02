← [2026-10-01：aos-tick 的系統級任務總整理（給 hooks 慢慢想用）](../2026-10-01-tick-system-tasks.md)（分檔 2/4）｜[上一份](01-hooks現況與範本.md)｜[下一份](03-普通程式工具與構想.md)

## 二、git 三項（B-630、B-622、B-632）

使用者 10-01：「git也先不動」。plan 待問 1～8 都還在想。共通前提：[git.md](../../spec/deferred/git.md)、格式 P-205。

### aos-git open（`git-open`）

- **做什麼**：上一格沒正常收尾（`last/` 是 `ended:false` 或有 `stopped_after`）就把 aos 範圍還原到 HEAD；清掉殘留的 `refs/aos/marks/*`；打本格第一個存檔點。
- **原本位置**：有 git 版第 1 項。
- **機制**：讀上一格紀錄；「在不在 tick 內」靠繼承的鎖 fd；故障時寫擋板＋停格檔。
- **狀態**：待實作（[B-630](../../spec/deferred/git.md)）。
- **前提不在了**：鎖 fd 不傳給任務（`not_in_tick` 判不了）；`kind` 回查、巢狀排除（上下層判定 B-628 暫緩）都沒依據；紀錄只記非 0，存檔點命名、組的判法 plan 已改照 `index`。
- **hooks 想法（待使用者想）**：
  - 留在 `tasks` 第一項：最單純，沒什麼不行。
  - 等開 `before_all`：使用者不會忘了排、也不會被誤排到中間。
  - **注意**：如果 close 搬進 `after_all`（下面），「上一格有 `stopped_after`」這種情況可能在當格就處理掉，open 只剩管當機（`ended:false`）。~~但 hook 跑到一半被殺時紀錄仍是 `ended:true`，open 會看不出來——這是 hooks 現行紀錄設計的洞。~~ 〔第十八批已解決：hooks 跑完才收尾〕

### aos-git mark（`mark-get`、`mark-user`、使用者自己加的存檔點）

- **做什麼**：打存檔點；剛結束那組有失敗，就把那組改的 aos 範圍還原到往前最近的存檔點再打點。`mark <路徑…>` 可把使用者的檔加進 aos 範圍。
- **原本位置**：有 git 版的 `mark-get`（`mq-get` 之後，把取件那段隔開）、`mark-user`（使用者任務之後、`clean` 之前）；使用者任務要存檔就自己插一項。存檔點各占一項，不做包裝寫法（疑-12）。
- **機制**：讀本格紀錄判斷「組」有沒有失敗（現在照 `index`）；ref 名原用 `AOS_TASK_ID`，plan 建議改 `AOS_TASK_INDEX`。
- **狀態**：待實作（[B-630](../../spec/deferred/git.md)）；`mark <路徑…>` plan 建議先不做（待問 3）。
- **前提不在了**：「兩個存檔點之間全是 `kind:"system"` 就整段算 aos 範圍」要回查 `kind`，plan 建議拿掉（待問 1）；`id` 可重複、可省。
- **hooks 想法（待使用者想）**：
  - 留在 `tasks` 當一般項：它本來就是「夾在兩項之間」，`after_all` 做不到。
  - 等開 `after_task`：每項後自動打點＝每項自成一組，使用者不用自己插；代價是每項都掃一遍 aos 範圍（成本）、組變細。
  - `mark-get` 只在有 `mq-get` 時才需要；`mq-get` 如果搬去 `before_all`，`mark-get` 可能跟著併進去。
  - 若 hook 也要打點，ref 名不能只用 `AOS_TASK_INDEX`（會跟任務撞號），要加前綴之類。（第十批後 hook 沒有 `AOS_TASK_INDEX`，改用 `AOS_HOOK_POINT`＋`AOS_HOOK_INDEX`。）

### aos-git close（`git-close`）

- **做什麼**：處理最後一組（失敗就還原）、把 aos 範圍剩下的改動提交一次（`aos-tick <seq>`）、刪本格存檔點。
- **原本位置**：有 git 版倒數第二，`clean` 之後、`mq-post` 之前。
- **機制**：**被停格擋住是刻意的**——停格＝這格作廢，close 不跑、不提交，交給下一格 open 還原。close 失敗建停格檔，保住「先提交再送」。
- **狀態**：待實作（[B-630](../../spec/deferred/git.md)）；故障處理 plan 建議只回 1（待問 5）。
- **前提不在了**：同 open；故障寫擋板＋停格檔 plan 建議拿掉。
- **hooks 想法（待使用者想）**：
  - 留在 `tasks` 倒數：照原設計，停格自然不跑。
  - 搬進 `after_all`：停格也會跑，得自己讀 `stopped_after`，再選「停格就不提交（照舊作廢）」或「停格也提交前面成功的組」——後者會改掉「停格＝整格作廢」的語意。
  - 搬進 `after_all` 後，close 失敗**擋不住**後面的 hook（例如 `mq-post`），「先提交再送」要改由 `mq-post` 自己核對。

## 三、系統訊息佇列 aos-mq（B-623、B-624）

兩項都要暫緩區的 daemon 通道（B-612、B-614）；現行 daemon 沒有通道，跑了也只是 `no_channel`、回 0。plan 排在第四段。

### aos-mq get（`mq-get`）

- **做什麼**：用 `node.take` 把本工作資料夾佇列裡的請求與回應取到空；取出後怎麼分派 aos 不管。每個工作資料夾只有它取。
- **原本位置**：沒有 git 版第 1 項；有 git 版第 2 項（`git-open` 之後）。
- **機制**：通道、本格憑證；「在不在 tick 內」靠鎖 fd，不在就自己取鎖、拿不到回 75。
- **狀態**：待實作、依賴暫緩（[B-623](../../spec/deferred/mq.md)、P-206）。
- **前提不在了**：通道、憑證、鎖 fd、75 碼（C-08 後要重定）。
- **hooks 想法（待使用者想）**：「每格開頭」的事，適合 `before_all`（還沒開）；在那之前只能是 `tasks` 第一項。`after_all` 不合適（取了要給這格的任務用）。訊息模組本身可能整個改成 daemon 模組，到時候再看。

### aos-mq post（`mq-post`）

- **做什麼**：把 `.aos/mq/post/` 裡的訊息用 `node.send` 一件件送出；送不了的搬到 `.aos/mq/failed/`（下一格開送前清掉）。
- **原本位置**：沒有 git 版倒數第二；有 git 版最後（`git-close` 之後）。
- **機制**：排在使用者任務之後，「前面都跑完才送」「停格就不送」「有 git 時只送已提交的」全靠順序與停格檔。
- **狀態**：待實作、依賴暫緩（[B-624](../../spec/deferred/mq.md)、P-206）。
- **前提不在了**：同 `mq-get`。
- **hooks 想法（待使用者想）**：「每格收尾」很像 `after_all`；但 `after_all` 停格也跑，要保住「停格不送」得自己讀 `stopped_after`。跟 close 都放 `after_all` 時，陣列順序 close → post 照樣排得出來，只是 close 失敗擋不住 post。也可以乾脆留在 `tasks` 尾巴。

## 四、aos-clean（B-404）

- **做什麼**：過了保留期（以格數計，`retention_ticks`）的資料封存或刪除；自己記上次清理是第幾格，間隔 `interval_ticks` 未到就回 0。只清自己認得的（agent／kernel 任務產生的）。
- **原本位置**：沒有 git 版最後；有 git 版移到 `git-close` 前、自成一段（讓清理的變動當格提交）。舊 kernel 範本裡是 `custom` 類、排最後。
- **機制**：`kind:"system"`；在 tick 內靠鎖 fd、有 git 交給 close 提交；直接跑時自己取鎖、自己 commit。
- **狀態**：待實作（[B-404](../archive/spec-2026-10-02/base/storage.md)、[P-605](../archive/spec-2026-10-02/protocol/ops.md)）；plan 待問 9 建議第二段不做（POC 沒有它認得的資料）。
- **前提不在了**：沒有 kernel、agent 任務可清；鎖 fd；`state/ops/clean.json` 不在新的 aos 範圍。
- **hooks 想法（待使用者想）**：跟這格任務成敗無關、停格也可以清，很像 `after_all`。但有 git 時它原本要排在 close 前「當格提交」——兩個都在 `after_all` 就排 clean → close；close 留在 `tasks` 的話 clean 在 `after_all` 會變成下一格才提交。也可能根本不屬於 tick，交給使用者自己掛一項。
