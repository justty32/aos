家機 `~/aos-home` 更新五次：早上到 repo `88ea321f4`（install.py、kernel.json 補思考程度、ann 照 start-api 範本換、保留 model=sol、sol 驗四題，線 top-1121-homeup）；上午再到 `5a99e1320`（ann 改動態連結 agent-fsm 的格程式、刪夾裡 9 個舊抄本、sol 驗九次含 /compact 先清工具輸出，線 top-1121-homeup2）；中午到 `97d4abc16`（hook 換新格式：ann 的 hooks.json→hookeds.json、kernel 加 interfaces.json／kernel_hooks.json／kernel_hookeds.json、stack 的 hooks/→hookeds/，4 個 hook 一個不少，sol 驗五次，線 top-1121-homeup3）；下午到 `2060ee9d5`（只跑 install.py、樹裡不改檔，sol 答一句、`aos-gdb --def-hooks` 在活樹列得出 13 點，線 top-1121-home4）；傍晚到 `83e6fa5e3`（只改三支指令的 `--help` 說明、只跑 install.py，沒起樹，線 top-1121-helpfix）；前四次都關回原狀，第五次沒起樹。

← [2026-11-21](README.md)｜前情：[aos-hook-fire換-1121](aos-hook-fire換-1121.md)、[llm-effort-1121](llm-effort-1121.md)、[tool-desc-瘦身-1121](tool-desc-瘦身-1121/)、[aos-agent-預設目標-1121](aos-agent-預設目標-1121.md)｜給使用者看的過程頁：`~/Desktop/aos-home更新過程-1121.html`

## 授權

使用者 11-21 當場：「可以開始改，改好後去幫我把~/aos-home更新一下，把更新過程寫成html放到桌面」「好，install.py你跑就行」。

## 做了什麼

1. 開工核對：沒有指向 `~/aos-home` 的行程（表上四隻都 `sleeping`，記的 daemon pid 已不在）；repo 工作樹乾淨，HEAD `88ea321f4`。
2. 在 proto8 跑 `python3 install.py`：30 支指令（9 C++、21 Python）、`py/` 587 檔與 12 個 C++ 函式庫進 `lib/`，清掉 22 個舊檔（含 `hook_fire`）。跑完寫 `~/.aos/scratch/top-1121-homeup/install-done`。
3. 逐檔比 `~/aos-home` 與 `templates/start-api/`（JSON 用 `json.load` 比內容）。使用者那份的 JSON 全是 `json.dumps(indent=2)` 的排版；內容上屬於他自己的只有 ann 的 `llm.json`（`model: sol`）和 kernel.json 裡範本沒有的包。其餘差異都是範本這兩天的新東西。
4. 改檔（每個先備份成 `<檔>.bak-1121b`；早上的 `kernel.json.bak-1121` 沒動），JSON 照他的縮排 2 格寫回。

| 檔 | 改了什麼 |
|---|---|
| `llm/kernel.json` | 頂層在 `endpoint` 後加 `reasoning_effort_levels`；luna、terra、sol、astra 在 `summary` 前加 `"api": "responses"`、`reasoning_efforts`；luna 的 summary 換成範本那句。其他包與鍵不動 |
| `agents/ann/loop.json` | 照範本：起停改叫 `aos-hook fire -q --agent`，多 before_run／after_run 與兩個旗標條件 |
| `agents/ann/interfaces.json` | `llm_keys` 多 `reasoning_effort` |
| `agents/ann/hooks.json` | 只差 description |
| `agents/ann/tools.json`、`brain.py`、`llm_settings.py`、`system.txt`、`README.md` | 照範本逐字抄（四支 self 工具關掉、思考程度進信、系統提示指知識庫） |
| `perm/loop.json` | 照範本（loop 層 hook 點）；權限站沒掛 |

沒改：ann `llm.json`；`env.sh`、樹根 `README.md`、`root/`、`llm/` 其餘、`perm/kernel.json`、ann `hook_points.json`（內容同範本，只差排版）。

5. `aos-hook check --agent ~/aos-home/agents/ann` → `ok: 11 points from 2 declarations, 4 hooks from 1 lists`；`grep -rl --include=loop.json -F hook_fire ~/aos-home` 沒有結果。
6. 起樹（清掉繼承的 `AOS_*`，`source env.sh`，背景 `aos-exec root`，輸出寫暫存區）；四隻都 `running`。驗完 `aos-daemon-ctl -d .stack shutdown`，根行程退出、沒有殘留行程，表上四隻回 `sleeping`。

