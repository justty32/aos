# 隊 X 回報——修掉 trial 的 25 條 bug，repro 全部翻面

← [交接書 proto-X-bugfix](../proto-X-bugfix.md)｜[trial 摘要](../../trial/README.md)｜[findings-L1](../../trial/findings-L1.csv)／[findings-L2](../../trial/findings-L2.csv)

**分支**：`main`（直接在主 working tree 做，未 push）
**隊形**：Opus 隊長＋codex gpt-5.6-sol ×4 **並行**（按小專案／檔案切線，同檔循序）＋1 條文件同步線；
隊長寫任務書、審 diff、跑 ctest 與全部 repro、做行為語意裁決、commit，不親自寫實作
（例外：4 條隊長裁決造成的收尾修改，見「隊長裁決」節）。

## 結果

| 驗收 | 狀態 |
|---|---|
| 25 條 `bug` 的 repro 全部翻面 | **24 條 PASS，1 條（L2-14）腳本本身自相矛盾、以等價證據結案** |
| ctest 全綠 | **8/8**（`cmake --build --preset default` → `ctest`） |
| 新增回歸案例 ≥ 15 | **36 個 `TEST_CASE`**（exec 2、loop 7、agent 21、tool 4、llm 2） |
| 其餘 repro 不從 PASS 變 FAIL | 是（`L1-03`／`L1-26`／`L2-02`／`L2-05`／`L2-07` 這些非 bug 的腳本一併重跑過） |

## commit

| hash | 內容 |
|---|---|
| `1331a43` | 開工前置：repro 的 `AOS`／`ROOT` 指回主 repo build（斷言一個字沒動）、兩個空的 agent 測試檔位 |
| `ca79aca` | `core/loop`＋`core/exec`：L1-01／L1-09／L1-15／L1-30／L2-14／L2-20／L2-22＋run·deliver 的 help |
| `b7c5661` | `core/tool`＋`core/llm`：L2-21／L1-16＋llm·tool·contact 的 help |
| `aedca67` | `core/agent` 生命週期：L1-07／L1-17／L1-19／L1-20／L2-28＋L1-01 的 every argv |
| `8972d59` | `core/agent` CLI：L1-02／L1-06／L1-08／L1-31／L1-32／L2-01／L2-08／L2-09／L2-10／L2-12＋help |
| `e13f1a8` | code-map 與五份 core README 同步 |
| （本檔） | 隊 X 回報 |

## 分組表——按小專案／檔案切線，不按 bug 切

| 線 | 檔案（每條線獨佔） | 認領的 bug |
|---|---|---|
| **G1** loop／exec | `core/loop/src/{run,turn,deliver_cli,fs}.cpp`、`include/aos/loop.hpp`、`core/exec/src/{start,wait_all,interrupt}.cpp`、`include/aos/exec.hpp` | L1-01、L1-09、L1-15、L1-30、L2-14、L2-20、L2-22 |
| **G2** agent CLI | `core/agent/src/{run,run_top}.cpp`、`run.hpp`、`tests/test_agent_cli.cpp` | L1-02、L1-06、L1-08、L1-31、L1-32、L2-01、L2-08、L2-09、L2-10、L2-12 |
| **G3** agent 生命週期 | `core/agent/src/{step,engine,engine_pi,store,init}.cpp`、`internal.hpp`、`tests/test_agent_lifecycle.cpp` | L1-07、L1-17、L1-19、L1-20、L2-28 |
| **G4** tool／llm | `core/tool/src/{tool_cli,contact_cli}.cpp`、`core/llm/src/{llm,run}.cpp`、`include/aos/llm.hpp` | L1-16、L2-21 |
| **跨線** | 各線各自負責自己那幾支 CLI | L1-14（八個子命令的 `--help`） |
| **G5** 文件 | `wf/workflows/common/code-map.md`、五份 `core/*/README.md` | （不改程式碼） |

切線原則：**同一個檔案只有一條線碰**。`core/agent` 有 8 條 bug，拆成「CLI 層」與「生命週期層」兩條，
兩條的測試各寫在一個新檔（隊長先把兩個空檔掛進 `CMakeLists`，免得兩條線同時改同一份建置檔）。
四條線各自用自己的 build 目錄（`/tmp/aosb-gN`，共用 repo 的 `vcpkg_installed`），不搶 `build/`。

