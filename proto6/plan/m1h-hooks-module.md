# 第一段之二：hooks（外掛掛點）

> **補註（2026-10-01 第十七批）**：掛點加到四個——`before_all`、`after_task`（{任務 id: [inst…]}）、`after_every_task`、`after_all`；跟任務有關的兩個另給 `AOS_TASK_ID`／`INDEX`／`EXIT`；`hook-exits.json` 改成開格就建、跟任務有關的筆帶 `task_index`。下面是只有 `after_all` 時的原計畫，照留；現行規定見 [B-635](../spec/tick/hooks.md)。

← [plan 入口](README.md)｜**接在 [m1-tick-core](m1-tick-core.md) 之後。**｜依據：[verdicts 11 篇末「第六批：tick 的 hooks（外掛掛點）」](../notes/verdicts/11-tick-as-unit/11-1001-第六七批.md#2026-10-01-第六批tick-的-hooks外掛掛點已寫入-speccommit-前由我補號)｜結束碼：[C-08](../spec/conventions.md)｜spec 正本：[B-635](../spec/tick/hooks.md)、格式 [P-202、P-203、P-213](../spec/protocol/tick.md)

**做完的樣子**：任務表 `.aos/tasks.json` 頂層多一個可選鍵 `hooks`（跟 `tasks` 同層）。寫了 `"hooks": {"after_all": [...]}`，`aos-tick` 照表跑完（含被停格檔停下）之後就照順序跑那一串，每項的碼記進本格紀錄的 `hooks.after_all`。沒寫 `hooks` 時 `aos-tick` 就是 m1 原樣。

> **使用者裁定（2026-10-01，原話）**：「那就做外掛掛點，這個hooks就是模組」「after_cell？我以為是after_all，我們有cell嗎？ 2.可以一串。 3.吃，hooks中的掛點所提供的，比如"after_cell":[{},{},...]，就比照tasks。4.會記錄。 剩下都建議」。同日改：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。
>
> 1～4 的意思：掛點叫 `after_all`（沒有 cell 這回事）；一個掛點可以掛一串；每項吃 tasks.json 頂層預設、寫法比照 `tasks`；碼要記錄。「剩下都建議」＝下面標「AI 隊定」的照建議做。改裁定：hooks 不放 `modules` 底下、不叫模組，直接是頂層鍵。

> **POC 總原則**：默認一切正常，不寫邊緣處理。

> **結束碼**：hooks 不新增任何碼；tick 照舊只回 0／1，hook 回幾都不影響。

## 分檔目錄

> 2026-10-02 整理：原檔約 9 KB 超過 8 KB 門檻，按標題逐字拆進 `m1h-hooks-module/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-步驟1-2-讀表與何時跑.md](m1h-hooks-module/01-步驟1-2-讀表與何時跑.md) | 步驟 1：讀表與極簡檢查；步驟 2：什麼時候跑、怎麼跑 |
| 2 | [02-步驟3-4-紀錄驗收與收尾.md](m1h-hooks-module/02-步驟3-4-紀錄驗收與收尾.md) | 步驟 3：紀錄；步驟 4：整段驗收；這段不做的；待問；做完了沒 |
