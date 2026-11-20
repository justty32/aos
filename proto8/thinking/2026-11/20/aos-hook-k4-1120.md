# 「提供 hook 點」的介面：施工第 4 刀（新指令 aos-hook：fire、points、check，只加不改）

← [當天索引](README.md)｜設計 [aos-hook-plan-1120](aos-hook-plan-1120/README.md)（指令在 [05](aos-hook-plan-1120/05-發事件指令.md)，對不上以 [12 採納表](aos-hook-plan-1120/12-採納表.md) 為準）｜使用者已答 [13](aos-hook-plan-1120/13-使用者已答.md)｜第 1 刀 [aos-hook-k1-1120](aos-hook-k1-1120.md)

線 aos-hook-k4-1120，11-20 公司 WSL。頂層問「hook 那邊不用等裁定的第 2、4 刀，要接著開工嗎？」，使用者答「先開第 4 刀」。頂層派、線隊長做。

## 結論

- 新指令 **`aos-hook`**（`py/aos/apps/hook/main.py`＋`lists.py`）：`fire` 發一個事件、`points` 列宣告的點、`check` 驗宣告與清單。C++、shell 寫的子程式從此能提供 hook 點：放一份 `hook_points.json`、在那個時機起一次 `aos-hook fire`。
- **跑 hook 全交給引擎 `aos.hook_run.fire`**（agent 與 kernel 用的同一份，一行沒改）：順序、退 10 攔下、`on_error`、`timeout_ms`、能改哪些鍵都是引擎的規矩。指令這層只多做兩件引擎早就留了口的事：改回來的值照宣告的 `change` 型別驗（經引擎的 `check` 參數，逐個 hook 當下驗）、清單的格裡 `entry_keys` 寫錯點＝`HooksBad`。
- **只加**：沒有任何程式叫它；`hook_fire`、`loop.json`、aos-loop、格程式、`interfaces.json` 都沒動。`--agent` 留了旗標位置，給了＝`ArgumentsBad`「not available yet」（要第 2 刀）。
- 新測試 10 支綠，改壞三處各自會紅；全套測試基準與疊上改動逐夾比對見「測試」。耗時見「耗時」：沒人掛約 36 毫秒、掛一個 sh handler 約 40、python handler 約 59（負載下量的；今天的 `hook_fire` 約 30）。

## 加了、改了哪些檔

| 檔 | 新／改 | 一句話 |
|---|---|---|
| `py/aos/apps/hook/main.py` | 新 | 指令本體：三個子指令、共用旗標、事件資料怎麼組、英文 `--help`；295 行 |
| `py/aos/apps/hook/lists.py` | 新 | 讀 `--list` 的清單（後蓋前、null 關掉、檔不在＝沒有）、對宣告驗格、型別檢查函式；88 行 |
| `py/aos/apps/hook/__init__.py` | 新 | 一行說明（09b 列了這檔；有它 `from aos.apps.hook import lists` 才是一般套件） |
| `py/aos/apps/hook/README.md` | 改（擴寫） | 指令說明、shell 與 C++ 用法、實跑輸出、規矩、成本 |
| `py/entries.json` | 改 | 加 `"aos-hook": "aos.apps.hook.main"`（install 後 Python 入口 20→21 支） |
| `py/tests/apps/hook/test_hook_cli.py` | 新 | 10 支，跑裝好的 `bin/aos-hook` |
| `py/docs/05-commands.md` | 改 | 指令表加一列 |
| `py/docs/04-共用模組.md` | 改 | 補第 1 刀留下的 `aos/hook_point.py` 一列 |
| `knowledge/aos/cli/hook_points.json`、`knowledge/aos/cli/_index.json` | 新、改 | 知識庫 cli 一頁＋索引一項（`hook.json` 已經是 `aos-agent hook` 那頁，所以這頁叫 `hook_points.json`） |

`install.py` 的指令數期望值：查過沒有任何測試寫死「20 支 Python 入口」（`test_install.py` 用自己的假家），所以沒有要改的期望值；複本 install 印的是 `30 commands (9 C++, 21 Python entries)`。

## shell 與 C++ 的人怎麼用

宣告（跟 Python 那邊同一種格式，[設計 01](aos-hook-plan-1120/01-宣告格式.md)）：

```json
{"description": "demo saver", "provider": "demo-saver",
 "points": {"before_save": {"when": "before the saver writes a file", "phase": "before",
   "fields": {"file": "the file name"}, "change": {"file": "nonempty_string"},
   "block": true, "if_blocked": "the file is not saved"}}}
```

