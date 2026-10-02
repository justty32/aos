# 整理區：tick 與 daemon 的基礎

← [規格入口](../README.md)｜[第二十批裁定](../../notes/verdicts/11-tick-as-unit.md)｜[現行程式](../../src/py/README.md)

## 這是什麼

整理區（`settled/`）放**已經定案、整理好的 tick 與 daemon 基礎**，跟 kernel、agent、LLM、CLI 等其他篇分開。〔使用者方向 2026-09-30，第二十批「整理區」〕

**2026-10-01 統一更新**：整理區改成跟現行 Python POC（[proto6/src/py](../../src/py/README.md)）與當天的裁定一致，分成兩塊：

- **正式篇**：現在就照著做的規定。tick 核心縮成三件事（簡單互斥鎖、照表跑、每項結束碼紀錄）；daemon 縮成「定期叫 `aos-exec` 的 cron」加一個可掛的控制模組；另開一篇通用慣例（結束碼、狀態資料夾名、環境變數）。
- **[暫緩區](deferred/README.md)**：已經想好、但現在先不做的規定（完整互斥、上下層判定、任務帳號 125、落盤與紀錄失效、整套舊 daemon、helper、cgroup、訊息）。原文照留、條號保留不重用，每條標「暫緩」或「已被 X 取代」。

其他原則照舊：

- **條號不變、不重用。** 搬家只換檔案位置；新規定開新號。
- **主規格是行為正本，協議篇只留格式**（方案 A，[V-01](../conformance.md)）：`tick.md`、`daemon/` 寫行為；`protocol/` 底下只寫欄位、JSON、argv、結束碼。
- **git 與 cgroup 是「有就用」，不是前提**（git：[B-630、B-622](deferred/git.md)；cgroup：現行是 daemon 收屍模組 [B-644](daemon/cgroup.md)；`aos-cg` [B-634](deferred/cg.md) 第二十三批搬暫緩區，舊 daemon 那側也在暫緩區）。提交與還原只限 aos 自己的東西，使用者任務改的檔 aos 不管。
- **hooks 與 tick 模組**（[hooks](tick/hooks.md)、[tasks-blocked](tick/tasks-blocked.md)）放在正式篇的 [tick/ 子篇](tick/README.md)；系統級任務**全部在暫緩區**（`aos-publish` 2026-10-01、`aos-tick-check-task` 第十六批、`aos-git` 第十七批、`aos-mq get`／`post`、`aos-clean` 與範本第十八批；普通程式 `aos-cg` 第二十三批）：它們是之後幾段要做的獨立程式，規定沒被推翻；每篇開頭一行標狀態（已實作／待實作／依賴暫緩），用到暫緩區東西的地方各條有註明。〔使用者 2026-10-01；astra 報告建議 1〕
- **要能自己讀懂**：區內各篇互相連結；對區外的依賴列在下面「對外依賴」。
- **其他篇之後才放進來**：kernel、LLM、agent、CLI、基底其餘各篇，等它們跟上新基礎再放入。

## 閱讀順序

1. [通用慣例](conventions.md)（C-08 結束碼、C-09 `AOS_DIRNAME`、C-10 環境變數總表、C-11 設定檔頂層 `cwd` 與指示詞展開範圍）：aos 每支程式都守的規矩，最短，先讀。
2. [名詞](terms.md)（T-07 tick 核心、T-10 四類程式、T-11 daemon 核心與模組）：先知道「核心、系統級任務、普通程式、tasks-blocked（原停格檔）、擋板檔、模組」這些詞。
3. [通用 tick 核心](tick.md)：核心三件事（B-626、B-602、B-620、B-633）與直接跑（B-627）→ [tick/ 子篇](tick/README.md)：hooks、tick 模組 `tasks-blocked`、當機恢復，每篇開頭標狀態（範本、佇列的取與送、git、`aos-cg` 都在暫緩區）。〔使用者 2026-10-01 拆篇〕
4. [daemon](daemon/README.md)：[B-640 最核心 daemon](daemon/core.md) → [B-641 控制模組與 `aos-ctl`](daemon/control.md) → [B-642 重讀設定](daemon/reload.md)、[B-643 記住狀態](daemon/state.md)、[B-644 收屍／cgroup](daemon/cgroup.md)、[B-645 訊息與 `aos-mq`](daemon/mq.md)、[B-646 帳號](daemon/account.md)。
5. 要看格式時：[tick 協議](protocol/tick.md)（P-200～214：工作資料夾布局、任務表、`aos-tick` 與各系統級任務的 argv 與結束碼；原 `protocol/node.md`，2026-10-01 改名）→ [daemon 協議](protocol/daemon/README.md)（P-120 設定檔與輸出、P-121 控制 socket 與 `aos-ctl`）。
6. 想知道「以後還會有什麼」：[暫緩區](deferred/README.md)。