## 驗證數字（sol，共 4 次呼叫）

| # | 問 | 答 | reasoning_effort | prompt_tokens | cached_tokens | reasoning_tokens |
|---|---|---|---|---|---|---|
| 1 | pong | pong | — | 5,962 | 0 | 0 |
| 2 | 2+3 | 5 | — | 5,983 | 5,888 | 0 |
| 3 | 7*6 | 42 | high | 6,004 | 5,888 | 0 |
| 4 | 1～1000 被 3 或 5 整除但不被 15 整除 | 401（對） | high | 6,049 | 5,888 | 28 |

- 對照：昨天同一隻 ann 的 prompt_tokens 是 12,646（工具瘦身前）。
- 第 3、4 筆 llm kernel 帳本那行有 `"reasoning_effort": "high"`；換程度後快取照中（configuration_update 的效果）。
- `llm rm reasoning_effort` 後 aos-agent 自己收掉 stack 的覆蓋檔，`llm` 只剩 `model=sol`。
- 省略：在 `.stack/procs/ann` 不設 `AOS_DAEMON`，`aos-agent ctl where` 印出 ann 的 stack、`aos-agent history ls -3` 列最後三則；在樹根不給 `-d`，`aos-agent -t ann ctl where` 報 `DaemonMissing`（設計如此）。
- 沒設 `LITELLM_KEY`，代理不帶金鑰照收。

## 替使用者做的選擇

1. JSON 照他那份的縮排 2 格寫回，不用範本的單行寫法。
2. ann 保留 `model=sol`，其餘照範本換，含 `tools.json`（ann 也變 36 支，self_llm 等四支關掉）。
3. `perm/loop.json` 沒在用也照範本換。
4. luna summary 換成範本那句。
5. ann 的 `README.md` 抄 HEAD 那份；同時有別的線在工作樹改範本那份（「40 支」改「36 支」），沒抄未交的版本。
6. ann 歷史留下這次的 4 問 4 答（第 9～16 則）。
7. 起樹輸出寫暫存區，不寫樹裡的 `root.log`。

## 沒做、留給使用者

- gpt 包要不要改成「設了程度才走 responses」（現在一律走 `/v1/responses`）。
- ann 要不要打開那四支 self 工具。
- repo 裡 `wf/temp` 兩份暫存隊員定義還指 `hook_fire`（不在 `~/aos-home`）。

## 第二次更新（到 `5a99e1320`，線 top-1121-homeup2）

授權（使用者 11-21 當場）：同上兩句；刪檔另有「那9個檔可以刪」（範本那 9 個，已刪）與「aos-home那9個也刪。」——只限 `~/aos-home/agents/ann/` 的 `act.py`、`atomic_file.py`、`brain.py`、`cell_common.py`、`compact.py`、`idle.py`、`llm_settings.py`、`wait.py`、`hook_points.json`。

### 做了什麼

1. 開工核對：沒有 aos 行程，表上四隻 `sleeping`（記的 daemon pid 已不在）；repo 工作樹乾淨，HEAD `5a99e1320`。
2. proto8 跑 `python3 install.py`：30 支指令（9 C++、21 Python）、`py/` 590 檔與 12 個 C++ 函式庫進 `lib/`，清掉 21 個舊檔；`lib/aos/agentlib/tool_clear.py`（compact 第 1 刀要的）在。
3. 全樹逐檔比 `templates/start-api/`（JSON 比內容）：不同的只有 ann 的 `fsm.json`、`interfaces.json`、`README.md`、`llm.json`（他的 `model=sol`）與樹根 `README.md`；多出來的是那 9 個檔與 `root.log`。前三個跟 `88ea321f4` 的範本內容一樣（ann 這兩份沒被使用者改過）；樹根 README 跟 `88ea321f4` 一字不差。
4. 換檔（先備份 `<檔>.bak-1121c`）：

| 檔 | 改了什麼 |
|---|---|
| `agents/ann/fsm.json` | 照範本抄：四格 `argv` 指 `{"$env": "AOS_HOME", "$path": "/templates/agent-fsm/<格>.py"}` |
| `agents/ann/interfaces.json` | `hook_points` 的 `"hook_points.json"` 換 `{"provider": "agent-fsm"}`；照他的縮排 2 格寫回 |
| `agents/ann/README.md`、樹根 `README.md` | 照範本抄 |