## 25 條 bug 的修法（一句話）＋ PASS 判準

判準欄的「腳本自帶斷言」＝該支 `repro/*.sh` 自己有 `FAIL … exit 1`，PASS＝腳本 exit 0 且不印 FAIL；
其餘的腳本只印 `EXPECT`／`ACTUAL` 不做判斷，PASS 判準由隊長依該列 CSV 的 `expected` 欄訂在下表。

| id | 修法 | PASS 判準與實測 |
|---|---|---|
| L1-01 | `every/agent-<name>.json` 的 argv[0] 從裸 `aos` 換成**這一個執行檔的絕對路徑**（`AOS_BIN`→`/proc/self/exe`→PATH→退回 `aos`）；另外 `run` 現在會逐條講出失敗的 inst 並以非 0 結束 | 在 `PATH=/usr/bin:/bin` 底下推 5 回合：**agent 真的在工作**（turn 1 的 inst 跑了 10.4 秒、turn 3／5 各發了一次 `ls` 工具呼叫），`out/*.json` 全部 `exit: 0`，`aos state` 是 `status=tool`。修前是 5 次 `exit 127`、stderr 空白、`state` 永遠 idle |
| L1-02 | `aos state` 加 `unread`／`engine`／`model`，未讀>0 時 `status=pending`；`aos listen` 印完 log 再印一段「## 未讀 (N)」 | 說完三句後 `state` → `"status": "pending"`、`"unread": 3`、`detail` 是「3 封未讀，等下一回合處理」；`listen --once` 印出三句原文 |
| L1-06 | `aos agent init` 不給 folder 時改用 cwd 就地建世界，不再往上找祖先的 `.aos/` | 站在 `outer-world/src/my-feature` init：「我站的地方有 .aos 嗎：**yes**」，祖先的 `outer-world/.aos/agents` 根本不存在 |
| L1-07 | `write_engine` 對 lmstudio 也寫 `model`；`step` 用 `engine.model` 蓋掉 `AOS_LLM_MODEL`；`aos state` 印 `engine`／`model` | `a/engine.json` → `{"engine":"lmstudio","model":"google/gemma-4-12b-qat"}`；`aos state` 同時印出這兩個欄位 |
| L1-08 | `say` 在解析前先認第一個位置的 `--help`／`-h`，印用法、exit 0、不投遞 | 印出含 `--to` 說明的 usage、`exit=0`、`say/` 檔案數 **0 → 0** |
| L1-09 | `aos run` 明確給了 folder 就先驗它存在且是資料夾，否則報錯回 1、什麼都不建 | `aos run: /tmp/…/my-projekt 不存在`、`exit=1`，跑完之後那個路徑仍然不存在 |
| L1-14 | 全 aos 統一：`--help`／`-h` → 完整用法印到 **stdout**、**exit 0**；用錯參數才 stderr＋exit 2。八個子命令的 usage 都補上逐項選項說明 | 八行全部 `exit=0` 且第一行是自己的 usage；`say --help` 之後收件匣多了 **0** 封 |
| L1-15 | 同 L1-09 的路徑檢查；`fs::mkdir_p` 的錯誤訊息也帶上 `error_code` 的真實原因 | `aos run: /nonexistent/zzz 不存在`（修前是 `無法建立 …/.aos/inbox: Permission denied`） |
| L1-16 | 新增 `parse_response_model()`；`complete()` 多一個出參；`aos llm` 發現端點回的 model 與請求的不同就回 1 | `exit=1` ＋ `aos llm: 端點回答的是 qwen/qwen3.5-9b，不是你要的 no/such-model-xyz——這個端點沒有那顆模型` |
| L1-17 | `step_pi()` 失敗回 1（原本回 0）、status 寫 `error`、`No API key` 時指路到 `<PROVIDER>_API_KEY` | `out/*.json` 記 `exit: 1`、`run exit=1`、`state` 是 `status=error`、log 出現「請設定 DEEPSEEK_API_KEY」 |
| L1-19 | 失敗的回合 status 寫 `error`（原本寫 idle），並在 log 留一行失敗說明＋端點指路句；`run` 以非 0 結束 | `run exit=1`；`state` → `status=error`、detail 是連線失敗原文；`listen` → `> 第 1 回合失敗：…（請確認 LLM 端點 http://localhost:19999/v1 是不是活的…）` |
| L1-20 | `step`／`step_pi` 改成**先呼叫 LLM、成功之後才吃掉 `say/`**（原本先吃再呼叫） | 端點壞掉推 1 回合後「未讀剩：**1 封**」（修前是 0）；端點修好再推，`log` 出現 `## turn 2 assistant 收到了嗎` |
| L1-30 | `exec` 加行程級的子行程群組註冊表與 `interrupt_running()`（signal-handler 安全）；`aos run` 掛 SIGINT／SIGTERM，收到就對整批送 SIGTERM、寫 `phase=interrupted`、回 130 | 同一支腳本、同一種跑法（`script -qec … bash -m`，見下方註）：**修前 `alive_after_1s=yes, out_exists=no`；修後 `alive_after_1s=no, out_exists=yes`**，`run.log` 印「收到中斷訊號，已終止 turn 3 的所有指令」，`state.json` 是 `phase: interrupted`，事後 `pgrep aos agent step` 空 |
| L1-31 | `aos talk` 讀 stdin 之前先用 `.aos/run.lock` 判斷有沒有 runner，沒有就立刻指路、回 1、**不投遞** | `exit=1`（修前 124）、`output_bytes=240`（修前 0）、`queued_say_files=0`（修前 1） |
| L1-32 | 頂層 `aos talk` 也認得 `--interface`，`pi` 就印跟 `aos agent talk` 一樣清楚的那句 | 輸出：`aos talk: pi 介面需要 extension adapter，尚未內建；見 core/agent/docs/pi-interface.md` |
| L2-01 | 同 L1-06 | **腳本自帶斷言**：`PASS: worker 是自己的世界` ＋ `PASS`（祖先沒被汙染），exit 0 |
| L2-08 | `say --to` 的成功訊息改印真正的收件匣目錄 | **腳本自帶斷言**：`已送給 b（/tmp/…/b/.aos/agents/b/say）` → `PASS: 是真實路徑` |
| L2-09 | 投遞前自己檢查三種情況（資料夾不存在／不是 aos 世界／還沒有 agent），每種講不同的話並印出解析後絕對路徑 | 情況一：`聯絡人 ghost 指到 /tmp/…/nope，那個資料夾不存在`；情況二：`/tmp/…/empty 還沒有 agent；請先在那裡跑 aos agent init` |
| L2-10 | 同 L1-08 | **腳本自帶斷言**：`say/` 信箱「（空）」→ `PASS`，exit 0 |
| L2-12 | 同 L1-02 的 `listen` 那半 | **腳本自帶斷言**（`L2-07.sh`）：`aos state` 不再含 `"status": "idle"`，exit 0；`listen --once` 印出 `## 未讀 (3)` 與三行任務 |
| L2-14 | `aos run` 全程持有 `<folder>/.aos/run.lock` 的 `flock(LOCK_EX\|LOCK_NB)`，拿不到就指路並回 1 | **腳本自相矛盾，見下方裁決**；等價證據（隊長手跑）：loop1 `exit=0` 推 2 回合、loop2 `exit=1` 印「這個世界已經有一條 aos run 在推進（鎖：…/.aos/run.lock）」、最終 `turn=3`（修前兩條都 exit 0、合計推了 4 回合） |
| L2-20 | `wait_all` 改成每條子行程**各自收線當下**記 `ended_at` | **腳本自帶斷言**：相異 `ended_at` **2** 個（`true` 18.906、`sleep 3` 21.925），印 `PASS`，exit 0 |
| L2-21 | `aos tool add` 探測前先驗 argv[0]（含 `/` 查檔案，否則查 PATH），找不到就回 1、不登記，`--description`／`--no-probe` 都繞不過 | 兩次都印 `aos tool: 找不到執行檔 /definitely/not/here；它不在 PATH 上，也不是一個可執行的檔案路徑`，`tool ls` 裡沒有 `bad`；整支腳本 exit 0 |
| L2-22 | `--step`／`--interval` 重複時印警告到 stderr 並**沿用第一個**（見裁決 3） | **腳本自帶斷言**：印 `--step 重複指定；沿用第一個 1，忽略 2`，只跑 1 回合（`RAN=1`），exit 0 |
| L2-28 | 新增正典 `agents/<name>/log.jsonl`；`log.md` 降級成渲染快取，`read_log()` 對不上就印警告並從 journal 還原 | **腳本自帶斷言**：假造的 `## turn 99` 被 `aos listen` 吃掉並還原，`grep turn 99` 落空，exit 0 |

