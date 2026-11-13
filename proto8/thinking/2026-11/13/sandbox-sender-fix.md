# 沙箱與腦請求寄件人修正（線修，11-13 晚，家機）：修 gpt 隊試驗撞到的沙箱四條（T32 深的規則說了算、T36 沒綁的地方唯讀、T34 工具夾自動看得到；T21 與使用者 11-12 裁定衝突、沒改）與腦請求寄件人兩條（T31／T38 一律用 stack、T39 對不上的額度 key 提醒）。

← [2026-11-13](README.md)｜試驗紀錄：[gpt-fsm-team 06](gpt-fsm-team/06-試驗紀錄.md)

## 原話

頂層報告試驗三點後，使用者（11-13 晚，逐字，頂層轉）：

> 1.貴不是他的問題，是我的問題(泣)...好啦不鬧，這塊就是要跟astra說，請他盡量把雜事和簡單工作交給sol，要是這樣還貴的話就沒辦法，之後慢慢調整成medium或轉而讓sol指揮，反正慢慢調整。其次是gpt的額度很耐用，所以我覺得還行。2.好，總之修到順手。3.好，就統一用stack，這確實該這樣。剩下的都隨你。

第 1 點歸線隊（已做，見 commit 579230106）；這份做第 2 點（沙箱修到順手）與第 3 點（腦請求寄件人統一用 stack）。

## 改法（每條一段）

### A 沙箱（`cmd/aos-sandbox/bin/aos-sandbox`，存檔即生效）

| # | 現象（摘 06） | 改法 | 測試 |
|---|---|---|---|
| T32 | rw 最後綁、蓋過 ro，表達不了「repo 可寫、`.git` 唯讀」 | `ro`、`rw` 混在一起照路徑深淺排（看實際位置：符號連結看它指到的地方）、淺的先綁＝深的說了算；同深度 ro 先 rw 後（同一條兩邊都列＝可寫，同舊） | `test_dry_run_orders_binds_by_depth_and_ends_read_only`、`test_ro_inside_rw_stays_read_only`（兩個方向都測：rw repo＋ro .git、ro repo＋rw sub） |
| T36 | 寫到沒綁的路徑落進沙箱暫存根、退 0、主機沒檔 | 所有綁定之後加 bwrap `--remount-ro /`：沒綁的地方＝`Read-only file system`、指令失敗。`/tmp` 照舊可寫（沙箱自己的、跑完就沒了） | `test_write_outside_rw_fails_loudly` |
| T34 | `ro` 改絕對路徑後沙箱裡看不到工具夾，`inner` 找不到 | 設定檔所在的資料夾（工具夾）沒被任何 `ro`／`rw` 蓋到＝自動唯讀綁；被蓋到就不另綁（在 rw 裡的照舊可寫）。README 寫明「別把祕密放在沙箱設定旁邊」、`inner` 指到的地方照舊要列 | `test_dry_run_binds_the_config_folder_only_when_not_listed`、`test_config_folder_is_visible_so_relative_entries_work` |
| T21 | 設定寫壞＝不套沙箱照跑（只印 warning） | **沒改**：這是使用者 11-12 晚明裁的（「甲，出事自己負責」，[metainfo-views](../12/metainfo-views.md)），頂層派單寫「改成報錯」與它衝突；不翻使用者的裁定，列進待裁。T21 的乙（「s6 只在設上限時才要」）README「需要」一節本來就寫了 | — |

另外照試驗的寫法（gpt-lead 的 shell-boxed：`ro` 全絕對、沒列工具夾、rw repo、ro repo/.git）在 repo 外 stage 用 aos-exec 跑真的 shell 工具一次：寫 repo 成、寫 `.git` 與 `$HOME` 都 `Read-only file system`、`inner` 找得到。

舊測試 `test_good_config_really_runs_inside_bwrap` 的祕密檔原本跟設定檔放同一夾，T34 之後會被看到；改成設定放自己的夾（行為改變是刻意的）。

### B 腦請求的寄件人（C++，待停樹換執行檔）