5. 刪前查那 9 個檔：逐個在 git 歷史找一模一樣的版本，8 支 `.py` 都等於 `f94b060b7^:proto8/templates/start-api/agents/ann/<檔>`（其中 `brain.py`、`compact.py`、`idle.py` 跟現在的 agent-fsm 不同，差的是 compact 第 1 刀）；`hook_points.json` 位元組對不上（他那份是縮排 2 格），JSON 內容等於 `b1c075f60` 起的範本與現在的 agent-fsm。都沒有使用者自己的改動。
6. 起樹（清掉繼承的 `AOS_*`、`source env.sh`、背景 `aos-exec root`，輸出寫 `~/.aos/scratch/top-1121-homeup2/`），驗完（見下）才刪那 9 個檔，刪完再問一句。`aos-hook check --agent ~/aos-home/agents/ann` 換檔後、刪檔後都是 `ok: 11 points from 2 declarations, 4 hooks from 1 lists`。
7. `aos-daemon-ctl -d .stack shutdown`，根行程退出、沒有殘留行程，表上四隻 `sleeping`。
8. 桌面過程頁加「第二次更新」一節，最上面的結論改成涵蓋兩次。

### 驗證數字（sol，共 9 次呼叫）

| # | 題 | prompt_tokens | cached_tokens | reasoning_tokens |
|---|---|---|---|---|
| 1 | A：讀 ann 的 `README.md`、`system.txt`（叫工具） | 6,102 | 5,888 | 0 |
| 2 | A：回答 | 10,822 | 0 | 25 |
| 3 | B：17×3 → 51 | 10,877 | 10,624 | 0 |
| 4 | C：列 `agents/ann`、`llm`（`max_items` 1000 → `ArgumentsBad`） | 10,919 | 6,016 | 0 |
| 5 | C：改 500 重列 | 11,164 | 0 | 16 |
| 6 | C：回答「33；9」（對） | 11,529 | 11,008 | 0 |
| 7 | `/compact` 摘要 | 3,326 | 1,408 | 0 |
| 8 | D（刪檔後）：再列 `agents/ann` | 6,956 | 3,712 | 0 |
| 9 | D：回答「24 個、act.py 不在」（對，含備份檔） | 7,173 | 3,712 | 0 |

- 在 `.stack/procs/ann`、不設 `AOS_DAEMON`：`aos-agent history ls -n 3` 列第 21～23 則；`history ls -3` 報 `FlagUnknown unknown flag -3`。
- `/compact`：壓前 31 則、工具輸出 7 則，清了讀 README（8,513 字）與 system.txt（1,474 字）兩則；`history_removed.jsonl` 多 2 列 `op: "clear_tools"`（line 19、20）與 32 列 `op: "compact"`；`compact.json` 記 `cleared: 2, cleared_chars: 9987, replaced: 32, summary_chars: 3625`。ann 夾裡舊的 `compact.py` 沒有清這一步，所以這也證明格程式讀的是 `$AOS_HOME` 那份。
- 剛拿到工具結果的那一輪（第 2、5 筆）快取 0，其他輪都中；只記下，沒追。

### 替使用者做的選擇

1. **在他的 ann 上真的壓了 `/compact`**：先備份 `.stack/procs/ann/history.jsonl.bak-1121c`（開工前 16 則）與 `history.jsonl.bak-1121c-precompact`（壓前 31 則）；ann 現在的對話是摘要＋壓完那句＋刪檔後一問一答。
2. 為了有東西清，讓 ann 讀兩個檔（它自己的 README、system.txt）、列兩個夾，沒塞別的。
3. `interfaces.json` 照他的縮排 2 格寫回；`fsm.json` 新範本本來就是縮排 2 格。
4. 樹根 `README.md` 也換了（第一次沒換；這次 ann 那列說明跟實際不符）。
5. 先換檔、驗問答／工具／`/compact`，再刪 9 個檔；9 個檔沒另留一份，repo 裡有一模一樣的版本（還原指令寫在過程頁）。
6. 驗證的 4 題與 `/compact` 留在 ann 歷史；起樹輸出寫暫存區；沒設 `LITELLM_KEY`。

### 沒做

- kernel 的 `kernel.py` 只隨 install 裝好，`perm/`、`llm/` 沒改成用它編。
- sol 的 `ls` `max_items` 寫 1000 被拒（工具上限 500）、第 2、5 筆快取 0：只記。
- 要注意的（寫進過程頁）：ann 的格程式現在直接讀 `$AOS_HOME/templates/agent-fsm/`，他的 `AOS_HOME` 就是 repo 的 `proto8/`，有人改那幾支還沒交時 ann 會吃到半成品。

