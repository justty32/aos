# bin — aos-tick、aos-tools、aos-daemon-ctl、aos-eca-turn（Python）

← [proto8](../README.md)｜慣例：[CONVENTION](../docs/CONVENTION.md)｜demo：[demo](../demo/README.md)｜C++ 實作：[impls](../impls/README.md)｜測試：`python3 -m unittest discover -s proto8/tests`（先建 impls，見 [testing](../../wf/workflows/testing.md)）

> **C++（[proto8/impls](../impls/README.md)）是唯一實作**（使用者 10-23：「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 和 tick，使用者選「fsm 也改用 C++、tick 先留 Python」）：
> `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 的說明在各自的 README：[aos-exec](../impls/aos-exec/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-fsm](../impls/aos-fsm/README.md)、[aos-daemon](../impls/aos-daemon/README.md)；inst 是 C lib [inst](../impls/inst/README.md)。
> 這裡是 `aos-tick` 與 10-28 加的 `aos-tools`（同天的 `aos-parts` 11-01 刪了）、10-30 加的 `aos-daemon-ctl`（同天的 `aos-round` 11-01 刪了）、10-31 加的 `aos-eca-turn`（Python，都用 `aos_flags.py` 的旗標解析 `parse`）。
> 刪掉的 bin 版各支逐支說明在 git 歷史：`git show 60d677cc:proto8/bin/README.md`。

```
sh proto8/demo/run.sh                                  # 建暫時工作區、放一題、跑 agent-bob、agent-ann，再用 aos-daemon 同時管兩隻，最後讓 aos-loop 跑 5 次 aos-tick；印工作區與 stack 樹
python3 -m unittest discover -s proto8/tests           # 四支 C++ 在 impls/<名>/bin/、aos-tick 在這裡（tests/aos_bins.py 放 PATH）
```

aos 的程式都不動 PATH（ideas § 24）：自己跑時把 `proto8/impls/<名>/bin/`（四支）與這個 `bin/`（aos-tick、aos-tools…）放進 PATH，`demo/run.sh` 就是這樣做。

## 逐支說明

> **分層（[C-74](../docs/CONCEPTS/01-設計理念.md#分層10-22-使用者定)）**：`aos-tick` 擱置中、不歸層。（基礎層、標準庫那幾支只有 C++ 版，見 [impls](../impls/README.md)。）

- **`aos-tools - 一個 agent 資料夾一份工具註冊檔（tools.json），登記這隻 agent 能叫哪些工具`**（10-28；決定與代定 [thinking 10-28 aos-tools](../thinking/2026-10-28-aos-tools.md)；完整說明在檔頭 docstring）
  用法 `aos-tools [--file F] add [--override] [--name N] XXX｜rm XXX｜ls [--json]｜get XXX｜call 名`，註冊檔＝`--file`＞`./tools.json`（沒有＝沒登記任何工具）。
  **三種登記對象**（種類照 aos-exec 的認法，N-61）：資料夾（裡面 `_tooldef`，沒有再找 `_tooldef.json`）、沒 `+x` 的 JSON 檔（頂層 `_tooldef` key）、有 `+x` 的 python／可執行檔（`XXX --tooldef` 在 stdout 吐定義，結果依檔的 mtime＋大小快取在註冊檔）；不符合就報錯。工具定義＝OpenAI function 物件去掉 `name`。工具名＝`--name`＞檔名去副檔名（資料夾名），只收 `[A-Za-z0-9_-]`；撞名 `ToolExists`，`--override` 蓋掉。
  **存法**：`{"tools": {名: {"path": 絕對路徑, "cache"?: {...}}}}`；add 的相對路徑從 cwd 算、一律存絕對；手寫的相對路徑從註冊檔的資料夾算（範本用這個，搬家不斷）。有 `$ref`／`$env` 就交給 aos-json 解與改（`$ref` 陣列＝拆成好幾份，add 寫進最後一份）。
  **叫**：`call 名`——資料夾、JSON＝`aos-exec 路徑`，arguments 原樣從 stdin 進（P-41）；可執行檔＝arguments 寫成 `$AOS_STACK/tool_call.json`（沒設＝暫存檔、用完刪），`aos-exec 檔 --tool-call 那個檔`。結束碼是工具的。
  **錯**：stderr 一行 `aos-tools: 代號 原因`、退 1（`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`RegistryBad`、`PathMissing`、`ToolDefMissing`、`ToolDefBad`、`NameBad`、`ToolExists`、`ToolMissing`、`DirectiveBad`、`CommandMissing`、`WriteFailed`）；ls／get 碰到登記了但壞掉的工具也報錯。要 PATH 上有 aos-exec、aos-json。測試 `proto8/tests/test_aos_tools.py`。