設計 05 那段 shell 照實跑（`jq` 換成 python3 解 JSON，暫存 `~/.aos/scratch/aos-hook-k4-1120/demo/`；兩個 hook：`a_deny` 是 python，檔名 secret 開頭退 10；`b_rename` 是 sh，回 `{"file": "<原名>.bak"}`）：

```
$ save notes.txt
save as notes.txt.bak
$ save secret.txt
save skipped by a hook
$ aos-hook fire --points hook_points.json --list config.json --stack state --field file=notes.txt before_save; echo "exit $?"
{"data": {"file": "notes.txt.bak"}, "changed": ["file"], "blocked": false, "hook": null, "text": ""}
exit 0
$ aos-hook fire --points hook_points.json --list config.json --stack state --field file=secret.txt before_save; echo "exit $?"
{"data": {"file": "secret.txt"}, "changed": [], "blocked": true, "hook": "a_deny", "text": "secret files are not saved\n"}
exit 10
$ aos-hook fire --points hook_points.json --list config.json --stack state before_sav; echo "exit $?"
aos-hook: error: EventUnknown no point before_sav in hook_points.json (points: before_save)
exit 1
```

loop 那份的點也發得動（標 `not_fired_yet` 的不擋，之後 aos-loop 就用這支發）：

```
$ AOS_LOOP_CODE=3 AOS_LOOP_CAUSE=' stop ' aos-hook fire --points $AOS_HOME/lib/aos/apps/hook/loop_points.json --stack state after_stop
{"data": {"code": 3, "signal": null, "cause": "stop"}, "changed": [], "blocked": false, "hook": null, "text": ""}
$ aos-hook fire --points .../loop_points.json --stack state --field-file stage=/nonexist --field-default stage=idle before_run
{"data": {"counter_runs": null, "stage": "idle"}, "changed": [], "blocked": false, "hook": null, "text": ""}
```

C++：不 link 任何 hook 的東西，用 aos-loop 公開的 `run_once` 起 `aos-hook fire -q …`、看結束碼（10＝被攔、非 0／10＝錯誤行 aos-hook 已印）。寫法照設計 05，README 有那段。**C++ 這邊沒有實跑**：今天沒有任何 C++ 程式叫它（接 aos-loop 是第 5 刀）。

要注意的一件事：**`aos-hook` 會把 stdin 讀到底**（除非是終端）。從別的程式起它時 stdin 要嘛給 JSON、要嘛接 `/dev/null`；接著一條永遠不關的管子它會一直等。aos-daemon 底下的 aos-loop 本來就接 `/dev/null`（`cpp/aos-daemon/src/child/child.hpp`），aos-loop 起的子程式繼承它，所以第 5 刀照設計接上不會卡；README 與知識庫頁都寫了。

## 三種結束碼與 stdout

| 情況 | 結束碼 | stdout | stderr |
|---|---|---|---|
| 沒人掛、或 hook 都照常 | 0 | 一行 JSON `{"data", "changed", "blocked": false, "hook": null, "text": ""}`（`-q` 不印） | 空 |
| `block: true` 的點有 hook 退 10 | 10 | 一行 JSON，`blocked: true`、`hook`＝那個 hook 名、`text`＝它的 stdout | 空 |
| 錯 | 1 | 空 | 一行 `aos-hook: error: CODE reason` |
| `on_error: continue` 的 hook 失敗 | 0 | 一行 JSON（壞值沒進 data） | 一行 `aos-hook: warning: hook X (event E) failed: …; going on without it (on_error: continue)` |

錯誤代號照設計 05：`HookFailed`、`HooksBad`、`PointsBad`、`EventUnknown`、`ArgumentsBad`、`StackMissing`；另外 `aos.flags` 本來就會報的 `FlagUnknown`、`CommandUnknown`。測試逐一驗了（`test_hook_cli.py`）。

## 耗時

量法：暫存複本裝好的 `bin/aos-hook`，`~/.aos/scratch/aos-hook-k4-1120/sh/measure.py`，七種各 60 次、輪流跑（負載變動平均攤到每一列），stdin 接 `/dev/null`。**機器當時負載 4.4（8 核，鄰線在跑全套測試）**，數字偏高；第一輪（負載 7）結果差不多。

