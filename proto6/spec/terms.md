# 名詞：tick 核心、四類程式、daemon 核心

← [整理區](README.md)｜[tick](tick.md)｜[daemon](daemon/README.md)｜[慣例](conventions.md)｜其餘名詞：[名詞與責任](../terms.md)｜[暫緩的名詞 T-09](deferred/terms.md)

只講詞義；規則以各篇與程式為準。

## T-07：tick 核心

**tick 是一個定期被執行的程式**（`aos-tick`），誰來跑都行（daemon、cron、人手），本質是加了功能的 `aos-exec`。核心只做三件事：簡單互斥鎖、照表跑、每項結束碼紀錄；其餘（git、cgroup、訊息、清理…）一律是系統級任務或普通程式，核心不靠它們。

- **工作資料夾**：這一格 tick 的 cwd，由命令列目標決定；任務拿到的 `AOS_TICK_CWD` 就是它。「node」一詞留給之後的 node 模組。
- **衡量基準**：整個 aos 以「格」計；反應速度最快是下一格。不准有背景程序繞過 tick。
- **tick 外的寫入者**：在 tick 之外自己取鎖改檔的工具，算外部世界，aos 不管。

## T-10：四類程式

| 類 | 一句話 |
|---|---|
| tick 核心 | `aos-tick` 本身 |
| 系統級任務 | 從核心拆出、掛在任務表上的獨立程式，寫在表上才跑；`kind:"system"` 只是標記，不授權。現行沒有，全在暫緩區 |
| 普通程式 | 任務自己包在 argv 裡的工具（`aos-cg`、`aos-as`…）。現行沒有 |
| 其他任務 | kernel、agent、clock、自訂任務等 |

「管轄區」＝tick 的 cwd；兩個 tick 的管轄區慣例上不重疊但可包含，**這是約定、不是 tick 運作的前提**。daemon 不在任務表上。常用詞：**tasks-blocked**（擋本格後續項的檔）、**擋板檔**（擋之後各格、只由人刪）、**掛點／hooks**、**每項結束碼紀錄**、**格數 `seq`**——都在 [tick.md](tick.md)。

## T-11：daemon 核心與模組

現行 daemon 只是「定期叫 `aos-exec` 的 cron」，其餘功能做成可掛的模組（設定檔頂層 `modules` 底下一個鍵一個，寫了才掛）：

- **daemon 核心**：照設定檔 `insts` 的每一項定期叫 `aos-exec`；不認得工作資料夾、不讀任務表、不碰 tick 的鎖與擋板。一項就是 inst 字面值，沒有 id。
- 模組：`control`（socket 加 `aos-ctl`）、`reload`（SIGHUP 重讀）、`state`（記住暫停）、`cgroup`（收屍）、`mq`（訊息門與信箱）、`account`（用指定帳號開）。各模組見 [daemon/README.md](daemon/README.md)。
- 舊 daemon 的登記、通道、收尾等用語在暫緩區。