## 檔案清單

| 檔 | 條號 | 說明 |
|---|---|---|
| [README.md](README.md) | — | 本篇 |
| [conventions.md](conventions.md) | C-08、C-09、C-10、C-11 | 2026-10-01 新開；C-11 是第二批新開 |
| [terms.md](terms.md) | T-07、T-10、T-11 | 從 [名詞與責任](../terms.md) 拆出；T-11 是 2026-10-01 新開；T-09 搬到暫緩區 |
| [tick.md](tick.md) | B-626、B-602、B-620、B-633、B-627 | tick 核心（已實作）。從 `spec/tick.md` 搬來；B-628 與 B-602、B-620、B-633 的部分內容搬到暫緩區；2026-10-01 其餘各條拆到 tick/〔使用者 2026-10-01〕 |
| [tick/](tick/README.md) | B-636、B-625、B-635 | 2026-10-01 從 tick.md 拆出，條號不變；同日第六批新開 [hooks](tick/hooks.md)（B-635，外掛掛點，已實作）：[template](deferred/template.md)（B-629）、[check-task](deferred/tick/03-B-624與B-621.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)（B-621）、[cg](deferred/cg.md)（B-634、B-631；第二十三批搬暫緩區）、[mq](deferred/mq.md)（B-623、B-624）、[git](deferred/git.md)（B-630、B-622、B-632）、[recovery](tick/recovery.md)（B-625）；狀態見[子篇入口](tick/README.md) |
| [daemon.md](daemon.md) | — | 舊的 daemon 入口，只指向 daemon 目錄 |
| [daemon/](daemon/README.md) | B-640～646 | 2026-10-01 重寫：[core](daemon/core.md)（B-640）、[control](daemon/control.md)（B-641）、[reload](daemon/reload.md)（B-642）、[state](daemon/state.md)（B-643）、[cgroup](daemon/cgroup.md)（B-644）、[mq](daemon/mq.md)（B-645）、[account](daemon/account.md)（B-646） |
| [protocol/tick.md](protocol/tick.md) | P-200～214 | tick 協議。從 `spec/protocol/node.md` 搬來；2026-10-01 由 `protocol/node.md` 改名〔使用者 2026-10-01〕 |
| [protocol/daemon/](protocol/daemon/README.md) | P-100、P-120～126 | 2026-10-01 重寫：[core](protocol/daemon/core.md)（P-120）、[control](protocol/daemon/control.md)（P-121）、[reload](protocol/daemon/reload.md)（P-122）、[state](protocol/daemon/state.md)（P-123）、[cgroup](protocol/daemon/cgroup.md)（P-124）、[mq](protocol/daemon/mq.md)（P-125）、[account](protocol/daemon/account.md)（P-126） |
| [deferred/](deferred/README.md) | B-628、T-09、B-303、B-504、B-601、B-603～615、P-101～119 | 暫緩區；總表與每條狀態見它的 README |

`spec/protocol/daemon.md` 是更舊的單檔入口，留在原處，只指向這裡的 daemon 協議。

## 分檔目錄

> 2026-10-02 整理：原檔約 32 KB 超過 8 KB 門檻，按標題逐字拆進 `readme/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-收錄判準對外依賴與待放入.md](readme/01-收錄判準對外依賴與待放入.md) | 怎麼判斷哪些放進來；對外依賴；待放入 |
| 2 | [02-疑點-1001統一更新.md](readme/02-疑點-1001統一更新.md) | 疑點 |
| 3 | [03-疑點-1001第二批與訊息佇列.md](readme/03-疑點-1001第二批與訊息佇列.md) | 2026-10-01 第二批：astra 審查與使用者裁定落實；系統訊息佇列改寫後，區外要跟上的（還沒改） |
| 4 | [04-疑點-git與cgroup.md](readme/04-疑點-git與cgroup.md) | 納入 git 與 cgroup 後，區外的狀況；納入 git 與 cgroup：原暫定 13 題，已定案 |
| 5 | [05-疑點-前輪暫定與已關.md](readme/05-疑點-前輪暫定與已關.md) | 前一輪留下、仍是暫定的（astra 審整理區修正輪）；這輪關掉的；基礎條文依賴 kernel／agent 規則（已在上面「使用例」標出，留待其他篇放進來時再定）；更早幾輪修掉的舊疑點 |