## 第三次更新（到 `97d4abc16`，hook 換新格式，線 top-1121-homeup3）

授權（使用者 11-21 當場）：同上兩句；頂層事先說過這一刀交了會裝新版、換 ann 的檔、搬 stack 裡的 hook，他沒反對。刪檔沒有新授權，施工紀錄（[hook-新格式施工 03](hook-新格式施工-1121/03-保不住的行為與活樹更新.md)）寫「刪」的地方一律改名留底 `.bak-1121d`。

### 做了什麼

1. 開工核對：沒有 aos 行程；repo 工作樹乾淨，HEAD `97d4abc16`。舊 lib 跑 `aos-agent -d .stack --target ann hook ls -l` 直接 `PointsBad … templates/agent-fsm/hook_points.json: No such file`（03 預告的那個壞法）。
2. 盤點：ann 定義的 `hooks.json` 掛 4 個（`context_wrap` on_clock every_ms 5000＋config、`timer` on_clock 300000、`mail_notify` on_clock 60000、`brain_notify` brain_failed condition BudgetMissing/BrainFailed），全寫 `on_error: continue`，沒有關掉的；`.stack/procs/ann/` 沒有 `hooks.json`、沒有 `hook_*.flag`，只有工作夾 `hooks/`（context_wrap、mail_notify、timer）。其他 stack 沒有 hook 相關的檔。全樹逐檔比 `templates/start-api/`（JSON 比內容）：要換的檔都跟 `5a99e1320` 的範本內容一樣，使用者自己的只有 ann `llm.json`（`model=sol`）；`llm/kernel.json` 跟現在的範本內容一樣、本來就沒有 `hooks` 鍵。
3. proto8 跑 `python3 install.py`：30 支指令（9 C++、21 Python）、`py/` 590 檔與 12 個 C++ 函式庫進 `lib/`，清掉 25 個舊檔。
4. 換檔（先備份 `<檔>.bak-1121d`；JSON 內容照範本、照他的縮排 2 格寫）：

| 檔 | 做了什麼 |
|---|---|
| `agents/ann/interfaces.json` | 最外層 `hooks`（loop_hooks.json＋agent-fsm/hooks.json 兩個指示詞）、`hookeds: "hookeds.json"`；aos-agent 格不再有 hooks／hook_points |
| `agents/ann/hookeds.json`（新） | 舊 hooks.json 的 4 格拿掉 `on_error`（等於範本） |
| `agents/ann/hooks.json` | 改名 `hooks.json.bak-1121d`（沒另外再抄一份） |
| `agents/ann/loop.json` | 起停 `aos-hook fire -q --stop-on-nonzero --def`；before_run／after_run 不接 |
| `agents/ann/README.md`、樹根 `README.md` | 照範本抄 |
| `llm/interfaces.json` | 多 `hooks`、`hookeds`、`"kernel": {}` |
| `llm/`、`perm/` 的 `kernel_hooks.json`（逐字抄）、`kernel_hookeds.json`（新） | 範本那份 |
| `perm/interfaces.json`（新）、`perm/loop.json` | 照範本 |

5. 搬 stack：沒有 `<stack>/hooks.json` 要轉；`.stack/procs/ann/hooks/` 先抄成 `hooks.bak-1121d/` 再改名 `hookeds/`。`history.jsonl` 備份 `history.jsonl.bak-1121d`（開工前 6 則）。
6. 起樹（清掉繼承的 `AOS_*`、`source env.sh`、背景 `aos-exec root`，輸出寫 `~/.aos/scratch/top-1121-homeup3/`）：表上四隻 `running`，llm kernel 的 `_sweeper` 也 `running`。perm 不在板子上，改在暫存區另開 stack 起（`AOS_DAEMON` 指一個空夾當下一站；不給的話 kernel 第一輪報 `DaemonMissing no next station`）：`running`、起停兩點過、TERM 後 `stopped`。
7. `aos-daemon-ctl -d .stack shutdown`，根行程退出、沒有殘留行程，表上四隻 `sleeping`。
8. 桌面過程頁加「第三次更新」一節，最上面的結論改成涵蓋三次。

### hook 清單對照

