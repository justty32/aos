# KISS 鳥瞰：proto8 現有規範＋實作，哪些是兩套做一件事、哪些可以刪

範圍：整體鳥瞰——NORMS（規範）與實作（lib 程式、lib 說明、bin、demo、測試、proto8-1）。不鑽單一模組（loop／daemon、窗、fsm、kernel、agent、總則、組合子各有人看）。概念（CONCEPTS）不審。

← [討論紀錄](../README.md)｜前提：KISS 最高、C-52 只管自己這一層、C-53 只處理自己的錯（[原則稿](../2026-10-15-principles.md)）｜已在處理、本稿不重提：[inst-exec 第三版](../2026-10-15-inst-exec-v3.md)（TARGET 全拿掉、aos-inst 只吃 stdin、aos-exec 語法糖、frame.json、aos-tree 刪、$abs_path 不做）、原則稿第 2、4、5、6 條。

> AI 盤點稿（10-15 深夜）。每條：現況 → KISS 版 → 動到哪 → 風險。直接給推薦。

## 現在有哪些東西、怎麼疊

```
規範  N-01～N-44（9 份分檔，約 45 KB）
程式  proto8/lib 24 支 .py（4350 行）＋ proto8-1 6 支（316 行）；bin/aos 10 個子命令、proto8-1/bin 5 支
      inst ─ loop ─ daemon(=loop 子類＋表＋控制資料夾)        ← 基礎
      inst ─ methods ─ fsm ─ agent_lib(5 格)＋frame＋2 顆腦   ← agent
      inst ─ mailbox ─ gate ─ kernel_llm ─ judge ─ kernel_general＋judge_rules   ← kernel
      tree（v3 已刪）；tasks seq/par/if/not＋tick（proto8-1）
說明  lib/README 11 KB＋11 份 lib/x.md（約 64 KB）＋每支檔頭 docstring   ＝ 同一件事寫三處
demo  5 條跑法（daemon、fsm、paint、kernels/llm、kernels/general）＋proto8-1 三條 pipeline；6 個 agent 定義資料夾
測試  proto8 172 個、proto8-1 21 個
```

兩套做同一件事的，一眼看得到的有六組：**kernel 兩種**、**daemon 與 loop**、**ctl 窗與控制資料夾**、**tasks 與 sh**、**loop 的 stop_on_end 與 fsm 的 end**、**五份一模一樣的 agent 定義**。下面逐條。

## 一、兩套做同一件事 → 合成一套