| 情況 | 中位數 | 最快 |
|---|---|---|
| `python3 -c pass`（對照：光起 Python） | 16.2 ms | 13.2 ms |
| `aos-hook fire`，沒給清單（沒人掛） | **36.0 ms** | 28.0 ms |
| `aos-hook fire`，空清單（沒人掛） | 35.9 ms | 29.4 ms |
| `aos-hook fire`，掛一個 sh handler | **39.6 ms** | 32.4 ms |
| `aos-hook fire`，掛一個 python3 handler | **59.1 ms** | 49.5 ms |
| 今天的 `hook_fire after_start`（沒人掛） | 30.3 ms | 25.3 ms |
| 單起 `aos-exec` 跑那支 sh handler | 2.5 ms | 2.1 ms |

- 設計估「沒人掛約 18、掛一個 30～37」：實測沒人掛約 36（比估的多一倍）、掛 sh 約 40、掛 python 約 59。多出來的是 import：`python3 -X importtime` 看 `aos.flags`（連 `aos.tool_io`）累計約 15 ms、`json` 約 10 ms、`aos.hook_run` 約 5 ms（負載下量的）；設計那個數是純 Python 起來加標準庫的估計。
- 跟今天的 `hook_fire` 比，多約 6 ms（它不 import `aos.flags`）。
- 掛一個 handler 多出來的＝那支 handler 自己起來的時間（sh 幾毫秒、python 二十幾毫秒）加寫 `event.json`。

## 測試

- **新測試** `py/tests/apps/hook/test_hook_cli.py` 10 支綠：`--help`／不給子指令／不認得的子指令與旗標／沒給 `--points`／`--agent`；沒人掛（stdout 形狀逐鍵比、`-q`）；資料來源（stdin、env 空的不蓋 stdin、env 蓋 stdin、`--field` 蓋 env、同旗標兩次後者算、`--field-file` 去空白與檔不在＝null、`--field-default` 補 null、int 轉不了、`NAME=VALUE` 壞、`--field` 與 `--field-file` 撞名、stdin 不是 JSON／不是物件）；python 與 sh 兩支 handler 的改鍵、攔下（退 10、`hook`、`text`）、名字排序；`condition`；後面清單的 null 關掉前面的、清單檔不在；`on_error stop`／`continue`、回話不是 JSON、逾時；型別檢查（`nonempty_string` 壞值不進 data、下一個 hook 看到的是原值；`object`）；`EventUnknown`、`StackMissing`（與 `$AOS_STACK`）、`PointsBad`（壞宣告、兩份說法不一）、`HooksBad`（不認得的事件、`entry_keys` 寫在別的點、壞名字、清單不是物件）；loop 那份 `before_run`（not_fired_yet 照發、`--field-default`、`$AOS_LOOP_RUNS` 轉整數、退 10）與 `after_stop`；`points` 文字與 `-j`、`check` 的 ok 行與 not_fired_yet 警告。
- **證明會紅**（在暫存複本的 `lib/` 改壞再跑，跑完還原、cmp 對過）：被攔下改成退 0、拿掉 `entry_keys` 檢查（同一輪）→ 3 支紅；拿掉 `nonempty_string` 的空白檢查 → `test_change_types` 紅。
- **全套**：兩份乾淨複本（`git archive ec3b4f4be`＝開工時的 HEAD；`base` 只有 HEAD、`mine` 疊上本線的檔），各自在複本裡跑 `install.py`、清掉 `AOS_*` 後逐夾跑 unittest：`py/tests`、`py/tests/apps/*`、`py/tools/**/tests`、`templates/tests` 與其子夾、`templates/kernel/tests`、`cpp/*/tests`，共 79 夾（mine）。**除了新的 `py/tests/apps/hook`（10 支 OK），其餘 78 夾逐夾支數與結果跟基準一樣**；`py/tests` 兩邊都是 640 支 OK（skipped 1、expected failures 1）。兩邊都退 5 的是 `templates/tests/image-move-check`、`templates/kernel/tests`（0 支：不是 unittest，是 `check.py` 腳本，兩邊一樣，沒另外跑）。結果檔在 `~/.aos/scratch/aos-hook-k4-1120/suite-*.txt`。
- 基準那次跑完後我誤把它重跑了一次、中途停掉（收的是自己記下的 pid），`suite-base.txt` 被清空；第一輪的結果從各夾的 log 重新整理在 `suite-base-run1.txt`，`py/tests` 與後來補的 13 夾在 `suite-base-rest.txt`。
- 沒在 `~/repo/aos/proto8` 跑 `install.py`；沒起任何樹、沒叫模型。