起樹前、起樹後 `hook ls -l` 都是 brain_notify、context_wrap、mail_notify、timer 四個，參數同更新前，來源 `agents/ann/hookeds.json`。ann 沒有工具上的 hook（before_tool／after_tool 沒掛），「工具 hook 有被叫」沒得驗；改看 on_clock：起樹那刻 `hookeds/` 下三個工作夾的 `event.json`、`on_clock.json` 都更新（`on_clock.json` 是新格式 `{"loop": [boot_id, pid, ticks], …}`），mail_notify 的 `notified.json` 照用。

行為：4 個都在不能攔的點，舊的 `on_error: continue`＝失敗只 warning，新版這些點失敗也只 warning——對 ann 沒變。

### 驗證數字（sol，共 5 次呼叫）

| # | 題 | prompt_tokens | cached_tokens | reasoning_tokens |
|---|---|---|---|---|
| 1 | pong → pong | 7,205 | 0 | 0 |
| 2 | 2+3 → 5 | 7,229 | 7,040 | 0 |
| 3 | 用 ls 列 `.stack/procs/ann/hookeds`（叫工具） | 7,274 | 0 | 0 |
| 4 | 回答「context_wrap, mail_notify, timer」（對） | 7,343 | 7,040 | 0 |
| 5 | reasoning_effort=high：401（對） | 7,390 | 7,168 | 14 |

- 第 5 筆帳本記 `reasoning_effort: high`；`llm rm reasoning_effort` 後 stack 覆蓋檔被收掉，`llm` 只剩 `model=sol`。
- 在 `.stack/procs/ann`：`aos-agent history ls -n 3` 列第 14～16 則；`-3` 照舊 `FlagUnknown`。
- 沒寄 `/compact`。ann 的 stderr 沒多任何一行。

### 替使用者做的選擇

1. 「刪舊清單」改成改名留底；舊旗標檔他的 stack 本來沒有。
2. JSON 照他的縮排 2 格寫（範本是單行／縮排 1 格）；`kernel_hooks.json` 逐字抄。
3. perm 不替他掛上板子，在暫存區另開 stack 驗。
4. 不為了驗工具 hook 臨時替 ann 掛一個；用 on_clock 工作夾證明 hook 在跑、用的是新夾。
5. 驗證的 5 題留在 ann 歷史（現在 16 則）；起樹輸出寫暫存區；沒設 `LITELLM_KEY`。

### 留著沒刪

`agents/ann/hooks.json.bak-1121d`、`.stack/procs/ann/hooks.bak-1121d/`、前幾次的 `.bak-1121`／`.bak-1121b`／`.bak-1121c`、樹根 `root.log`。新版都不讀（`hooks.json` 改名是因為新版的 `hooks.json` 是宣告，原名留著會誤導人；新程式只照 interfaces.json 指的名字讀，`*.bak-*` 不會被當清單）。

### 沒發現新版程式的問題

照 03 的步驟走完沒有卡住；03 的指令跟實物對得上，差別只有 perm 單獨起要有下一站（03 沒寫，因為 perm 平常掛在板子上、有 `AOS_DAEMON`）。

## 第四次更新（到 `2060ee9d5`，只換程式，線 top-1121-home4）

授權：同上兩句；頂層事先跟使用者說過「gdb 那條線交了就重裝一次、裝完用真模型起一次確認」。這次只准 install＋驗收，不改樹裡的檔。

### 做了什麼

1. 開工核對：`pgrep -a aos` 只有線 top-1121-tutorial 的樹（cwd、執行檔都在 `~/.aos/scratch/top-1121-tutorial/`，用它自己複本的 `bin/`），沒有從 `~/aos-home` 起的；表上四隻 `sleeping`（記的 daemon pid 已不在）。`git status -- proto8/py proto8/cpp proto8/templates` 乾淨，HEAD `2060ee9d5`。
2. `97d4abc16..HEAD` 動到 `templates/` 的：agent-fsm 的格程式與 `hooks.json`（ann 動態連結，裝完就生效）、`start-api/agents/ann/README.md`（多一句壓縮前後兩個 hook 點，純說明）。樹裡沒有要換的定義檔、不用搬夾、不用重新編譯；ann 的 README 沒抄（不在這次准做的範圍，跟 HEAD 只差這一句）。
3. proto8 跑 `python3 install.py`：30 支指令（9 C++、21 Python）、`py/` 597 檔與 12 個 C++ 函式庫進 `lib/`，清掉 22 個舊檔。
4. **lib 殘留**：裝前 `lib/aos/hook_handle.py`、`lib/aos/hook_flags.py` 都在；install 自己會清 `py/` 已經沒有的檔，裝完兩支都不在了（我沒動手刪）。`lib/aos/gdb/decl.py`、`lib/tools/agent/gdb_trigger/_entry` 在。
5. 起樹（清掉繼承的 `AOS_*`、`AOS_HOME` 指 repo 的 proto8、`source env.sh`、背景 `aos-exec root`，輸出寫 `~/.aos/scratch/top-1121-home4/`）：四隻 `running`。
6. 驗收（見下），`aos-daemon-ctl -d .stack shutdown`：根行程退出、沒有 cwd 在 `~/aos-home` 的行程，表上四隻 `sleeping`。
7. 桌面過程頁加「第四次更新」一節，最上面的結論改成涵蓋四次。