1. **兩種 kernel。** 現況：`aos_kernel_llm.py`（218 行）與 `aos_kernel_general.py`（254 行）各一支，general 的功能是 llm 的超集（slots 多資源、判官可插、沒判官就用規則）。KISS：只留 general，LLM kernel＝它的一份設定 `{"slots": {"llm": 1}}`（判官不寫＝規則）。動：刪 `aos_kernel_llm.py`、`kernel_llm.md`，`deadline()` 搬進 `aos_kernel_judge_rules.py`；`bin/aos` 的 `kernel llm`；`demo/kernels/llm` 改成 general 的設定；N-42「先做兩種」改「一種、兩份設定」。風險：N-42 是使用者定的「兩種」——實作合一不違反「兩種用法」，但要他點頭；llm demo 三段要重跑一次確認順序不變。
2. **排序政策寫在 kernel 身體裡，又有判官。** 現況：priority／deadline／aging_ticks／near_ms／budget 的算法在 kernel 身體，判官另外決定 run／defer／reject，兩邊都在排序。KISS：身體只管「格數、問判官、起跑、放格」；所有政策（級數、deadline、aging、額度）全搬進規則判官，身體一個政策 key 都不認。動：`aos_kernel_general.py`（刪 budget／aging_ticks／near_ms）、`aos_kernel_judge_rules.py`（接手）、state 窗子集加 `served`。風險：額度是跨拍累計，判官要從 state 窗子集拿 `served`；判官 inst 每拍多算一點，原型期無妨。
3. **daemon 是另一支程式，其實是 loop 的子類。** 現況：`aos_daemon.py`＋`aos_daemon_table.py`＋`aos_daemon_folder.py`（690 行）繼承 `aos_loop.Loop`，N-28 自己說「daemon.json 是 loop.json 的嚴格超集」。KISS：一支 `aos loop`，設定裡有 `children` 就多管子項；`aos daemon` 這個名字、`aos_daemon.py` 入口刪（表的程式碼留一個模組，loop 有 children 才載）。動：`aos_daemon.py` 併入 `aos_loop.py`、`bin/aos`、N-28 改「同一支程式」、`daemon.md` 併進 `loop.md`、demo 與測試的 `aos daemon` 改 `aos loop`。風險：「daemon」這個詞在文件裡到處是；只改程式名、文件裡仍可叫「有 children 的 loop＝daemon」。
4. **控制一個 daemon 有兩條路。** 現況：宣告式 ctl 窗（N-06～N-08）之外，daemon 還有指令式控制資料夾（N-10：add／set／pause／resume／add_times／remove／state／get／list，`.done` 回信），其中 pause／resume／add_times／state／get 全是「替子 loop 寫 ctl、讀 state」的轉手。KISS：只留宣告式——`children` 進 daemon 的 ctl.json（整份就是全部期望，add／remove＝改這份），要暫停某個子 loop 就直接寫**它的** ctl.json（窗本來就「誰都可以寫」）；控制資料夾、`.done`、`table` 窗、`load` 全刪，子項狀況看各自的 state 窗。動：刪 `aos_daemon_folder.py`，`aos_daemon_table.py` 只剩起／收子程序，N-10 刪、N-11「ctl 只能蓋節奏類」加一句 children 例外、N-28 刪 ctl_dir／table／load／policies 字句，`demo/run.py` 重寫，`test_daemon.py` 大半重寫。風險：N-10 是使用者 10-12 親定；「一問一答」這種窗之後若真的需要再開；`policies.child_exit` 策略格跟著刪（子項掛了＝state 窗看得到，要重起就改 ctl）。
5. **tasks 四支＝sh 四個字。** 現況：proto8-1 的 aos-seq／par／if／not（316 行、4 支 bin、14 個測試、三條 demo pipeline）各做 `&&`、`& wait`、`if`、`!`；N-34 一整條在講它們的結束碼例外。KISS：刪四支，inst 的 argv 直接寫 `sh -c 'aos-exec a && aos-exec b'`；N-34 只剩「述詞例外」一句併進 N-43；aos-tick 留。動：`proto8-1/lib` 四支＋`aos_tasks.py`、`bin` 四支、`tests/test_tasks.py`、`demo/pipeline*`、N-34、proto8-1 README。風險：**翻案**——使用者 10-12 定「四個原語」、10-15 定「stdlib 地位」；aos-par 的「收到訊號轉給子程式」在 sh 要寫 `trap`，原型期可接受。
6. **loop 認得 fsm 的輸出。** 現況：N-44 `stop_on_end`＝loop 看 inst 的 stdout 有沒有 fsm 結束那行（`"end": true`、`from`、`to`），loop 知道 fsm 長什麼樣（跨層）。KISS：寫成 N-12 的通則一句——「可呼叫的程式 stdout 最後一份帶 `"end": true`＝不必再叫我」，loop 只認這一句、不知道 fsm；`stop_on_end` 旗標刪（永遠生效）；N-44 整條併進 N-12。動：`aos_loop.py`、N-12、N-44、`loop.md`、六份 loop.json。風險：哪支 inst 恰好吐 `"end": true` 就會被停——那正是規範的意思。
7. **`aos agent fsm` 與 `aos fsm` 兩個入口。** 現況：agent_lib 的 `fsm [NAME]` 子命令只是「用 frame 找 fsm.json 再呼叫 aos_fsm」。KISS：刪它，loop.json 直接 `aos fsm`，fsm 設定用 stdin／`$ref` 指定義資料夾那份（v3 的 frame.json 拿掉後它本來就沒事做）。動：`aos_agent_lib.py`、六份 loop.json、`agent_lib.md`、`bin/aos` 說明。風險：依 v3 最後怎麼定「定義在哪」。
8. **兩顆真腦。** 現況：`aos_brain_openai.py`、`aos_brain_ollama.py` 都在 lib，ollama 原生只為了 `num_ctx`。KISS：lib 只留 OpenAI 相容一顆；ollama 那支搬到 `demo/fsm/brains/`（跟 fake.py 同級，是「某人的腦」不是函式庫）。動：搬檔、`bin/aos` 的 `brain ollama`、`agent.md` 第三顆那段。風險：低。

## 二、刪（key、旗標、特例）