- **~~`aos-parts`~~（10-28 晚加、11-01 刪）**：A 題 parts 瘦身（[thinking 10-31 parts-round § 決定（11-01）](../thinking/2026-10-31-parts-round.md#決定11-01-使用者)：parts 是 agent 慣例層的約定、以刪掉 aos-parts 為目標）。`parts.json` 換成 aos-exec 格式——整份就是槽表，槽值＝路徑字串（轉向，相對路徑從 parts.json 的資料夾算）或 `{".env": {名: 值}, "_entry": 路徑}`，`endpoint/<名>`、`hook/<點>` 巢狀（`{"hook": {"pre_think": …}}`）；`.env` 的值可放 `$env`／`$ref`（aos-exec 本來就會，C-72、N-61），預設不蓋環境裡已有的（N-58），要蓋那一跳加 `aos-exec --dotenv-override`。找格（註冊檔有寫的優先 → 固定名字 `<agent>/<槽>` → 沒有）改在 [`lib/agent/parts.py`](../lib/agent/parts.py)，器官（roundlib、queue、compact、act、ask_round）共用。原本的子命令換成：
  | 原本 | 現在 |
  |---|---|
  | `aos-parts --file F run 槽 args…` | `aos-exec <agent>/parts.json#/槽 args…`（註冊的）或 `aos-exec <agent>/<槽> args…`（固定名字） |
  | `aos-parts which 槽` | `aos-json get <agent>/parts.json#/槽`（`PointerMissing` 退 1＝沒登記）；固定名字 `ls -l <agent>/<槽>` |
  | `aos-parts get／ls` | `aos-json get <agent>/parts.json`（加 `--resolve` 解開指示詞） |
  | `aos-parts add／rm` | 手寫，或 `aos-json set --parents <agent>/parts.json#/槽 '"路徑"'`／`aos-json del <agent>/parts.json#/槽` |
  沒留薄殼：人在 shell 裡要問「這隻 agent 的 queue 在哪」，上面兩行就答得出來，沒有非程式不可的情境。測試 `proto8/tests/test_round_parts.py`。

- **`aos-round`**：11-01 刪了（使用者「aos round這東西還沒刪掉嗎」「刪掉」）。agent 的 `loop.json` 直接叫 aos-fsm 跑 `lib/agent/round/` 的表：
  `{"exec": {"argv": ["aos-fsm", "fsm-stop.json"], "cwd": "../../lib/agent/round", "timeout_ms": 600000}}`（demo/agent-nia；repo 外的 agent 寫絕對 cwd）——
  `cwd` 讓表裡的格名從 round 資料夾找，表的 `{"$env": "AOS_CD"}`＝loop 跑那張單子時的 `AOS_CD`＝agent；queue 空的停法＝指哪張表（`fsm-stop.json` 退 10 收工／`fsm-idle.json` 退 0 再來）。
  單走一格＝`aos-exec <agent>/loop.json#/exec`（lib/aos/ask_round 這樣叫）。說明在 [lib/README round](../lib/README.md)；測試 `proto8/tests/test_round_loop.py`。

- **`aos-eca-turn - 外部 coding agent（claude／codex）的一輪：從 stack 的 queue 認領一則、交給 CLI 答、回答接進 history`**（10-31 改名、升成 bin 指令；使用者「aos eca turn」、C-54 R13 `aos-<領域>-<功能>`；前身 10-30 的 `lib/eca/turn` 格；設計 [thinking 10-30 eca](../thinking/2026-10-30-eca.md)；完整說明在檔頭 docstring）
  用法 `aos-eca-turn [--one] [--on-empty stop|idle] [--on-busy yield|answer] <定義資料夾絕對路徑>`（旗標在位置參數前）。定義＝`demo/eca-claude` 那種（頂層 `cli.json`、選填 `prompt.txt`），定義不被寫、寫的都在 `$AOS_STACK`。一次答一則：`queue/cur/` 有信先接、否則 `aos-post claim` 一封 → user 接進 `history.jsonl` → 經 `lib/agent/cli_session.py` 的 `ask` 問 CLI（畫面開著貼字、沒開 `--resume`）→ assistant 接進 history → 收信；壞信丟掉、trace 記 `letter_warning`；trace 一行 `unit: "aos-eca-turn"`；`$AOS_STACK/eca.json` 記 kind、ws、template。
  **`--on-empty`**（10-31 取代環境變數 `ECA_ON_EMPTY`，不再讀它）：queue 空時 `stop`（沒給；退 10＝loop 收工）｜`idle`（退 0＝loop 隔 `interval_ms` 再來）；壞值、跟 `--one` 一起給＝`ArgumentsBad`。**`--on-busy`**（10-31）：`yield`（沒給）＝lock 拿不到、有人接在 tmux 畫面上、`busy.txt` 在＝這輪退 0、信留 `cur/`、不寫 trace（`--one` 照錯退 1）｜`answer`＝照常答不退讓（lock 等、有人接著照樣貼、`busy.txt` 等它消失，共用 `timeout_ms` 期限，逾時 `ReplyMissing`）。`--one`＝工具形（stdin `{"prompt"}` → stdout，同 `lib/agent/claude` 的 `call_main`）。定義的 `loop.json` 這樣叫：`{"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000}}`。
  **錯**：stderr 一行 `aos-eca-turn: 代號 原因`、退 1（`ArgumentsBad`、`FlagUnknown`、`AgentBad`、`StackMissing`、`HistoryBad`、`PostFailed`、`WriteFailed`，加 cli_session 的 `CfgMissing`、`CfgBad`、`CliMissing`、`CliFailed`、`ReplyMissing`）；10-30 的 `SettingBad` 拿掉了。要 PATH 上有 aos-post。測試 `proto8/tests/test_eca_turn.py`（範本 `test_eca.py`）。

- **`aos-tick - 把時鐘檔的回合數往前走一格`**（NAME，C-54 R1）
  用法 `aos-tick [旗標] FILE`（Python）：時鐘往前走一格（C-44：只是時鐘，不包任務、不保證什麼）。FILE 裡是回合數（十進位＋換行），讀出 n、寫回 n＋1 就退 0；FILE 不在＝0（第一次寫 1）；寫進 n＋1＝第 n 回合結束、第 n＋1 回合開始，mtime＝這回合從什麼時候開始。先寫同資料夾的 `.名字` 再改名蓋過去（N-05），不 fsync，stdout 不吐東西。**命令列**：唯一的位置參數就是 FILE（必給、只能一個、相對路徑從 cwd 算）；FILE 照字面用，`#` 不切指標（它是時鐘檔不是設定檔）；目前沒有旗標（旗標表是空的、走 `aos_flags`，`--` 結束旗標）。**自己的錯**退 1、stderr 一行 `aos-tick: 代號 原因`、FILE 不動：`ArgumentsBad usage: aos-tick [旗標] FILE（原因）`（跟 aos-loop、aos-fsm 同一個寫法）（沒給、多給；不認得的旗標是 `FlagUnknown usage: …`）、`ClockBad 時鐘檔讀不到：`（例：它是資料夾）、`ClockBad 時鐘檔壞：`（內容不是 `[0-9]+` 加可有可無的一個 `\n`；空檔、`\r\n`、空白、負號、全形數字都算壞）、`WriteFailed 時鐘檔寫不了：`（資料夾不在或沒寫入權限；不替人建資料夾，暫存檔會清掉）。節奏、停、只走 N 回合交給 loop（`max`、`interval_ms`、ctl 的 `paused`）；同一個 FILE 兩個人同時 tick 不管。

- `aos_flags.py`：命令列旗標解析 `parse(argv, 旗標表)` 回 `(opts, [XXX, args...])`（`--x V`／`--x=V`、重複給最後一個算、`--` 結束旗標、第一個不是旗標的參數起原樣；不認得＝`FlagUnknown`、缺值＝`ArgumentsBad`）。aos-tick、aos-tools、aos-eca-turn 用（10-28～11-01 aos-parts 也用）。

執行中狀態（`state.txt`、`trace.jsonl`、`plan.txt`、`current.txt`）在 `$AOS_STACK`（預設 `$AOS_WS/.stack/`）；工作區只放交辦的東西與成果（題目 `new/` → 認領 `cur/` → `done/`，答案 `out/`）；定義資料夾不被寫，所以同一個 agent 可同時被兩個工作區跑。結果＝工作區內容；沒有別的結果通道。

## 已定值

- `AOS_ENTRY` 預設 `_entry`（使用者已定，[ideas § 13](../thinking/2026-10-19-ideas.md)），環境變數可覆寫。入口只佔資料夾的一層，跟 table 的一個 key 對上（`js["_entry"]`，C-72）；工作區的 `.stack/` 是 stack 的預設位置，跟入口無關。
- `AOS_STACK`（使用者已定）：預設 `$AOS_WS/.stack/`，是被叫的那個程式自己的 stack。它的子程式的 stack 由它自己訂（例如給 `$AOS_STACK/think`、`$AOS_STACK/act`），aos 不管巢狀。
- 工作區變數名 `AOS_WS`（使用者已定）。
- `aos-exec [--ws WS] XXX [args...]`（N-58；使用者「放前面吧。舊的寫法也要改」）：`--ws -`／沒給＝沿用 `$AOS_WS`，沒設才用 `.`（使用者 10-19 定）。
- `AOS_CF`、`AOS_CD`（使用者 10-19 下班前定，「同意做」）：實際被執行的檔、它所在的資料夾，aos-exec 每層覆寫（N-57；已做）。
- `AOS_CO`（使用者 10-21 晚「AOS_CF不動。但是我們再加上AOS_CO」「aos current obj」）：入口在 JSON 檔裡的指標，aos-exec 每層覆寫（N-57；已做）。aos-loop、aos-fsm、aos-daemon 的 `exec` 直接放單子物件時，跑那張單子的期間也把 `AOS_CF`／`AOS_CD`／`AOS_CO` 設成它的位置（設定檔、資料夾、`/exec` 或 `/states/<名>/exec`），跑完還原，見 [impls/aos-loop](../impls/aos-loop/README.md)、[thinking 10-24](../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)。
- `#/` 尋址（使用者 10-19 下班前定，「#/。」「尋址一定值得。」）：`檔#/指標` 指進 JSON（N-62；已做）。

- **`aos-daemon-ctl - 把東西掛到一個 aos-daemon 上（往它的信箱投 loops_added／execs_added）`**（10-30；使用者「我們現在跑aos-exec XXX，等同於把這個proc掛到linux這個原生proc管理器上。假如我們想要掛在daemon上呢？或許是aos-daemon-ctl add XXX這樣，然後會自動識別XXX是否為loop，不是的話就max:1這樣？」；[thinking 10-30 agent-lifecycle](../thinking/2026-10-30-agent-lifecycle.md) 實作第 7 步的補；完整說明在檔頭 docstring；例子在 [demo/daemon-3](../demo/daemon-3/README.md)）
  用法 `aos-daemon-ctl [--daemon-stack D] add [--name N] [--ws WS] XXX [-- 參數...]｜rm 名字｜ls [--json]`。11-02 使用者「把--kind刪掉，XXX後面可以接-- ... 也就是附加argv參數。改成子項結束後不留名單」：`--kind`（含 `max1`）拿掉、給了＝`FlagUnknown`，`KindBad` 一起拿掉；`add XXX -- 參數...`；ls 只看得到還在跑的。
  **哪個 daemon**（N-63 hub 型變數）：`--daemon-stack` ＞ `$AOS_DAEMON_STACK`（11-02 從 `--daemon`／`$AOS_DAEMON` 改名、不留別名，使用者「就AOS_DAEMON_STACK吧」「最好明講，也就是--daemon-stack」；給 `--daemon`＝`FlagUnknown`，只設舊名＝`DaemonMissing`、訊息提示改設新名），值＝那個 daemon 的 `$AOS_STACK`（它的窗用預設名字：信箱 `loops_ctl_mailbox/`、`loops_state.json`）；都沒有或不是資料夾＝`DaemonMissing`；子 proc 照常繼承。
  **add／rm＝投信**（信箱模式，N-28 的 10-29 補、N-54）：daemon.json 要寫 `"loops_ctl_mailbox": "loops_ctl_mailbox"`（11-02 前叫 `loops_mailbox`；可以跟 `loops_ctl` 同時開），沒有 `new/`＝`MailboxMissing`；stdout 印 aos-post 的信號；daemon 下一圈才套，結果看 ls（壞信在 loops_state 的 `mailbox_warning`）。rm＝`loops_removed`＋`execs_removed` 都寫那個名字。
  **做完的同名再 add＝重新起**（11-02）：信箱模式下子項做完（done）daemon 就從期望表拿掉，再投一封同名的 add 就再跑一次，不用先 rm、等一下（11-02 試驗場碰到的「rm 跟新信同一圈收到、新題沒跑」不會再有）。
  **自動識別**：XXX 是有 `loop.json` 的資料夾＝loop 子項，設定＝它的 loop.json（去掉 `_entry`；相對 exec 照 XXX 轉絕對；exec 是內嵌單子＝換成 `<XXX>/loop.json#/exec`，子 loop 每次 aos-exec 指回原檔那張單子，`AOS_CD`＝XXX、相對的 cwd／argv 照原地算——agent-nia 的表用 `{"$env": "AOS_CD"}` 認 agent、eca 定義的 `aos-eca-turn … {"$env": "AOS_CD"}` 靠這條掛得上 daemon；11-01 刪 aos-round 時取代原本的「複製單子補 cwd、把 `{"$env": "AOS_CD"}` 釘成 XXX」）——子 loop 直接跑它的 loop，ctl／state 落在小格；其他＝`execs`（XXX 的絕對路徑）。名字＝`--name` ＞ XXX 的資料夾名。XXX 的 `.env`、loop.json 裡的指示詞不處理。
  **`-- 參數...`**（11-02）：`--` 之後全當附加 argv，原樣不轉路徑；exec 型＝`execs_added {名字: [XXX 絕對路徑, 參數...]}`（daemon 起它＝`aos-exec XXX 參數...`；沒參數照舊是字串），有 `--ws`＝`{"exec": [XXX, 參數...], "ws": WS}`。**loop 型帶參數＝`ArgumentsBad`**（代定：子項設定是 XXX 的 loop.json，參數沒有自然的去處；要參數寫進 loop.json 的 `exec`）。XXX 後面接的不是 `--`＝`ArgumentsBad`（add 只收一個 XXX）。例：`aos-daemon-ctl add ../../agents/bob -- "在 env:AOS_WS 寫一首詩，詠桃花，檔名 peach.txt。"`。
  **`--ws WS`**（10-30 eca 第 2 步，[thinking 10-30 eca](../thinking/2026-10-30-eca.md) 衝突 1、3，使用者「都照建議」）：這一隻的工作區。WS 從呼叫當下的 cwd 轉絕對（不是資料夾＝`PathMissing`、空＝`ArgumentsBad`），寫進子項物件的 `ws`（loop＝子項設定多一個 `ws`；exec＝`{"exec": XXX 或 [XXX, 參數...], "ws": WS}`），daemon 起它時設 `AOS_WS`（[aos-daemon「子項的工作區 ws」](../impls/aos-daemon/README.md)）。
  信送出之後：`<WS>/.stack` 不在（`lexists`，壞掉的 symlink 也算在）＝建一個 symlink 指到這一隻在 daemon 的小格 `<D>/loops/<名字>`（11-02 改 `loops/<名字>/`，[thinking 11-02 stack-tools](../thinking/2026-11-02-stack-tools.md)；小格還沒建也先建），cd 到 WS 打 aos-say 就接上這一隻；已經在（例如直接 aos-exec 跑過留下的真 `.stack/`）＝不建、stderr 一句「`aos-daemon-ctl: 注意 工作區已有 .stack（…），沒建捷徑到小格 …；要接上請先搬開（或用 --stack …）`」，add 照樣成功、退 0（10-30 代定：照「注意」慣例，不另設 `StackExists`）。
  rm（代定）：信送出之後，`loops_state.json` 那一列有 `ws`、而且 `<ws>/.stack` 是指到 `<D>/loops/<名字>`（11-02 改）的 symlink＝順手拿掉；拿不到 ws、不是 symlink、指到別處＝不動、不報。11-02 起已經結束的子項不在表上＝拿不到 ws，捷徑留著（要自己刪）。
  **ls**：讀 `loops_state.json` 兩張表（切檔的 `$ref` 合回來），一行「名字 TAB loop|exec TAB phase TAB pid TAB code TAB ws」（code、ws 沒有＝`-`；ws 那欄 10-30 eca 加）；`--json`＝一行 `{"loops", "execs"}`（列照 loops_state 原樣，有給 ws 的帶 `ws`）。**11-02 起表上只有還在跑的**（`running`、收的途中 `stopping`）：子項結束（`done`／`stopped`）daemon 就拿掉，**結束碼看 daemon 的 log**（`aos-daemon --enable-logs` 時 stdout 每個子項起來一行、結束一行 JSON，`{"at","name","table","phase","pid","code","signal"(,"ws")}`），所以 code 那欄平常是 `-`。
  **ls 另判 daemon 活著**（11-02，使用者「要看一個proc是否還活著，除去linux底層proc機制外，我們的aos-daemon-ctl問詢也是一個方式，兩者並存」）：loops_state 頂層的 `pid`＋`started_at_ticks`（＋`boot_id`）對 /proc（N-17 的確定法），對不上＝stderr 一句「`aos-daemon-ctl: 注意 daemon 沒在跑（pid N）；表是它最後寫的`」，照樣列、退 0（`--json` 也一樣，輸出不加欄）。不看 `updated_at` 或檔案新不新（state 窗 11-02 起有變才寫、沒心跳）。
  **錯**：stderr 一行 `aos-daemon-ctl: 代號 原因`、退 1（`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`DaemonMissing`、`MailboxMissing`、`PathMissing`、`LoopBad`、`StateMissing`、`StateBad`、`CommandMissing`、`SendFailed`）。要 PATH 上有 aos-post。測試 `proto8/tests/test_aos_daemon_ctl.py`（10 案；10-30 eca `--ws` 3 案；11-02 `-- 參數`、ls 判活、同名再 add）。
