# tick 暫緩區：上下層判定與核心先不做的細節

← [暫緩區](README.md)｜[通用 tick（現行）](../tick.md)｜[tick 協議](../protocol/tick.md)｜[慣例](../conventions.md)

**這篇整篇在暫緩區。** 2026-10-01 使用者定 POC「默認一切正常、先不考慮邊緣狀況」，tick 核心縮成三件事：簡單互斥鎖、照表跑、每項結束碼紀錄（[B-626](../tick/core/02-B-626-核心與系統級任務界線.md#b-626核心與系統級任務的界線)）。原本寫在 [tick](../tick.md) 裡、現在先不做的規定搬到這裡，原文照留，條號保留、不重用。現行規定一律看 [tick](../tick.md) 與 [tick 協議](../protocol/tick.md)。

- 整條搬來的：B-628 上下層判定。
- 部分搬來的：B-602、B-620、B-633 各有一段（標題寫成「暫緩：B-xxx …」，原條還在 tick.md）；B-625 的 `aos-config-add` 那段（原條還在 [tick/recovery.md](../tick/recovery.md)）；B-624 的發布摘要 `aos-publish` 那段（原條還在 [tick/mq.md](mq.md)，2026-10-01 第五批）。
- 整條搬來的（2026-10-01 第十六批）：B-621 `aos-tick-check-task`（原檔 `tick/check-task.md` 已刪）。
- 第十七批搬來的 B-629「有 git 版範本」那段，第十八批隨 B-629 整條併到 [template.md](template.md)。
- 協議那側搬來的：P-207 `aos-config-add` 的格式（整條）、P-206 的 `aos-publish` 那列、P-204 `aos-tick-check-task`（整條，第十六批），在 [protocol/tick.md](protocol/tick.md)。
- 篇末「已撤回／被取代」列的是被新設計換掉的舊做法，不是暫緩，以後也不會回來。

原文裡的「node」在 tick 這層讀成「工作資料夾」；`.aos` 是 `AOS_DIRNAME` 沒設時的名字（[C-09](../conventions.md)）；原文的結束碼 75、2、125 等是舊碼表，回來時要照 [C-08](../conventions.md) 重定。

## 分檔目錄

> 2026-10-02 整理：原檔約 26 KB 超過 8 KB 門檻，按標題逐字拆進 `tick/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-628上下層與B-602-B-620細節.md](tick/01-B-628上下層與B-602-B-620細節.md) | B-628：上下層判定：預設看資料夾包含、可登記覆蓋；暫緩：B-602 完整互斥的其餘細節；暫緩：B-620 任務的帳號（125） |
| 2 | [02-B-633落盤與B-625.md](tick/02-B-633落盤與B-625.md) | 暫緩：B-633 落盤、寫不進與讀不懂；暫緩：B-625 加入普通設定（`aos-config-add`） |
| 3 | [03-B-624與B-621.md](tick/03-B-624與B-621.md) | 暫緩：B-624 發布摘要（`aos-publish`）；暫緩：B-621 前面的項沒跑好就停格（`aos-tick-check-task`） |
| 4 | [04-已撤回與被取代.md](tick/04-已撤回與被取代.md) | 已撤回／被取代 |