| # | 現象 | 改法 | 測試 |
|---|---|---|---|
| T31／T38 | 送給 llm kernel 的信封 `sender`＝`aos::identity()`（`$AOS_WS` 優先），同工作區的 agent 共用一格額度；信箱信封卻是 stack | aos-util 加 `aos::stack_identity()`＝`$AOS_STACK`（空字串算沒設、相對的從 cwd 算、轉絕對）＞`aos::identity()`；aos-post 的 `SendOpts` 加可選 `sender`（不給＝照舊 `identity()`，aos-post 自己的行為不變）；aos-llm 的 `send` 與 `ask`（`send_held`）都改用 `stack_identity()` | `impls/aos-llm/tests/test_sender_stack.py`（4 則：send、相對 stack、沒 stack 退回工作區、ask） |
| T39 | 額度 key 寫錯不報錯 | 查證：Python 與 C++ kernel 本來就會在 key「不是資料夾」時印 warning（活樹 `procs/llm-gpt/budget_warned.txt` 確實有那行，只是沒人看 stderr；06 說「不提醒」不準）。真正易錯的是 `used.json` 的 key 相對 kernel stack、`kernel.json` 的 key 相對設定檔所在夾。最小改動：① 不是資料夾、而「從 kernel stack 算」對得上時，warning 多寫一句對的路徑；② key 是資料夾卻沒有 `state.json`（不是起過的 proc 的 stack，多半照舊寫成了工作區——改成 stack 之後這種 key 永遠對不上）也印一行。兩邊（`lib/aos/kernel_llm/budget.py`、`impls/aos-llm-kernel/src/budget/budget.cpp`）同一套字 | 兩邊 `test_two_machines.py` 各加 2 則、改 1 則（`agents/here` 補 `state.json`） |

文件與知識庫跟著改：`knowledge/aos/brain.json#/priority`（寄件人＝你的 stack）、`knowledge/aos/cli/sandbox.json`（run、config 兩節）、`kernel/docs/01-llm-kernel.md`、`impls/aos-llm-kernel/{README.md, docs/02, docs/04}`、`impls/aos-llm/docs/01`、`cmd/aos-sandbox/README.md` 與 `examples/shell-boxed/README.md`、`--help`；兩處 gitignore 指南的「sender＝工作區」註解改成分開講。

## 代定

1. 寄件人「一律用 stack」只改**腦請求**（aos-llm）；aos-post 的信封與 aos-lock 名牌照舊 `identity()`（工作區優先）。理由：派單只講腦請求；aos-post 被很多地方用（人在殼裡寄信沒有 stack），一起改範圍太大。要統一再開一條。
2. 沒有 `$AOS_STACK`（人在殼裡打 `aos-llm ask`）＝退回 `identity()`。
3. 「不是 proc 的 stack」用「資料夾裡沒有 `state.json`」判斷（daemon 給每個 proc 的 stack 都會寫）。只是提醒、照樣收那格。
4. T34 自動綁的是**設定檔所在的資料夾**（不是 cwd）；已被 ro／rw 蓋到就不綁，所以不會把 rw 裡的工具夾變唯讀。
5. T36 `/tmp` 照舊可寫（程式常要暫存）；寫進去的跟以前一樣跑完就沒了。

## 沒做的

- T21 改 fail-closed：與使用者 11-12 晚裁定衝突，**待使用者裁**：維持「壞了不套沙箱照跑＋warning」，還是改成「壞了報錯不跑」。
- aos-post／aos-lock 的寄件人不動（代定 1）。
- 額度 key 收「名字樣式」（06 T26 乙）沒做。
- 活樹的 `~/aos-home/lib` 是複本：`lib/aos/kernel_llm/budget.py` 要重抄才生效（活樹的 `llm-gpt` kernel 用的就是它）；`knowledge/` 兩份也要重抄。C++ 的 aos-llm、aos-llm-kernel 在 repo 外 `~/code/fix-1113/build` 編好、測過，**待停樹換**（`impls/aos-llm/bin/aos-llm` 是 `~/.local/bin/aos-llm` 指的那支）。aos-post、aos-lock 也重編過（只多一個欄位、行為不變），可以不換。
- 換了 aos-llm 之後，活樹 `llm-gpt/kernel.json` 那格 `"../../../../teams/t1"`（本來就沒對上）要改寫成各 agent 的 stack 絕對路徑才有每寄件人上限；`used.json` 裡舊的工作區 key 換窗後自然消失。
