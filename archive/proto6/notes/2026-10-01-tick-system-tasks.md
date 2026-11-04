# 2026-10-01：aos-tick 的系統級任務總整理（給 hooks 慢慢想用）

← [筆記索引](README.md)｜[tick 子篇入口](../spec/tick.md)｜[hooks B-635](../spec/tick/hooks.md)｜[第二段 plan 草稿](../plan/m2-system-tasks.md)｜[第六、七批裁定](verdicts/11-tick-as-unit/11-1001-第六七批.md#2026-10-01-第七批tick-模組的取捨node逾時歷史紀錄)

> **現況（2026-10-01 晚，第十三～十八批之後）**：下面列的**系統級任務全部暫緩**，現行沒有系統級任務、也沒有標準任務表範本——`aos-as`（第十三批）、`aos-tick-check-task`（第十六批）、`aos-git` 三項與有 git 版範本（第十七批）、`aos-mq get`／`post`、`aos-clean`、範本 B-629（第十八批），都在[暫緩區](../spec/deferred/README.md)。tick 這邊的外掛改成：
> - **hooks**（[B-635](../spec/tick/hooks.md)）：`before_all`、`after_task.<id>`、`after_every_task`、`after_all`；跟任務有關的兩個掛點拿得到 `AOS_TASK_EXIT`。B-635 有「hook 加普通 git 指令」取代 `aos-git` 的範例。所有 hooks 跑完才寫 `ended:true`，所以下面說的「hook 跑到一半被殺、紀錄仍是 `ended:true`」那個洞已解決（第十八批）。
> - **tasks-blocked**（[B-636](../spec/tick/tasks-blocked.md)）：停格檔改名 `tick/tasks-blocked`，每項任務之前看、只看存不存在、整格最後由 tick 刪；模組 `modules["tasks-blocked"]`（第十六批原名 `tasks_blocked`，第二十批改名）發現它時先跑一組 insts、跑完檔不在就放行。擋板檔只看存不存在、存在就靜靜回 0（第十六批）。
> - 訊息改由 daemon 訊息模組做（[B-645](../spec/daemon/mq.md)，`aos-mq send`／`take`／`peek`）。
>
> 下面是 10-01 下午整理時的原文，照留。

**這份只是整理，不是裁定。** 使用者 2026-10-01：「把aos-tick的系統性任務，先前有規劃過的，都寫下來，我之後慢慢思考他們要怎麼在hook下實作」。下面把過去規劃過的系統級任務、相關普通程式、範本、已暫緩與已撤回的東西全部列出來，每項附「放到 hooks 下」的觀察。**每項的「hooks 想法」都只是選項，標了「待使用者想」，沒有替使用者決定。**

背景方向（[第七批](verdicts/11-tick-as-unit/11-1001-第六七批.md#2026-10-01-第七批tick-模組的取捨node逾時歷史紀錄)）：tick 模組能用 hooks 做的就用 hooks；node、逾時不做 tick 模組；歷史紀錄不做；停格與 git 先不動。

## 分檔目錄

> 2026-10-02 整理：原檔約 24 KB 超過 8 KB 門檻，按標題逐字拆進 `2026-10-01-tick-system-tasks/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-hooks現況與範本.md](2026-10-01-tick-system-tasks/01-hooks現況與範本.md) | 現在 hooks 能做什麼、限制在哪；怎麼讀每一項；一、標準任務表範本（B-629） |
| 2 | [02-git-mq-clean.md](2026-10-01-tick-system-tasks/02-git-mq-clean.md) | 二、git 三項（B-630、B-622、B-632）；三、系統訊息佇列 aos-mq（B-623、B-624）；四、aos-clean（B-404） |
| 3 | [03-普通程式工具與構想.md](2026-10-01-tick-system-tasks/03-普通程式工具與構想.md) | 五、普通程式（不是系統級任務）；六、在 tick 外的工具；七、已暫緩或只是構想；八、第七批列過的模組候選 |
| 4 | [04-已撤回daemon側與總表.md](2026-10-01-tick-system-tasks/04-已撤回daemon側與總表.md) | 九、已撤回或改名、不會照原樣回來的；十、daemon 那側、本來就不在任務表上的；總表 |