## 沒做的與為什麼

- **`--agent DEF_DIR`**：設計 05 寫它要「宣告＝定義夾 `interfaces.json` 的 `hook_points`、清單＝定義那份疊 stack 那份、after_start 先清 on_clock 狀態、驗 on_clock 專用鍵」；那幾件是 agent 一家的事，設計放在第 2 刀的把手（`agentlib/hooks.py` 的 `open`）裡。這一刀只留旗標位置：`--help` 寫 not available yet，給了＝`ArgumentsBad --agent is not available yet (it needs the agent's own declarations); give --points FILE and --list FILE`。今天所有定義夾也都還沒有 `hook_points` 鍵（第 1 刀紀錄），就算接了也是空表。
- **型別檢查**：設計說「交給引擎逐個 hook 驗」——引擎 `hook_run.fire` 本來就有 `check` 參數，**不用改引擎就做得到**，所以這一刀在指令這層做了（`lists.check`）。沒做的是「併進 `hook_point.open` 的把手、讓 agent 與 kernel 也照宣告驗」：那是第 2 刀，而且會換掉 `agentlib/hooks.py` 手寫的 `_check`。
- **on_clock 專用鍵的值**（`every_ms` 要正整數、`every_cycles`／`every_ms` 二選一、`clock` 是字串）：那是 agent 這個提供者自己的規矩，通用的 `--list` 不驗；只驗「這個鍵只能寫在宣告了它的點上」（設計 01 的 `entry_keys`、B5）。
- **`check` 不看 handler**：不解指示詞、不看檔在不在（解指示詞要起 `aos-directive`；設計只說「事件在不在、鍵對不對、不跑 handler」）。
- **`py/docs/05-commands/01-逐支說明.md` 加一節**（09b 刀 4 表）：那份已經 17 KB，超過 8 KB 的拆分門檻；只在 `05-commands.md` 的指令表加一列，細節放夾裡的 README。要不要拆那份是另一件事。
- 沒做第 2、3、5 刀的任何事：格程式、`interfaces.json` 的 `hook_points`、aos-loop、`hook_fire`、`agent_spec` 都沒碰。

## 照設計預設做、使用者沒裁的地方

這一刀不依賴任何待裁題（[10](aos-hook-plan-1120/10-待裁題.md)：「第 1、2、4 刀不依賴任何一題」）。碰到的只有一處沾邊：

- **第 4 題「欄位寫進宣告當唯一來源」**（使用者沒裁）：`fire` 照宣告的 `fields` 從環境變數補值、`points` 照宣告印欄位，等於用了宣告的 `fields`。選「不要」＝`fields` 變 `{}`，`aos-hook` 不會壞，只是不會從環境變數補值（loop 那份就得改由 argv 的 `--field` 帶）。

## 替使用者做的選擇（施工層級，設計沒寫到的）

1. **`--list` 指到不存在的檔＝沒有 hook**，不報錯：跟 agent 讀 stack 那份 `hooks.json` 一樣（那份平常就不在）。代價是路徑打錯會安靜地什麼都不跑；`check` 也不會抓。
2. **環境變數去頭尾空白後才判「不是空字串」**：設計 A14 只說「有設而且不是空字串」；這樣 `AOS_LOOP_CAUSE=' stop '` 得到 `stop`，跟今天 `hook_fire` 的 `cause()`（去空白、空的＝null）一樣，第 5 刀換過去行為不變。
3. **`--field-default` 在「沒有、或是 null」時都補**：`--field-file` 檔不在給的是 null，設計 A7 要的正是這時用起始格補，所以 null 也算「沒給出值」。
4. **同一個 NAME 同時給 `--field` 與 `--field-file`＝`ArgumentsBad`**；同一個旗標給兩次＝後面那個算（`aos.flags` 重複旗標的老規矩）。設計只說「同名時後者蓋前者：stdin → env → 旗標」，沒說兩種旗標之間的先後；`aos.flags` 的可重複旗標分表收，排不出兩種之間的順序，所以乾脆不准。
5. **`--field` 給宣告裡沒有的名字照收**，跟 stdin 的鍵一樣不驗（引擎也不驗）。要驗就兩邊一起驗，那是行為上多一道擋，留著等有人要。
6. **`check` 遇到掛在 `not_fired_yet` 點上的 hook 印一行 warning**（照常退 0）：設計沒寫；第 1 刀紀錄提醒第 3 刀要決定「not_fired_yet 算不算可掛」，這裡先只提醒、不擋。
7. **`check` 成功印一行 `ok: N points from N declarations, N hooks from N lists`**。
8. **`points` 的文字格式**：一個點一段，第一行 `名字  phase  condition 欄位  change 鍵 (型別)  can block`，下面每份宣告的 when／if blocked／if failed／not fired yet（第 1 刀的 `said` 逐份印）、每個欄位。設計 09b 說這段要讓第 3 刀的 `aos-agent hook events` 共用；**我把它留在 `main.py` 的 `show()`**，沒放進小庫（不動第 1 刀的 `hook_point.py`），第 3 刀要用時搬進小庫或直接 import。
9. 型別檢查與讀清單放在 `py/aos/apps/hook/lists.py`，不放進 `hook_point.py`：同上，第 2 刀做 `hook_point.open` 時可以整段搬過去。
10. 知識庫頁名 `hook_points.json`（`hook.json` 已被 `aos-agent hook` 用了）。

