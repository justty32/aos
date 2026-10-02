# 名詞：tick 核心、四類程式、daemon 核心

← [規格](README.md)｜[tick](tick.md)｜[daemon](daemon/README.md)｜[慣例](conventions.md)｜[暫緩的名詞 T-09](deferred/terms.md)

只講詞義；規則以各篇與程式為準。T-01～T-06、T-08 是舊設計留下來、現行程式沒有但方向還算數的幾條，收在文末。

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

## T-01～T-06、T-08：舊名詞，只留還算數的

舊的「名詞與責任」篇（node、kernel、agent、工作識別、萬級冷 node、投件權）整篇封存（[封存](../notes/archive/spec-2026-10-02/terms.md)）；現行程式沒有這些東西，下面只留方向還算數的。

- **T-01 保證跟著「掛了什麼」走**：tick 核心的三件事不靠任何系統級任務也成立；其餘保證來自任務表上掛的任務、任務包的普通程式與 daemon。git、cgroup 是「有就用」，沒有也要照常跑。
- **T-02 「node」不是現行用語**：tick 層叫「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（使用者：「node這塊不要動，我有預感，node相關概念以後會不存在。」）。daemon 的表是設定檔加記憶體（要記住暫停／已停另見 [state 模組](daemon/state.md)），tick 的表是 `tasks.json`，兩張不要混。
- **T-06 aos 是給特殊計算用的 OS**：一般 OS 分配的單位是 CPU 指令，aos 分配的單位是一次「計算」（一次 LLM 呼叫、一輪 agent）；計算必須能被 Linux 啟動、限制、殺掉。上下層可以多層，上層只用自己認得的資源與規則管下層，管理要「潤物細無聲」。現行程式只做到 tick 與 daemon 這一小層；其餘（kernel、資源、排程、隨機性怎麼量）是方向，沒有程式。
- **T-08 能下指令就等於能用那個身分**：能寫某個資料夾的 `tasks.json`、能連某個 socket，就等於能用那個程式的身分跑任意程式，而且會傳遞。所以 aos 不在裡面另外判斷權限，隔離只靠資料夾權限與帳號（見 [daemon 共通原則](daemon/README.md)）。
- T-03（工作識別碼）、T-04（已刪）、T-05（萬級冷 node）只屬舊設計，不留。