### 驗收

| 項目 | 結果 |
|---|---|
| ann 真模型（sol＝`chatgpt-gpt-6.1-sol`，1 次呼叫） | 問「請只回一個數字：4+5 等於多少？」答 `9`；prompt_tokens 7,416、cached 0、reasoning 0、3.7 秒 |
| `aos-gdb -d .stack --def-hooks ann` | 起得來，開場印 `hook declarations: 13 point(s) from 2 file(s)`；`hooks` 列出 `lib/aos/apps/hook/loop_hooks.json` 與 `templates/agent-fsm/hooks.json` 兩份、13 個點，含新的 `before_compact`／`after_compact`（14c2de1de 動態連結生效的證據）；Ctrl-D（stdin 結束）離開，沒下斷點 |
| ann 的 hook | `hook ls -l` 進 gdb 前（樹沒起時）與出 gdb 後逐字相同：brain_notify、context_wrap、mail_notify、timer |
| on_clock | 起樹那刻 `hookeds/` 三個工作夾的 `on_clock.json` 都更新 |
| ann stderr | 沒多任何一行 |

- `aos-hook check` 新版已經沒有（`CommandUnknown`），第三次也沒用它；改用上面的 `hook ls` 比對。
- 第一句快取 0：跟第三次第 1 句一樣（距上次呼叫幾小時，上游快取過期），只記。

### ann 多了哪一輪

`.stack/procs/ann/history.jsonl` 16 → 18 則：第 17 則 user「請只回一個數字：4+5 等於多少？」、第 18 則 assistant「9」。沒刪；這次沒另外備份 history（樹裡沒改任何檔），要拿掉就在樹關著時刪最後兩行。

### 替使用者做的選擇

1. 樹裡一個檔都沒改：ann 的 `README.md` 跟 HEAD 範本差一句說明，沒抄。
2. 驗收只問 1 句（不重做第三次那套 5 題），gdb 只打 `hooks`、不下斷點。
3. lib 那兩支由 install 自己清掉，沒另外處理。
4. 起樹輸出寫暫存區；沒設 `LITELLM_KEY`。

## 第五次更新（到 `83e6fa5e3`，只改 `--help`，線 top-1121-helpfix）

授權：使用者 11-21 傍晚「--help那三處也派線改」「能做的就做」；頂層事先告訴他改完樹要重裝一次，加上先前的「好，install.py你跑就行」。這次只准 install＋看 `--help`，不改樹裡的檔、不起樹、不叫模型（沒有行為改動）。

1. 交件 `83e6fa5e3` 之後核對：`pgrep -a aos` 沒有任何 aos 行程（測試時看到的是乾淨複本測試自己起的暫存樹，測試跑完它們自己收掉了）；全機沒有 cwd 在 `~/aos-home` 的行程，沒有 `aos-frontend serve`。`git status --short -- proto8/py proto8/cpp proto8/templates` 乾淨。
2. proto8 跑 `python3 install.py`（清掉繼承的 `AOS_*`）：退 0，30 支指令（9 C++、21 Python）、`py/` 597 檔與 12 個 C++ 函式庫進 `lib/`，清掉 20 個舊檔；aos-daemon 跟著重新編譯。輸出多一行 install.py 自己的 `DeprecationWarning`（`re.split` 的 maxsplit，乾淨複本一樣有，跟這次無關）。
3. 用活樹的環境（`cd ~/aos-home && source env.sh`，`AOS_HOME` 指 repo 的 proto8）看 `aos-agent ctl add --help`、`ctl set-def --help`、`kernel_llm/_entry --help`、`kernel/_entry --help`、`aos-daemon --help`：都是新字。
4. 桌面過程頁最上面加「第五次更新」一小段。

替使用者做的選擇：沒起樹、沒叫模型（install 輸出沒異狀）；樹裡沒改檔、沒有新備份。