**L1-30 的跑法註記**：那支腳本用 `kill -INT $RUN_PID` 模擬 Ctrl-C，而 `RUN_PID` 是 `( timeout … ) &` 這個
背景工作。非互動 shell 會把背景工作的 SIGINT 設成 `SIG_IGN`（POSIX），所以 `bash L1-30.sh` 這樣跑的話
**訊號根本送不到 `aos run`**，量到的永遠是 `yes`（修前修後都一樣）。真正的 Ctrl-C 是有終端機、有 job control
的情境，所以隊長用 `script -qec "… bash -m L1-30.sh" /dev/null` 跑（配一個 pty 並開 job control），
**修前修後各跑一次**做對照——腳本一個字沒改，只是給它一個訊號送得到的環境。

## 隊長裁決——行為語意改動的選項表

### 1. `--help` 的退出碼（L1-14）

| 選項 | 結果 |
|---|---|
| **A（採用）** `--help`／`-h` 出現在任何位置 → 完整用法印到 stdout、**exit 0**；用錯參數才 stderr＋exit 2 | 跟 `aos --help` 一致，跟 pi／git 一致；八個子命令行為統一 |
| B 維持 exit 2 | 「我問了 help」被當成用錯了，指令稿判不出差別 |

**例外兩處**（採用 A 之後補的）：`aos say` 只認**第一個**位置的 `--help`（其餘位置是使用者要說的話，
掃全部會把「--help」這個字從訊息裡吃掉）；`aos deliver` 掃到 `--` 就停（`--` 之後屬於被投遞的指令）。