## 對不上處與怎麼處理

- **設計 05 估「起一次約 18 毫秒」**，實測沒人掛時中位數約 36 毫秒（同一台、同一輪量的今天 `hook_fire` 約 30）。差的主要是 import：`-X importtime` 看 `aos.flags`（含 `aos.tool_io`）約 15 毫秒、`json` 約 10 毫秒、`aos.hook_run` 約 5 毫秒；設計那個數是純 `python3` 起來加 import 的估計，沒算 aos 自己的模組。量的時候機器負載 3～7（鄰線在跑測試），數字偏高。見「耗時」。
- **09b 刀 4 的「`01-逐支說明.md` 加一節」**：沒加，理由在「沒做的」。
- **09b 的 `--agent`（等刀 2）**：照任務書只留位置。
- **09b「`points` 的印法要讓刀 3 共用」**：留在指令裡，理由在選擇第 8 條。
- 其餘照 05 與 12：`--field-default` 有（12 的刀 4 改動）、環境變數「有設而且不是空字串才用」有、轉不了整數＝`ArgumentsBad` 有。

## 第 2 刀、第 5 刀開工前要知道的

- **第 2 刀**：
  - `lists.load`（讀清單、驗格、`entry_keys`）與 `lists.check`（照 `change` 型別驗）就是 `hook_point.open` 要的兩塊；搬進小庫後 `aos-hook` 改叫小庫即可（行為測試在 `test_hook_cli.py`，照跑）。
  - `--agent` 接上時：宣告用 `hook_point.for_definition`、清單用 agent 的兩層（定義疊 stack）、after_start 先 `clock_restart`、on_clock 的值照 `agentlib/hooks.py` 驗；`declared()` 那個函式是唯一要改的入口，`--agent` 與 `--points`／`--list` 二選一（設計 05）。
  - `before_tool` 的 `arguments` 宣告是 `any`（第 1 刀照今天行為寫的），所以 `aos-hook` 現在也不擋 arguments 的型別。
- **第 5 刀**：
  - loop.json 的 `on_start`／`on_stop` 改成 `["aos-hook", "fire", "-q", "--agent", …]` 要等 `--agent`（第 2 刀）；在那之前想先試，可以用 `--points` 指 `$AOS_HOME/lib/aos/apps/hook/loop_points.json`＋`--list` 指定義與 stack 的 `hooks.json`，但那樣不會清 on_clock 狀態、也不驗 on_clock 的值。
  - `AOS_LOOP_SIGNAL` 這類「沒有就給空字串」的環境變數，`aos-hook` 當成沒設（null）；給 `"0"` 會變成整數 0（A11 已定要給空字串）。
  - aos-loop 起它時 stdin 是 `/dev/null`（daemon 給的），不會卡在讀 stdin。
  - 每次發一次約起一支 Python（數字在「耗時」）；`before_run`／`after_run` 每圈各一次，旗標檔那套（第 11 題）就是為了沒人掛時省掉這筆。
- **兩刀都要**：新檔要 `install.py` 之後才進 `lib/`、`bin/aos-hook` 才有；**在 `~/repo/aos/proto8` 跑 `install.py` 要使用者點頭**（本刀只在暫存複本裡跑過）。
