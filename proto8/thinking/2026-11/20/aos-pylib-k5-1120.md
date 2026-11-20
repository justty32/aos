編譯程式庫第 5 刀（教學整章照新寫法實跑、改對不上的字、擬條文加註）施工紀錄（11-20，線 aos-pylib-k5-1120）：逐章實跑表、改了什麼、擬好等使用者點頭的 C-87 加註、跟設計對不上處、替使用者做的選擇、之後要再對一次的節。

← [2026-11-20](README.md)｜設計稿：[aos-pylib-plan-1120](aos-pylib-plan-1120/README.md)（[07c 第 5 刀](aos-pylib-plan-1120/07c-施工計劃-第3到5刀.md#第-5-刀-教學實跑與條文加註)）｜使用者答案：[12-使用者已答](aos-pylib-plan-1120/12-使用者已答.md)｜前四刀：[第 1 刀](aos-pylib-k1-1120.md)、[第 2 刀](aos-pylib-k2-1120.md)、[第 3 刀](aos-pylib-k3-1120.md)、[第 4 刀](aos-pylib-k4-1120.md)

## 一句話

教學 01～08 照新寫法（`defs.Agent(...)`＋`defs.main(agent)`、`@fn.tool`＋`fn.main`、`defs.extern` 編成連結）在乾淨複本＋暫存教學夾、真 daemon、假腦上**從頭打了兩遍**；程式沒有錯，對不上的五處都是教學的字：兩處舊寫法的詞（`SYSTEM`、`TOOLS`）、一處指令順序（改完 `kernel.json` 馬上 `aos-llm ls` 看不到新的一包）、06-2「衍生還能做的」兩個例子拿 ann 當底走不通。改了教學三份（06-1、06-2、教學 README），沒改程式；C-87 的加註字擬在下面，**沒交進條文檔**。

## 依據

- 設計稿 07c 第 5 刀：教學從 04 照順序走到 06-3、範例碼抄進暫存夾實跑；C-87 加註只列、不先改；`wf/HANDOFF.md` 不碰。
- 使用者 11-20：「舊的教學我都沒在用，現有的aos體系我也都沒在用。所以放心弄。」→ 不留舊寫法、不寫遷移。
- 使用者 11-20（比喻用詞）：「拜託，手、門只是比喻，幫我乖乖用kernel/daemon稱呼好ㄇ」；改名大工程之後再做 → 本線新寫的字不用那些比喻，既有的不動。

## 環境

- `git archive HEAD proto8`（HEAD＝`726c30ba1`）抄到 `~/.aos/scratch/aos-pylib-k5-1120/base`，複本裡 `install.py`（工作樹裡別線沒交的改動沒抄）。
- 每支腳本先 unset 所有 `AOS_*`，`export AOS_HOME=<複本>`、`source $AOS_HOME/env.sh`，在暫存教學夾（第一遍 `tut/`、改字後第二遍 `tut2/`）照教學一行一行打；視窗 A 的 `aos-exec root` 用 `setsid nohup` 放背景、記 pid。編輯器那幾步用小腳本照教學的字換掉 `# ---- your agent` 以下（`swap.py`）、在 `kernel.json` 的 `"endpoints": {` 後插那包（`addshout.py`）。
- `aos-gdb` 把教學那幾行從 stdin 餵進去。
- 第 07 章不叫真模型：只核對 `kernel.json` 的代號表、`endpoints/litellm/_entry`、`llm={"model": "luna"}` 的 `--dry-run`。
- 行程：每遍最後照第 08 章 `aos-daemon-ctl -d .stack shutdown` 收掉。

## 逐章實跑表

| 章 | 步數 | 對不上 | 怎麼處理 |
|---|---|---|---|
| 01 開始前 | 2 | 0 | — |
| 02 架 daemon | 9（含關機兩次） | 0 | — |
| 03 灌 kernel | 6 | 0 | — |
| 04 寫原始碼 | 6（抄骨架、換原始碼、`--dry-run`、`--compile`、`cat llm.json`、check） | 0 | — |
| 05 掛上去跑 | 10 | 0 | — |
| 06-1 改與工具 | 6.1：改 `system=`＋3 步；6.2：13 步；末節函數寫在 agent.py：另開 `agents/fnann` 編譯＋check 5 步 | 3 | 兩處舊詞改字；`aos-llm ls` 挪到 `listen` 之後並加一句為什麼（見下） |
| 06-2 連結與衍生 | 6.3：5 步；6.4：4 步；6.5：9 步；「衍生還能做的」三條用 `.dry_run()` 試 | 2 | 兩個例子加一句前提（見下） |
| 06-3 除錯與腳本 | gdb 7 行＋`b.id`、`b.kind`、刪了再讀；`ask.py`；bob 下斷點看 `HooksMissing` | 0 | — |
| 07 換成真模型 | 只核對 3 項（不叫真模型） | 0 | 照舊標「整章未實跑」 |
| 08 出事時與收尾 | 錯誤行 5 種＋收尾 3 步 | 0 | — |

輸出比對時不算的差：pid、時間、信名、`memory`／`processes` 數字、`history` 位元組（517 對 519，時間字串）、路徑（教學寫 `~/code/aos-tut`）。

### 對不上的五處

1. **06-1 6.1「把 `SYSTEM` 第一行改成」**：舊寫法的詞（第 2 刀起是 `defs.Agent(...)` 的 `system=`）。→「把 `defs.Agent(...)` 裡 `system=` 的第一行改成」。
2. **06-1 6.2 結論「在 `agent.py` 的 `TOOLS` 加一行」、「`TOOLS` 裡用法」**：同上。→「`tools=[…]` 加一項」「`tools=[…]` 裡的寫法」。
3. **06-1 6.2 劇本假腦**：照教學改完 `llm/kernel.json` 馬上 `aos-llm ls | grep shout`，**什麼都沒印**（退 1）。查了：`aos-llm ls` 讀的是 llm kernel 的窗 `<stack>/endpoints.json`，kernel 只在接到信的那一輪才重讀 `kernel.json`、重寫窗（沒有信時 6 秒內 mtime 不動，`touch kernel.json` 也不動）；`say` 一封之後 `ls` 就列得出。教學說的「每一輪都重讀這檔，不用重起」是對的（ann 沒重起就叫到 shout）。→ 把 `aos-llm ls` 那行挪到 `listen` 之後，加一段說它列的是上一次接信時寫的表。這不是程式的 bug（窗本來就是 kernel 每輪寫的），只是教學的順序。
4. **06-2「衍生還能做的」改 hook 一欄**：`hooks=[base.hooks, {"timer": {**base.hooks["timer"], …}}]`，拿 ann 當底時 ann 是 `hooks={}`，`base.hooks["timer"]` 是 `KeyError`；底是 `hooks=std.hooks()` 時 `.dry_run()` 過、`every_ms` 變 60000。→ 加一句「底要真的有那支 hook」。
5. **06-2「衍生還能做的」改狀態機一格**：`defs.fsm(base.fsm, [defs.state("think", [...])], drop=["act"])` 拿 ann 的四格當底＝`SpecBad state wait: next state 'act' is not one of the states (idle, think, wait)`（整張表重驗，`wait` 還指著 `act`）；只改 `think`、不 drop 就過。→ 例子拆成「改一格」與「drop 要連指著它的格一起改」，附那行錯誤。

另外教學 README：實跑的 commit 從 `a98cfbc64` 改成這次的 `726c30ba1`（寫明是換新寫法後從頭再跑）；章節表 06-1 那列加「工具或 hook 直接寫在 agent.py」與 `@fn.tool`。

### 第二遍（改字之後，新的教學夾 `tut2/`，同一份複本）

01～08 一路照打：非 0 的退出碼只有教學本來就寫會失敗的五個（`ArgumentsBad`、`AOS_WS is not set`、`HomeMissing`、`wiat`、`InstanceMissing`）；`aos-llm ls | grep shout` 挪到後面印出 `fake-shout`；五封信的回答都是教學寫的那句。輸出全文在 `~/.aos/scratch/aos-pylib-k5-1120/tut2.log`。

### 有對、值得記的

- 06-1 末節（函數寫在 agent.py）：`fn/shout.py`、`fn/no_secrets.py` 都是 755；`tools.json` 是 `{"path": "fn/shout.py"}`、`hooks.json` 是 `{"event": "before_tool", "handler": "fn/no_secrets.py", "condition": "ws_write"}`；`agent_def check` 回 `{"problems": []}`。教學沒要掛上去跑這隻，本線也沒掛（第 3 刀的實掛測試已做）。
- 06-2 bob：`--compile` 最後一行 `wrote …/system.txt -> system.hand.txt`、`readlink` 是 `system.hand.txt`、腦照樣叫 shout。
- 06-3：`HooksMissing` 那行的修法字是 `give hooks={} to defs.Agent(...) in agent.py, and recompile (python3 agent.py --compile)`，跟教學與第 08 章的表一致。
- 骨架 README、骨架 `agent.py`、`templates/` 裡沒有舊寫法（`git grep` 舊樣式只剩教學 06-1 那三處，已改）；`templates/` 裡示範用的 `agent.py` 只有骨架那一支，前四刀已改，本線沒動。

## 擬好、等使用者點頭的條文加註（沒交進條文檔）

位置：`docs/CONCEPTS/03-基礎設施/02-資料夾程式-工作區與-stack/01-stack與工作區分開.md:10`，C-87 的「11-19 加註」括號裡「…[aos-vs-c-1119](…) G2）」之後、「；執行時沒有命名空間機制」之前，加：

> ；11-20 補：`agent.py` 裡寫成 `@fn.tool`／`@fn.hook` 的函數，編譯時抽成定義夾裡的 `fn/<名>.py`，程式本身在定義夾、重新編譯才變，但它 import 的 `fn` 執行時從 `$AOS_HOME/lib` 讀，所以 aos 升級一樣會影響已編譯的 agent（[aos-pylib-k3-1120](../../../../thinking/2026-11/20/aos-pylib-k3-1120.md)）

設計稿（07c、07d 意見 13）只列 C-87 這一句；12-使用者已答沒有說可以直接寫，所以只擬字。別的條文設計稿查過不用加（N-70 沒範例碼、C-74 沒提 `defs`、C-51 名字不變）。

## 跟設計對不上、或設計沒寫到的（選最小）

1. **kernel 入口 `from aos.py.kernel import defs` 沒做**：任務書寫「若設計說這刀不做 kernel 入口就不做」；設計稿 07「不排的」第一項是 kernel 類別（第 9 題答了入口名，但 kernel 類別與初始 kernel 八題還沒排刀）。教學也沒有要寫 kernel 的章。
2. **設計說從 04 走到 06-3，本線 01～08 全走**：任務書寫「整套」；07 只核對不叫真模型（守硬規則 8）。
3. **「衍生還能做的」兩個例子是改字、不是刪**：例子本身對（換一個有 timer 的底、drop 時連 `wait` 一起改就過），只是拿教學裡的 ann 當底走不通，補前提最小。
4. **既有的比喻詞沒動**：03 章「llm kernel 像一台專門打電話的總機」「寄一封信進總機的收件匣」、「權限件：一台站」還在（任務書：改名之後再做，只是新寫的字別用）。本線新寫的字沒用手、門、總機、站、把手。

## 替使用者做的選擇

- C-87 加註只擬字（12-使用者已答沒說可以直接寫）。
- 第 07 章不叫真模型，照舊標「整章未實跑」；只核對檔與 `--dry-run`。
- 06-1 的 `aos-llm ls` 用「挪到後面＋說明」處理，沒改成「先 `say` 一封再 `ls`」或叫人等；理由：教學原本的步驟順序與輸出最少改動。
- 06-1 末節的函數 agent 沒有掛上去跑（教學沒寫要掛；第 3 刀 live 測試已實掛過）。

## 之後要再對一次的節（hook 兩條線還在跑，照現在 HEAD 寫的）

- **aos-hook-k2b-1120**（agent-fsm 格程式、hook 引擎、`hook_points.json`）：06-3 整節（`a.bp.add.before_tool`、`step` 停在 think 前、`hook add` 那行指令的旗標、`HooksMissing` 的字）、06-1 末節的 `@fn.hook("before_tool", condition=…)` 與「`after_tool` 寫 `fn.block` 報 `SpecBad`」、05 的 `hooks 0 hooks`。
- **aos-hook-k5-1120**（`aos-loop`、`loop.json` 產生處）：04 的 `--compile` 輸出（`wrote …/loop.json` 那行與順序）、骨架 README 檔案表 `loop.json` 那列（「with hooks, fires after_start / after_stop」）、06-1 6.1 那行「state machine and loop changes: from their next tick or restart」。

## 全套測試逐夾

教學沒有比對測試（`grep tutorial` 在 `*.py` 沒有命中）。改的只有 md，改前（`base`）／改後（`base` 疊本線三份 md 的 `after`）各跑一輪：結果見下表（交件前補）。

## 交件

本線只交：`docs/tutorial/06-接著開發-1-改與工具.md`、`06-接著開發-2-連結與衍生.md`、`README.md`、這份紀錄；日索引一列（`day_upsert`）、`wf/progress.json` 的 `aos-compile-base` 只加字（`progress_upsert`）。沒刪檔、沒 push、沒在 repo 跑 `install.py`。暫存在 `~/.aos/scratch/aos-pylib-k5-1120/`（複本 `base`、教學夾 `tut`、`tut2`、`probe-sd2`（試關機兩次的小板子）、留底 `tests-*`、各章腳本），都沒刪。