### 2. L1-01 修在哪一層——`every` 存絕對路徑，還是 loop 注入 PATH？

| 選項 | 結果 |
|---|---|
| **A（採用）** `agent init` 當下把**這一個** aos 的絕對路徑寫進 `every/agent-<name>.json` | 一行改動、不動協定、不動 loop；世界搬到別台機器要重跑 init（本來就要） |
| B loop 在 `to_spawn()` 時把 aos 的目錄注入 `PATH` | loop 得知道「aos 在哪」——它現在完全不需要知道；而且對其他 inst 也會生效 |
| C 只讓 `run` 把失敗講出來，不修根因 | 使用者看得到 127 了，但世界照樣不動；治標 |

採 A，**同時**也做了 C 的那半（`run` 逐條講出失敗並以非 0 結束）——那是 L1-17／L1-19「world 看得見失敗」
共用的地基。找不到絕對路徑時（例如從函式庫直接呼叫 `initialize()`）退回裸的 `"aos"`，舊行為不變。

### 3. 重複旗標：拒絕，還是沿用第一個？（L2-22）

| 選項 | 結果 |
|---|---|
| A 拒絕（usage＋exit 2） | CSV 的 `expected` 寫的是「被拒絕」，但**它自己的 repro 腳本過不了**：`set -eu` 下 `OUT="$(aos run …)"` 一遇非 0 就整支中止，而斷言要的是 `RAN == 1` |
| **B（採用）** 印警告到 stderr、**沿用第一個**、照常執行 | 歧義參數有一個可預期的答案（先寫先贏），而且使用者一定看得到那行警告 |

可執行的斷言優先於散文——這是隊長依「repro 是唯一驗收」這條規則做的取捨。