9. **exit 檔。** 現況：inst 的 `exit`／`exit_append`／`exit_mkdir`、`read_exit()`，N-30 自己說「只是與舊時代的橋樑」，tasks、loop 都改讀 stdout 了。KISS：全刪。動：`aos_inst.py`、`inst.md`、N-30／N-12 的「exit 檔出現也算」句、`demo/once`、`demo/tick` 的 inst.json、`test_inst.py`。風險：無。
10. **inst 的 12 個布林。** 現況：`cwd_mkdir`、`envs_clear`、`*_inherit`×3、`*_append`×3、`*_mkdir`×3、`stderr_merge`，再加三條 Conflict 檢查與 N-26 一整條。KISS：全刪，inst 只剩 `argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`timeout_ms`、`grace_ms`、`id`；要附加寫 `sh -c '… >> f'`、要併 stderr 寫 `2>&1`、要接呼叫者的寫 `/dev/stdout`、要建資料夾寫 `mkdir -p`——全是 POSIX 本來就有的。動：`aos_inst.py`、`inst.md`、N-26 刪、N-43 提 `stderr_inherit` 的句子刪、`demo/tick/inst.json`、測試。風險：低；`/dev/stdout` 在少數情況（pipe 被關）行為怪，原型期不管。
11. **loop 的三個節奏細節。** 現況：`interval_mode: fixed`（連帶 `skipped`）、`ctl_poll_ms`、`error_wait_ms`。KISS：只留 `after`；ctl 每拍讀一次（不另開輪詢）；出錯也只隔 `interval_ms`。動：`aos_loop.py`、`aos_ctl_state.py`（`_MODES`、`skipped`）、`loop.md`、`ctl_state.md`、N-07／N-11 列 `interval_mode` 的字。風險：interval 很長時 ctl 的 stop 要等到下一拍——要當場停就送 SIGTERM，本來就有。
12. **ctl 旗子的 `now`。** 現況：`paused`／`stop` 收 `{"val", "now"}`，`now`＝當場殺＝其實就是送訊號。KISS：只收布林；當場停＝SIGTERM。動：`aos_ctl_state.py`、N-07、daemon 的 stop now 分支、`ctl_state.md` 旗子那列。風險：N-07 使用者 10-12 定；`aos_cli.expand()` 在 ctl 這處用途消失（priority、think 計數還在用）。
13. **ctl 的 `seq`／state 的 `ctl_seq` 回音。** 現況：N-33，只有 daemon 等子 loop「讀到 pause 了才回」在用。KISS：第 4 條做了就沒人用，刪。動：`aos_ctl_state.py`、N-33、N-14「回音以序號為準」句、`ctl_state.md`。風險：依第 4 條。
14. **窗一族裡沒人用的。** 現況：N-15 鎖（沒實作）、N-16 信箱兩形（只用 Maildir）、N-17／N-32 心跳的 `started`／`boot_id`（判死用，沒人讀）。KISS：N-15 刪；N-16 一句「信箱＝Maildir」；心跳只留 `pid`、`beat`。動：NORMS/05、`aos_ctl_state.py`（`proc_started`、boot_id）、`ctl_state.md` 骨架。風險：低；要鎖的時候再寫一條。
15. **狀態值太多。** 現況：loop／daemon state 七態（starting／waiting／running／paused／done／stopping／stopped），table 子項六態。KISS：三態 `running`／`paused`／`done`（過渡態沒人等它）；子項表若第 4 條刪了就沒有六態。動：`aos_ctl_state.STATES`、N-17 末句、`ctl_state.md` 狀態表、測試斷言、demo 印出的字。風險：低。

## 三、跨層偷看／替別層做事的殘留

16. **上層伸手進下層的 frame。** 現況：kernels/llm demo 的 `boss/tools/clerk.json` 在 clerk 的 frame 放一份 boss 的 `brain.json`（呼叫者改被叫者的環境）；paint 的 `--keep`、換腦也靠在下層 frame 放檔。KISS：工具是黑箱 inst（v3 前提 2）；要 clerk 用別的腦就改 clerk 自己的定義（或 clerk 的 brain.json 本身就是閘門）。動：`demo/kernels/llm/boss/tools/clerk.json`、`demo/paint/run.py` 換腦那段、`frame.md`「綁定」段改成只講 history／args。風險：C-46 綁定（概念）不動，只是 demo 不示範「跨層放檔」。
17. **環境變數當呼叫機制。** 現況：閘門沒寫 `mailbox` 就讀 `AOS_KERNEL`、`priority` 讀 `AOS_PRIORITY`，所以 `aos_kernel_judge.py` 跑判官前要「拿掉自己的 AOS_KERNEL」（替判官整理環境＝替別層做事）；demo 的 `aos-demo` 又多 export `AOS_DEMO`。KISS：三個環境變數都刪，`mailbox` 在閘門 inst 裡必填（demo 用 `$ref` 指暫存設定）。動：`aos_gate.py`、`aos_kernel_judge.py`、`demo/kernels/*/gates/*.json`、`demo/bin/aos-demo`。風險：demo 設定多一行；`AOS_DIRNAME`（N-35）是布局慣例不是呼叫機制，照留。

## 四、demo

18. **五份一模一樣的 agent 定義。** 現況：clerk、boss、judges/agent、painter、brush 五個資料夾的 `fsm.json` md5 全同，`cells/` 五格也幾乎全同，各自再帶 loop.json、system.md。KISS：lib 放一份預設定義（`lib/agent/`：fsm.json＋cells＋loop.json），demo 各資料夾只剩 `brain.json`、`system.md`、`tools/`——這正是「定義不變、綁定換掉」要示範的事。動：五個資料夾各刪 7 檔、`demo/fsm`（有內層 think fsm 的那份）留著當巢狀示範、`test_agent.py`／`test_paint_demo.py` 路徑。風險：依 v3「定義資料夾怎麼找」的最後寫法。
19. **五條 demo 跑法＋一個轉派器。** 現況：`demo/run.py` 末尾用 `runpy` 轉派到 fsm／kernels/llm／kernels/general 的 run.py；加 paint 與 proto8-1 三條 pipeline 共八條。KISS：三個 demo——`demo/loop`（現在的 daemon demo）、`demo/agent`（paint 吞掉 fsm demo：畫家→畫筆→報時員，巢狀、綁定、frame 一次看完）、`demo/kernel`（general 一個，llm＝第一段設定）；每個 demo 自己的 run.py，沒有轉派。動：`demo/run.py` 末段、`demo/fsm` 併入 `demo/paint`、`demo/kernels/llm` 刪、`demo/README.md` 重寫、proto8-1 demo 隨第 5 條。風險：`test_agent.py` 借 demo/fsm 的 clerk——改借 paint 的。
20. **`aos-demo` 的第二招。** 現況：`aos-demo x.py`＝跑 demo 裡的腳本（為了 C-50 葉子寫指令名），另一招「其他指令照跑並 export AOS_DEMO」。KISS：只留第一招（第 17 條刪 AOS_DEMO 後第二招沒用）。動：`demo/bin/aos-demo`。風險：無。

## 五、文件（規範條文與實作說明）

21. **條文夾帶沿革。** 現況：幾乎每條 N 都帶「原為…」「原 h3」「10-15 晚使用者『都按照推薦。』，盤點 S1」「推翻 10-14 下午…」；N-43 一條 3 KB、N-28 1.2 KB。KISS：條文只留現行規定一到三句，沿革一律條尾一個連結指 thinking（那裡本來就有原文與決定）。動：NORMS/01～09 全部。風險：改寫時不能動原意；歷史在 git 與 thinking，不會丟。
22. **NORMS.md 三張表。** 現況：主題表＋「條號→檔」表（44 列）＋「各批出處」（10 段）。KISS：只留主題表；條號 grep 就有、出處 thinking 已有。動：`NORMS.md`。風險：無。
23. **08-待定大半是劃掉的。** 現況：11 條裡 6 條整條劃掉（已定、附當時原文）。KISS：劃掉的全刪，剩 5 條活的。動：`NORMS/08-待定.md`。風險：無。
24. **小到不該分檔的分檔。** 現況：`02-設計理念-時空.md`（958 B，3 條）、`09-kernel.md`（1.2 KB，1 條），各自一行檔頭連結、一份 README 佔位。KISS：併回 NORMS.md 主題表下各一段（STRUCTURE 的反向：縮回純值）。動：`NORMS.md`、刪兩檔、`NORMS/README.md`、CONCEPTS 分檔檔頭的連結。風險：使用者 10-15 定「按主題分」——併回仍按主題分段，只是不分檔。
25. **一支程式三處說明。** 現況：檔頭 docstring（最完整）、`lib/x.md`（重講一遍＋沿革）、`lib/README.md` 表格裡每檔一長句（11 KB）。KISS：檔頭＝唯一出處；`lib/x.md` 只留 JSON 形狀與一個例子（prose 刪）；`lib/README.md` 每檔一行＋相依圖＋測試指令（目標 3 KB）。動：`lib/README.md`、11 份 `lib/*.md`。風險：工時大、不難；C-54 說「結構與名字本身就是說明」。
26. **lib 說明裡的沿革句。** 現況：「照 N-12 重做（10-14）」「10-15 收工後瘦身」「`aos_agent_call.py` 10-15 退場」「原本 127／126／125」到處是。KISS：同第 21 條，全刪。動：11 份 `lib/*.md`、各檔頭。風險：無。
27. **proto8/README.md。** 現況：兩個 artifact 連結、restart §3g、「PLAN 擱置」、「之前乾淨的兩個時刻」、規矩兩條。KISS：入口只留一段話＋四行（規範、lib、demo、thinking）。動：`proto8/README.md`。風險：無。
28. **PLAN.md＋PLAN/。** 現況：三檔 12 KB，AI 提案、10-11 擱置、檔頭自己說「高度錯」。KISS：刪（整份 AI 產出；10-12 夜的規矩是只留原文、決定、結論）。動：刪 `PLAN.md`、`PLAN/`、README 連結、wf 索引若有提。風險：使用者 10-11 說「留著當樣本」，10-12 規矩在後——刪前問一句。

## 六、C++ core/ 與 proto8

29. **同一疊東西兩套實作、同一個名字。** 現況：C++ `core/`（exec＝inst、loop、llm＝腦、agent、tick）與 proto8 Python 做的是同一疊；執行檔都叫 `aos`，誰先在 PATH 誰贏，`bin/aos` 檔頭還要解釋「同名不相干」。KISS：一個名字一件事——根 README 與 `core/README.md` 寫明 C++ 那套**封存**（只維持 ctest 綠、不收新功能、不同步 proto8 的規範），proto8 的 `aos` 是日常唯一入口。動：`README.md`（根）、`core/README.md`、`AGENTS.md` 第一段、`wf/INDEX`。風險：鐵律 1 要 ctest 全綠——封存不是刪，照舊 build；真要刪 C++ 是另一次拍板。

## 最小核心：現有規範＋實作從零重寫，只留這幾樣

**規範 7 條**（現在 44 條）：
1. 可呼叫的程式：stdin＝參數、stdout＝結果、stderr＝錯，三者 JSON 串流，半份不算；stdout 最後一份帶 `"end": true`＝不必再叫（N-12＋N-44）。
2. 結束碼 0／非 0，自己的錯一律 1，每層只說自己（N-43）。
3. stderr 一種形狀 `{"error": {"code", "msg"}}`，不放警告（N-29）。
4. 給別人讀的檔先寫暫存再改名（N-05）。
5. 窗：ctl 寫期望、整份就是全部、沒寫＝初始值；state 只有自己寫；會反覆跑的必開兩扇（N-06、N-09、N-19）。
6. fsm：表＝狀態→inst；下一狀態看格 stdout 的 `next`，沒有看表；`end` 到了就結束；出錯 phase 不動往外報（N-36～N-40 五條併兩條）。
7. 大家看同一個 tick 時鐘（N-01）。

**實作 5 支**（現在 lib 24 支＋proto8-1 6 支）：
- `aos-inst`：stdin 一張 inst → 跑一次 → stdout 一份結果（9 個 key，沒有布林）。
- `aos-loop`：拍一個 inst；設定有 `children` 就順便管一群子 loop（daemon 併進來）。
- `aos-fsm`：一拍一格。
- `aos-kernel`：格＋信箱＋問判官；政策全在判官那張 inst（規則判官是預設的一張）。
- `aos-brain`：OpenAI 相容一顆；閘門 `aos-gate` 是它排隊時的包裝。
- 外加 `aos-exec`（v3 語法糖）、`aos-tick`、agent 的五格（think／tool／route／intake／done）。

一句話：**inst 是唯一的東西，loop 讓它反覆，fsm 讓它分狀態，kernel 讓它排隊，其他全是 sh 與 JSON 本來就會的。**

## 不在範圍

概念（CONCEPTS、C 條）不審、不提刪改；TARGET／aos-tree／`$abs_path`／frame.json 已在 inst-exec 第三版；原則稿第 2、4、5、6 條另有人改。
