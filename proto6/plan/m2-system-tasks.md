# 第二段：不靠 daemon 的系統級任務與普通程式（草稿，部分已裁定）

← [plan 入口](README.md)｜正本（除 B-621 外都是 tick 大幅簡化**之前**寫的）：[範本 B-629](../spec/settled/deferred/template.md)、[aos-tick-check-task B-621](../spec/settled/deferred/tick/03-B-624與B-621.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)（2026-10-01 改寫）、[git B-630／B-622／B-632](../spec/settled/deferred/git.md)、[恢復與設定 B-625](../spec/settled/tick/recovery.md)、[清理 B-404](../spec/base/storage.md)｜格式：[tick 協議](../spec/settled/protocol/tick.md) P-204、P-205、P-210、P-213（停格檔）；[P-605](../spec/protocol/ops.md)（`aos-clean`）｜已搬暫緩區：[發摘要 `aos-publish`（B-624 部分、P-206 那列）](../spec/settled/deferred/tick/03-B-624與B-621.md#暫緩b-624-發布摘要aos-publish)、`aos-config-add`（B-625 部分、P-207）｜現在的 tick：[核心](../spec/settled/tick.md)、[慣例 C-08～C-11](../spec/settled/conventions.md)

> **〔2026-10-01 第十七批〕`aos-git` 整套搬暫緩區**（使用者：「git這塊先不要進範本。」）：改用 hooks 加普通 git 指令（[B-635 範例](../spec/settled/tick/hooks/03-B-635-範例hook加git.md#範例用-hook-加普通-git-指令管版本)），範本只留沒有 git 的那份。**文末待問 1～12 隨之擱置**（大多是 `aos-git` 的題）；`aos-tick-check-task` 第十六批也已暫緩。本檔照留當紀錄。
>
> **狀態：草稿（2026-10-01），還沒開工。** 2026-10-01 使用者已裁定 `aos-publish` 搬暫緩區、`aos-needs` 改寫成 `aos-tick-check-task`（見文末「裁定紀錄」）；其餘文末「待問」裁定後才照做。下面各步寫的是「建議的最單純版本」；舊 spec 跟現在 tick 對不上的地方集中在「舊規定哪裡對不上」一節。

**做完的樣子**（照建議裁定的話）：在沒有 daemon、cgroup、helper 的機器上，直接跑 `aos-tick <資料夾>`：

- 表上可以掛一項 `aos-tick-check-task a b`：本格 `a`、`b` 都沒出現在紀錄的失敗清單就什麼都不做；有出現就建停格檔，本格後面的項都不跑。不寫 id＝失敗清單非空就停（第八批）。
- 資料夾是 git repo、表上掛 `aos-git open`／`mark`／`close`：每格最多一個 commit `aos-tick <seq>`，只含狀態資料夾（預設 `.aos/`）裡的東西；上一格沒正常收尾，下一格開頭把 `.aos/` 還原；某一組任務失敗，那組在 `.aos/` 寫的東西被還原、不提交。不是 repo 時 `aos-git` 只印 `no_git`、回 0。
- 兩份第二段版範本任務表（沒 git、有 git）照常跑完。

> **POC 總原則**（[plan 入口](README.md)）：默認一切正常——git 指令都會成功、紀錄讀得懂、任務表是對的、沒有人在 tick 外亂改、`id` 不重複。不寫異常處理，出事讓 Python 自然丟錯（traceback、回 1）。
>
> **結束碼**（[C-08](../spec/settled/conventions.md)）：0＝預料之中；1＝通用錯誤（含用法錯）；`aos-tick-check-task` 建了停格檔也回 0（停格是預料之中），自己的錯回 1；原本 `aos-needs` 的 125 隨改寫拿掉。

- 由 AI 隊實作、照各步驟驗收試跑，做完交使用者看；每步的「要使用者裁定的點」集中在文末待問。
- Python 3.9、只用標準庫。放 [src/py](../src/py/README.md)：入口 `bin/aos-tick-check-task`、`bin/aos-git`（薄殼，`.gitignore` 擋 `bin/`，要 `git add -f`）；程式 `lib/aos_tick_check_task.py`、`lib/aos_git.py`（檔案怎麼切 AI 隊自己定）；測試 `tests/test_check_task.py`、`test_git.py`、`test_template.py`，用 `unittest`。狀態資料夾名一律用現成的 `lib/aos_dirname.py`。
- 任務表寫 `aos-git` 這種裸名字時要靠 PATH 找到 `src/py/bin/`；測試裡把 `bin/` 加到 PATH 最前面，不寫絕對路徑（這樣範本才能原樣用）。
- **`aos-publish`（發摘要）不在這段**：使用者 2026-10-01 裁定搬暫緩區（[B-624 部分、P-206 那列](../spec/settled/deferred/tick/03-B-624與B-621.md#暫緩b-624-發布摘要aos-publish)）；「把這一格總結成 JSON」的 `aos-summarize` 也暫時不做。
- **`aos-config-add` 不在這段**：已決定搬去暫緩區（[P-207](../spec/settled/protocol/tick.md)、[B-625](../spec/settled/tick/recovery.md)「改設定」）。**`aos-clean`、恢復前驗證**做不做見待問 9、10；下面的步驟先照「建議不做」排，沒有它們的步驟。
- **`aos-mq get`／`post` 不在這段**（第四段，要 daemon 通道）。

## 分檔目錄

> 2026-10-02 整理：原檔約 31 KB 超過 8 KB 門檻，按標題逐字拆進 `m2-system-tasks/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-現況對不上與步驟1.md](m2-system-tasks/01-現況對不上與步驟1.md) | 現在的 tick 給系統級任務什麼；舊規定哪裡對不上；步驟 1：aos-tick-check-task |
| 2 | [02-步驟2-4-aos-git.md](m2-system-tasks/02-步驟2-4-aos-git.md) | 步驟 2：aos-git 的共通部分；步驟 3：aos-git open 與 close；步驟 4：aos-git mark（存檔點） |
| 3 | [03-步驟5-6-範本驗收與不做的.md](m2-system-tasks/03-步驟5-6-範本驗收與不做的.md) | 步驟 5：兩份第二段版範本；步驟 6：整段驗收；這段不做的，先怎麼擋著 |
| 4 | [04-待問.md](m2-system-tasks/04-待問.md) | 待問 |
| 5 | [05-裁定紀錄.md](m2-system-tasks/05-裁定紀錄.md) | 裁定紀錄 |