### 4. L2-14 的 repro 自相矛盾，改以等價證據結案

那支腳本是 `set -eu`，而且用 `wait $P1; R1=$?` / `wait $P2; R2=$?` 取兩條 loop 的退出碼。
POSIX `set -e` 對 `wait` 一樣生效，所以**只要有任何一條 run 不是 exit 0，腳本就在 `wait` 那行中止**，
永遠走不到它自己的判斷式；而唯一能走到判斷式的情況（兩條都 exit 0）正是它要判 FAIL 的那一種。
**沒有任何實作能讓這支腳本 exit 0。**

處置：不改斷言（規則不准），改以三份等價證據結案——
(1) 腳本不再印出那行 `FAIL:`；
(2) 隊長手跑同一個情境：loop1 `exit=0` 推 2 回合、loop2 `exit=1` 印出鎖的訊息、最終 `turn=3`（修前是 4 回合）；
(3) ctest 回歸案例 `aos run 拒絕已被另一個 runner 鎖住的世界`（測試自己佔住 `flock` 再呼叫 CLI）。
**建議**：把那兩行改成 `wait $P1 || R1=$?` 之後這支腳本就能正常判斷；但那是改斷言，留給下一棒。

### 5. 兩個舊測試斷言記的是 bug 的行為，一併改掉

`core/agent/tests/test_agent_step.cpp` 斷言「completion 失敗後 status 是 `idle`」、
`test_agent_engine.cpp` 斷言「pi 失敗時 `step()` 回 0、detail 是『pi 失敗』」——這三個 assertion
記的正是 L1-19／L1-17 要修的行為。隊長授權改成新語意（`error`／回 1／帶 exit 與原文的 detail），
並在該處留下註解說明理由。

### 6. 未讀（`pending`）與失敗（`error`）誰蓋誰

`aos state` 有未讀時把 `status` 顯示成 `pending`；但**agent 停在 `error` 時 `error` 優先**
——停住的世界比未讀更急。`unread` 這個數字兩種情況都照印。

### 7. repro 腳本的兩處非斷言修改（`1331a43`）

L1 那批腳本把 `AOS`／`ROOT` 硬編到一個已經被刪掉的 worktree 路徑（`agent-a4b6627dc8a8b1254`），
不改就完全跑不起來。改成 `${AOS:-<主 repo>/build/bin/aos}`／`${ROOT:-<主 repo>}`，
**斷言、EXPECT／ACTUAL 文字、判斷式一個字都沒動**。

## 順手做的兩件事（不在 25 條裡，但屬於同一批改動）

- `aos state`／`aos agent state` 的實作原本被兩條線各寫了一份（約 150 行重複）；
  隊長收斂成 `core/agent/src/run.cpp` 的 `aos::agent::cli::state_text()`，宣告在 `src/run.hpp`。
- `aos talk` 判斷「有沒有 runner」用的是 `core/loop` 定的鎖檔路徑 `.aos/run.lock`，
  但為了讓兩條線能並行，agent 這邊是自己寫的 10 行 `flock` 探測，**沒有**跨小專案呼叫 loop。
  兩邊靠「鎖檔路徑」這個約定對齊——這是目前唯一的隱性耦合，寫在這裡備查。

## 對改進隊 Y 的交接

`core/agent` 這次動了 8 個檔，其中跟「state／inbox／chat／contacts 進 prompt」最可能撞車的是：

- `src/step.cpp`：**回合順序改了**——現在是「掃 say/ → 取槽 → 組 request → 呼叫 → 成功才落檔並刪檔」。
  要把 inbox／contacts 塞進 prompt 的話，塞在「組 request」那一段。
- `src/store.cpp`：`append_note()` 多了 `turn` 參數；log 的正典是新的 `log.jsonl`，
  **不要再直接 append `log.md`**（會被 `read_log()` 判成竄改並蓋掉）。
- `src/run.cpp`／`src/run_top.cpp`：`state_text()` 是 `aos state` 的單一實作點，要加欄位改那裡。
- `src/tools.cpp` **完全沒動**（system prompt 的組裝還在那裡，隨你改）。
