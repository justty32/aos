# proto6 規格草案

← [proto6](../README.md)｜[架構方向](../notes/2026-09-29-kernel-tree.md)｜[使用者裁定](../notes/verdicts/README.md)

2026-09-29 重寫，2026-09-30 依第十八、十九、二十批改寫。**node 是資料夾；kernel 與 agent 是它可兼任的角色。** node 靠定期被執行的 tick 推進，tick 也是整個 aos 的衡量基準；daemon 是定期跑 tick 的標準程式，不是 tick 存在的前提。狀態留在各 node 的檔案。〔使用者方向 2026-09-30，納入 cgroup 與 git〕git（提交與恢復）與 cgroup 是「有就用」，不是前提（[整理區](settled/README.md)）。這是設計草案，不是已完成的產品。

## 定位：給特殊計算用的 OS

〔使用者方向 2026-09-30，第十八批〕

- **分配單位是一次計算**：一般 OS 分配的是 CPU 指令，aos 分配的是 LLM 呼叫、agent 的一輪任務這類計算；計算要能被 Linux 管制，外部計算當外部函式庫管（[T-06](terms.md)）。
- **多層、多個 kernel**，各 kernel 自訂抽象、資源與隔離，aos 正式開放 kernel 登記自己的任務種類與資源名稱；上下層定義不同時不必對齊（[T-06](terms.md)）。
- **Linux 是基底**：CPU、磁碟交給 Linux kernel；cgroup 與使用者帳號是隔離的基礎。〔使用者方向 2026-09-30，第二十批〕切換帳號〔2026-10-01 第十三批〕現行只在 daemon 設定檔做（帳號模組）；任務自己包 `aos-as` 經 helper 開程序的做法暫緩（[T-10](settled/terms.md)、[B-301](base/identity-resources.md)）；daemon 以 runner 收尾；有 cgroup 時另用 daemon 的 node 框與上限、普通程式 `aos-cg` 的每項一框（[B-605](settled/deferred/daemon/cgroup.md)、[B-634](settled/deferred/cg.md)）。
- 〔使用者方向 2026-09-30，第二十批〕**tick 是衡量基準**：排程以格計（「這個任務要花十個 tick」，算安排它的上層的格），排程本身也是掛在任務表上、每格跑一次的程式；反應最快是下一格。除了 tick–daemon 通道，其他所有事都要在某一格裡做，不准有常駐服務繞過 tick（[T-07](settled/terms.md)）。
- 〔使用者方向 2026-09-30，第二十批〕**tick 核心只做四件事**：同資料夾互斥、照任務表依序跑、上下層判定、每項結束碼紀錄（[T-07](settled/terms.md)）。系統訊息佇列 `aos-mq get`／`post`、發摘要、清理、git 開格／存檔點／收尾 `aos-git` 都是掛在任務表上、`kind:"system"` 標記的**系統級任務**，標準任務表範本就是預設的一組；`aos-as`、`aos-needs`、`aos-cg` 這類包裝是**普通程式**〔2026-10-01：`aos-needs` 改寫成自己占一項的 `aos-tick-check-task`（[B-621](settled/deferred/tick/03-B-624與B-621.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）；發摘要 `aos-publish` 搬[暫緩區](settled/deferred/tick/03-B-624與B-621.md#暫緩b-624-發布摘要aos-publish)〕；任務要停掉本格剩下的項就建停格檔，要擋住之後的格就建擋板檔；其餘是 kernel、agent、clock、自訂任務（[T-10](settled/terms.md)）。**投件權就是執行權，而且會傳遞**（[T-08](terms.md)）。 〔2026-10-01 殘留註記〕現況：tick 核心是簡單互斥鎖、照表跑、每項結束碼紀錄（上下層判定暫緩）；**現行沒有系統級任務**——`aos-mq get`／`post`、清理 `aos-clean`、標準範本（第十八批）、`aos-git`（第十七批）、`aos-tick-check-task`／`aos-needs`（第十六批）、`aos-as`（第十三批）都在[暫緩區](settled/deferred/README.md)；外掛改用 hooks（`before_all`、`after_task`、`after_every_task`、`after_all`，[B-635](settled/tick/hooks.md)）與 tasks-blocked（[B-636](settled/tick/tasks-blocked.md)）。
- **管轄區就是 tick 的 cwd**：上層預設看資料夾包含，在 daemon 底下可登記覆蓋（[T-10](settled/terms.md)）。
- 管理目標之一是降低隨機性，怎麼量延後（[P-008](protocol/readme/03-P-007-P-008-schema與待決.md#p-008)）。

## 閱讀順序

1. **[整理區](settled/README.md)：tick 與 daemon 的基礎**（本輪已定案、整理好的部分）。依序讀：[整理區名詞](settled/terms.md)（T-07、T-09、T-10）→ [通用 tick](settled/tick.md) → [daemon](settled/daemon/README.md) → [helper 與 aos-as](settled/deferred/helper.md)，格式看整理區裡的 node 與 daemon 協議。
2. [名詞與責任](terms.md)：來源標記、node、角色、兩張註冊表與工作識別；定位與投件權（T-01～T-06、T-08）。
3. [kernel 與資源](scheduling/README.md)：樹上分配、資源 module、LLM 池及待處理事項。
4. [基底](base/README.md) → [inst 第 1 版](base/inst.md)：執行身分、工作材料、runner 與檔案交接。
5. [agent 任務](agent/README.md)：設定、內容、context、工具選擇與完成證據。
6. [共用契約](contracts.md)與[驗收入口](conformance.md)：跨篇最少定義及整合故障場景。
7. [人手操作 CLI](cli.md)：用途分層的指令、底層對應、待補接口與完整操作走查。

**整理區是什麼**：`settled/` 放已定案、整理好的 tick 與 daemon 基礎（git 與 cgroup 有就用），要能自己讀懂；它對區外的依賴列在[整理區 README](settled/README.md)。其他篇（kernel、LLM、agent、CLI、基底其餘各篇、協議篇其餘各檔等）還沒跟上新基礎，**之後整理好才一起放進整理區**；在那之前，它們可能還留著舊說法，碰到不一致照 [T-01](terms.md) 的裁定優先序判斷，並記成疑點。

[協議篇](protocol/README.md)只定新 node 架構的欄位、JSON、schema、範例、argv 與結束碼；行為一律以主規格為正本。目錄名 `agent/`、`scheduling/` 依領域保留，不代表兩種 node。

## 分檔目錄

> 2026-10-02 整理：原檔約 10 KB 超過 8 KB 門檻，按標題逐字拆進 `readme/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-來源原則平台與交付.md](readme/01-來源原則平台與交付.md) | 來源與正本；原則：能下指令、能管檔案，就能交給 agent；平台：原生 Linux 與 WSL；交付邊界 |
