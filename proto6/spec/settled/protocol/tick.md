# tick：工作資料夾、任務表與一格 tick

← [整理區](../README.md)｜[共用約定](../../protocol/README.md)｜行為正本：[inst](../../base/inst.md)、[tick](../tick.md)、[設定](../../agent/configuration.md)｜[慣例](../conventions.md)｜[tick 暫緩區](../deferred/tick.md)｜[使用者裁定](../../../notes/2026-09-29-verdicts.md)

本篇只定格式：資料夾裡的檔名、JSON、argv、環境變數、結束碼。行為一律以 [tick](../tick.md) 等主規格為正本，這裡寫到行為只留一句加條號。

- 本篇寫的 `.aos/…` 都是環境變數 `AOS_DIRNAME` 沒設時的樣子；設成別的名字就換那個名字，設成空字串就直接放在資料夾本身（[C-09](../conventions.md)）。
- 結束碼照 aos 慣例（[C-08](../conventions.md)）：0＝預料之中、1＝通用錯誤（含 argv 用法錯）、其他碼是各程式特別指定的。
- **改名**〔使用者 2026-10-01〕：本篇原是 `protocol/node.md`（「node：資料夾、任務與一格 tick」），2026-10-01 改成 `protocol/tick.md`，叫「tick 協議」；跟 [tick.md](../tick.md) 的關係就像 [daemon/core.md](../daemon/core.md) 對 [protocol/daemon/core.md](daemon/core.md)：一個寫行為、一個寫格式。schema 跟著改名：`node-tasks` → `tick-tasks`、`node-tick-record` → `tick-record`、`node-inst` → `inst`；範例資料夾 `examples/node/` → `examples/tick/`。
- 本篇講的**工作資料夾**（英文 `tick dir`）就是 `aos-tick` 這一格的 cwd，原本寫 node 的地方都改了；暫緩區講上下層的「上層 node／下層 node」與舊 RPC 名稱（`node.take`、`node.send`…）照舊。

## 分檔目錄

> 2026-10-02 整理：原檔約 42 KB 超過 8 KB 門檻，按標題逐字拆進 `tick/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-200-P-201-資料夾布局與inst.md](tick/01-P-200-P-201-資料夾布局與inst.md) | P-200．資料夾布局〔建議預設，未拍板〕；P-201．inst 的格式與展開驗證〔使用者方向 2026-09-29〕 |
| 2 | [02-P-202-任務註冊表.md](tick/02-P-202-任務註冊表.md) | P-202．任務註冊表〔建議預設，未拍板〕 |
| 3 | [03-P-203-aos-tick與任務程式.md](tick/03-P-203-aos-tick與任務程式.md) | P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕 |
| 4 | [04-P-203結束碼與P-204-P-212.md](tick/04-P-203結束碼與P-204-P-212.md) | P-204．aos-tick-check-task；P-205．aos-git：開格、存檔點、收尾；P-206．系統訊息佇列 aos-mq 與發摘要；P-208．收件區權限〔建議預設，未拍板〕；P-209．待決與跨篇；P-210．預設範本與恢復前驗證〔主編補〕；P-211．aos-cg：每項一框；P-212．aos-as：切換帳號 |
| 5 | [05-P-213-結束碼紀錄.md](tick/05-P-213-結束碼紀錄.md) | P-213．每項結束碼紀錄、tasks-blocked 與擋板檔〔建議預設，未拍板〕 |
| 6 | [06-P-213-tasks-blocked與P-214.md](tick/06-P-213-tasks-blocked與P-214.md) | P-214．tick 模組 `tasks-blocked`〔使用者 2026-10-01 第十六批；第二十批改名〕 |
