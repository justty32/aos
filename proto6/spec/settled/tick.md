# 通用 tick：核心

← [整理區](README.md)｜[名詞](terms.md)｜[慣例](conventions.md)｜[daemon](daemon/README.md)｜格式：[tick 協議](protocol/tick.md)｜系統級任務、範本與普通程式：[tick 子篇](tick/README.md)｜先不做的：[tick 暫緩區](deferred/tick.md)、[helper 與 aos-as](deferred/helper.md)

依據：[09-29 新架構](../../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../../notes/2026-09-29-verdicts.md)第三～十二批、[第十八批](../../notes/verdicts/09-special-computing-os.md)、[第十九批](../../notes/verdicts/10-tick-minimal-core.md)、[第二十批](../../notes/verdicts/11-tick-as-unit.md)與它篇末 2026-10-01 各節；現行程式 [proto6/src/py](../../src/py/README.md)。

讀之前先知道四件事：

- **本篇只寫已實作的核心**（B-626、B-602、B-620、B-633、B-627），由現行程式 `aos-tick` 實作。tick 模組與 hooks 在 [tick 子篇](tick/README.md)（系統級任務與範本第十八批全部搬暫緩區；`aos-tick-check-task` 第十六批、`aos-git` 第十七批、普通程式 `aos-cg` 第二十三批），一篇一個主題，大多還沒有程式，每篇開頭標了狀態。〔astra 報告建議 1；使用者 2026-10-01〕
- **工作資料夾**（英文 `tick dir`）＝這一格 `aos-tick` 跑的資料夾（它的 cwd），由命令列給的目標決定（`aos-tick [<目標>]`，B-620）。tick 這層只講工作資料夾；「node」是之後 node 模組才出場的詞，暫緩區講上下層時的「上層 node／下層 node」照舊。〔使用者 2026-10-01〕
- 「任務表」指工作資料夾裡的任務註冊表 `.aos/tasks.json`，跟舊 daemon 的登記表是兩回事（[T-02](../terms.md)）。
- 本篇寫的 `.aos/…` 都是環境變數 `AOS_DIRNAME` 沒設時的樣子（[C-09](conventions.md)）；結束碼照 aos 慣例：0＝預料之中、非 0＝要處理、1＝通用錯誤（[C-08](conventions.md)）。

## 分檔目錄

> 2026-10-02 整理：原檔約 50 KB 超過 8 KB 門檻，按標題逐字拆進 `tick/core/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-先講重點.md](tick/core/01-先講重點.md) | 先講重點 |
| 2 | [02-B-626-核心與系統級任務界線.md](tick/core/02-B-626-核心與系統級任務界線.md) | B-626：核心與系統級任務的界線 |
| 3 | [03-B-602-互斥鎖與B-620開頭.md](tick/core/03-B-602-互斥鎖與B-620開頭.md) | B-602：同一資料夾一次一格：互斥鎖；B-620：任務註冊表：照表依序跑 |
| 4 | [04-B-620-任務表與頂層預設.md](tick/core/04-B-620-任務表與頂層預設.md) | 任務表；頂層預設〔使用者 2026-10-01〕；頂層 `modules`〔使用者 2026-10-01〕；指示詞什麼時候展開〔使用者 2026-10-01 第二十批：「tasks.json改成全部解完」「除了陌生鍵和_metainfo」〕 |
| 5 | [05-B-620-讀表與跑每一項.md](tick/core/05-B-620-讀表與跑每一項.md) | 讀表：極簡檢查；誰驗什麼〔暫定〕；跑每一項 |
| 6 | [06-B-620-tasks-blocked與帳號.md](tick/core/06-B-620-tasks-blocked與帳號.md) | tasks-blocked 與擋板檔〔暫定〕；任務的帳號 |
| 7 | [07-B-620-核心結束碼.md](tick/core/07-B-620-核心結束碼.md) | 核心的結束碼 |
| 8 | [08-B-633-紀錄與格數.md](tick/core/08-B-633-紀錄與格數.md) | B-633：每項結束碼紀錄與格數 |
| 9 | [09-B-633收尾與B-627.md](tick/core/09-B-633收尾與B-627.md) | B-627：人手或 cron 直接跑一格：風險自負；驗收與尚未定案 |
