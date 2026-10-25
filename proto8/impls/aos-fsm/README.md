# aos-fsm

`aos-fsm - 照一張狀態表，每叫一次跑「現在狀態」那一格，成功就換到下一個`（NAME，C-54 R1）

**一句話：`aos-fsm [旗標] 設定檔.json`——一次只跑一格：看 `$AOS_STACK/state.txt` 記的現在狀態，跑那一格，格退 0 才把狀態換成 `next`，然後以格的碼結束。**
一個 lib（`lib/libaos-fsm.a`，沒有公開標頭）加一支薄薄的命令列（`bin/aos-fsm`）。連 [aos-loop](../aos-loop/README.md) 的公開 API（跑一格＝`run_once`；它又帶進 aos-exec、inst、aos-util、aos-directive）。全家慣例見 [impls/README.md](../README.md)。

像大富翁只擲一次骰子：桌上一張地圖（`fsm.json`：每格寫著「走到這裡做什麼、做完去哪格」），棋子停在哪格記在一張小紙條上（`$AOS_STACK/state.txt`）。
叫它一次，它就看紙條、做那格的事、做成了（0）才把棋子移到下一格，在流水帳（`trace.jsonl`）記一行，然後下班；做不成就留在原地、帶著那個碼回去。
要一直玩下去，就讓 aos-loop 一次次叫它。

```sh
cat fsm.json
# {"start": "idle", "states": {"idle": {"exec": "idle", "next": "think"},
#   "think": {"exec": {"argv": ["python3", "brain.py"], "stdout": {"$env": "AOS_STACK", "$path": "plan.txt"}, "timeout_ms": 120000},
#             "next": "act"},
#   "act": {"exec": ["act", "--fast"], "next": "idle"}}}
AOS_STACK=st/ aos-fsm fsm.json; echo $?   # 跑 idle 那格（aos-exec -- idle）；退 0 → st/state.txt 變 think
cat st/trace.jsonl   # {"started_at": "2026-10-19T14:07:00.123+00:00", "state": "idle", "code": 0, "signal": null, "elapsed_ms": 3}
```

規則出處：CONVENTION P-07～P-10、P-20、P-21、P-36、P-38，NORMS N-36、N-38、N-39、N-41、N-05、N-43、N-60，ideas § 20、§ 23、§ 24。
格的 `exec` 可以直接放單子（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking 10-24](../../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）：物件＝aos-fsm 行程內 `run_inst`（aos-loop 的 `run_once`）。

## 用法

```
aos-fsm [旗標] 設定檔.json
```

- **命令列**：唯一的位置參數就是設定檔——必給、只能一個；可寫 `檔#/指標`（aos-util 的 `load_cfg`；例 `agent.json#/fsm`）。
  目前**沒有旗標**（旗標表是空的，規則同 aos-exec，aos-util 的 `parse_cli`）；`--` 結束旗標。不認得的旗標（含 `--cfg`）＝`FlagUnknown`；沒給、多給＝`ArgumentsBad`
  （原因 `usage: aos-fsm [旗標] 設定檔.json（原因）`）。
- **fsm.json**：`{"start": 起始狀態名, "states": {狀態名: {"exec": 格, "next": 下一個狀態名}}}`（使用者「fsm.json，現在是用val，幫我改成exec」）。表一定明寫、`next` 只在表上（N-36）；其他 key 忽略（`body`、`_entry`…）。
  - `exec`（aos-loop 的 `parse_target`，跟 loop.json 的 `exec` 同一套寫法、同名）＝**字串**（每次 `aos-exec -- 它`）或**陣列 `[目標, 參數...]`**（`aos-exec -- 目標 參數...`）；
    相對路徑從 cwd 算（cwd 通常是 agent 資料夾，fsm 不轉）；WS 沿用 `$AOS_WS`、AOS_STACK 沿用（由那格的 aos-exec 定）。
  - `exec` 寫成**物件＝單子**：aos-fsm 在自己行程內交給 aos-exec 的 `run_inst` 跑、當監工（`timeout_ms`、整群收、轉訊號）。跑的期間 `AOS_CF`＝fsm.json 的實際路徑、
    `AOS_CD`＝它的資料夾、`AOS_CO`＝`/states/<名>/exec`（名字照 JSON 指標跳脫；設定檔寫 `檔#/指標` 時接在那個指標後面），跑完還原；相對路徑從 fsm.json 的資料夾算，單子裡的 `$ref` 從那格來自的檔的資料夾算；相對的 `AOS_WS`／`AOS_STACK` 以 fsm 的 cwd 轉成絕對（同 aos-loop）。
    單子壞（`EntryBad`／`DirectiveBad`／`LaunchFailed`）＝自己的錯一行「aos-fsm: 代號 狀態 X：單子跑不起來：…」、退 1、不寫 trace、state 不動；被逾時收掉＝trace `code` 143、`signal` 15。
    `"exec": "fsm.json#/states/<名>/body"`＋`body` 照樣能用（字串目標，由那格的 aos-exec 跑）。
  - **開跑時查整張表**（ideas 10-22 § 7，`check`）：讀表後、跑格前，`start` 要在表上；每一格要是 `{"exec", "next"}`、`exec` 合法（單子只看是物件，裡面跑那格時才驗）、`next` 是表上的狀態名、
    不是空字串、頭尾沒空白（認 Unicode 空白）、沒換行。哪一格不合都＝表壞 `CfgBad`、不跑格。
  - fsm.json 帶 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]` 時 `aos-exec fsm.json` 就是一次；表在大 JSON 裡時寫 `{"$env": "AOS_CF", "$path": "#/fsm"}`（`$path` 字串拼接）。
  - **指示詞**（使用者「aos 讀的 JSON 全部支援」，N-45）：只解 fsm 自己讀的格——整份、`states`、每一格先換一層，`start`、格的 `exec`（換一層後是物件＝單子，裡面不解、跑那格時才解）、`next` 整個解
    （例 `{"start": "idle", "states": {"$ref": "states.json"}}`、`"exec": ["aos-exec", {"$env": "TOOL"}]`）；格裡其他 key（`body`…）不碰，留給跑那格的 aos-exec。
    相對 `$ref` 從 fsm.json 所在的資料夾算（換進來的檔從那份檔的；fsm.json 是捷徑＝實際的資料夾，同 aos-exec 與單子的 `AOS_CD`，`aos::loop::config_file`）；解不開＝自己的錯 `DirectiveBad`、不跑。`#/` 指標走原文：`states` 拆到別的檔，`exec` 要指進那份檔（`states.json#/think/body`）。
- **`$AOS_STACK`**（必要）：fsm 自己的兩個檔都在這裡（只有 fsm 自己寫，N-39）：
  - `state.txt`：純文字一行狀態名（跟 shell 版 fsm 同格式，可互換，P-07）。沒有、空的＝`start`；前後空白去掉（認 Unicode 空白，同 Python `str.strip()`）。
    **在但讀不了**（沒權限、是資料夾、不是 UTF-8）＝`StateBad`、不跑格；裡面的狀態不在表上＝`StateUnknown`。
    寫的時候先寫 `.state.txt` 再改名蓋過去（N-05）。
  - `trace.jsonl`：每次追加一行 `{"started_at", "state", "code", "signal", "elapsed_ms"}`（排版同 Python `json.dumps`；`started_at`＝這次開始的時間〔C-54 命名方法 R6「時間點＝`<發生了什麼>_at`」〕，
    ISO 8601 UTC 到毫秒，同 Python `datetime.now(timezone.utc).isoformat(timespec="milliseconds")`（例 `2026-10-23T01:58:45.123+00:00`），P-38；
    `elapsed_ms`＝那格花了幾毫秒；`signal`＝停掉那格的訊號，沒有＝`null`）。**沒有 `timed_out`**（C-52：fsm 看不到格裡有沒有逾時；
    單子格逾時＝那格的 aos-exec 以 128＋N 正常結束，trace 是 `code` 143、`signal` null）。
- 只看格的結束碼：**不讀格的 stdout**（原樣接呼叫者的）、**不轉述格的 stderr**（N-38）。不開 ctl、lock，心跳不適用（N-39）。不讀 stdin。
- 每格不叫 PATH 上的 `aos-exec`，在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`；PATH 不動、原樣傳給那格（ideas § 24，見 aos-loop README 同一條）。

### 一次

1. 命令列不對、沒設 `AOS_STACK`、設定檔讀不到或指不到、表壞、查不到現在那格、`exec` 型別不對 → 自己的錯（state、trace 都不動）。
2. 跑那格（那層 aos-exec 的錯——入口不在、單子壞…：stderr 一行 `aos-exec: 代號 原因`、格的碼＝1）。
3. 追加 trace 一行。
4. 格的碼 **0** 才寫 `next`；10 與其他非 0（含被訊號停掉 128＋N、逾時）state 不動（下一次重跑同一格，P-20）。
5. 以格的碼結束（10 原樣往上，由 loop 決定停；fsm 不說話）。

trace 在 state 之前寫：trace 寫不了就不換狀態（下一次重跑同一格）。

### 訊號

同 aos-loop：整支程式擋著 SIGINT／SIGTERM／SIGHUP。跑格的期間收到就轉給那格（`kill` 給那格的 aos-exec 子行程；單子格再由它轉給整群），
等格結束，**trace 與 state 照常寫完**（格收好自己、退 0 就照樣換狀態），再以 **128＋N** 結束（P-36「寫好狀態再結束，但結束碼非 0」）。
跑格之前就收到：不跑，直接 128＋N。

## 元素

```
 main ──▶ block_signals ──▶ parse_cli ──▶ 要 AOS_STACK ──▶ read_table ──▶ read_state ──▶ pick ──▶ run_once（aos-loop）──▶ append_trace ──▶ write_state（碼 0）
```

跑一格借 aos-loop 的 `run_once`（格的 `exec` 跟 loop.json 的 `exec` 是同一個東西，訊號轉送也一樣）；fsm 不知道格是什麼（C-52）：`run_once` 只回碼、訊號、毫秒（沒有逾時）。沒有公開標頭（沒有別的專案要用 fsm 的庫）。

| 檔 | 做什麼 |
|---|---|
| `src/common/common.hpp` | `using`；代號（沿用 aos-loop 的，含 `StackMissing`；再加 `StateUnknown`） |
| `src/table/table.hpp`、`table.cpp` | `read_table`（`load_cfg` 讀 `檔` 或 `檔#/指標`、解指示詞（`resolve_table`）、驗 `start`／`states`）、`pick`（狀態名 → 那格：`exec` 用 aos-loop 的 `parse_target` 拆成目標與參數、物件＝單子（`place_inline` 填 `AOS_CF`／`AOS_CO`、`exec_bases` 記單子的 `$ref` 起點）；`next`） |
| `src/state/state.hpp`、`state.cpp` | `read_state`、`write_state`（`.state.txt` 再改名）、`append_trace`、`utc_now` |
| `src/main.cpp` | 命令列：`parse_cli`（旗標表空的）、要剛好一個設定檔；串上面；出錯印「aos-fsm: 代號 原因」 |

## 錯誤代號

自己出錯：stderr 一行 **`aos-fsm: 代號 原因`**、退 1（N-38、N-60）。跑格時才發現的錯，原因開頭是「狀態 X：」。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`（共用） | 沒給、多給設定檔 |
| `FlagUnknown`（共用） | 不認得的旗標（含 `--cfg`） |
| `StackMissing` | 沒設 `AOS_STACK`（或空的） |
| `DirectiveBad`（共用） | fsm.json 裡 fsm 讀的格（整份、`start`、`states`、每一格、`exec`、`next`）的指示詞解不開；那格的單子裡的指示詞跑的時候解不開 |
| `CfgMissing`（共用） | 設定檔不在；`#/` 指標指不到 |
| `CfgBad`（共用） | 設定檔讀不了、不是 JSON；`#` 後面不是 `/`；不是 `{"start": 字串, "states": 物件}`；開跑時查整張表不合：`start` 不在表上、某格不是 `{"exec", "next": 字串}`、`next` 不在表上／空字串／頭尾有空白／有換行、`exec` 不是字串、非空字串陣列或物件 |
| `EntryBad`（共用） | 那格的單子形狀不對（原因開頭「狀態 X：單子跑不起來：」） |
| `StateBad` | `$AOS_STACK/state.txt` 在但讀不了（沒權限、是資料夾、不是 UTF-8） |
| `StateUnknown` | state 檔裡的狀態不在表上 |
| `WriteFailed`（共用） | `trace.jsonl`、`.state.txt` 寫不了、改名不了（例 `AOS_STACK` 資料夾不在、單子格又沒人建它） |
| `LaunchFailed`、`Internal`（共用） | 跑格時 fork 失敗、準備轉送訊號失敗、那格的單子起不來（原因開頭「狀態 X：」） |

代號照 [10-23 命名統合](../../thinking/2026-10-23-naming.md)。

單子格壞、`$env` 沒設、起不來都是那格 aos-exec 的錯（它印一行、碼 1），fsm 只當那格非 0。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`）：
  A 段 state 在 stack 換、改名寫入、10 與失敗不換、字串格走 aos-exec、單子格逾時＝143、`$env`、trace 一次一行且沒有 `timed_out`、要 AOS_STACK、自己的錯一行、外層逾時整棵收掉；
  B 段用法、表／格壞的代號（含 `exec` 是物件、空陣列、元素不是字串）、空 state、trace 排版、字串格被訊號停掉、格的入口不在、不讀格的 stdout、相對路徑、PATH 原樣傳給格（§ 24）；
  C 段訊號（SIGTERM：格收好退 0 → state 照換、143；SIGINT 停掉單子格 → 130）與單子格的 `$ref` 從 fsm.json 的資料夾算、`argv[0]` 帶 `/` 又 exec 不了交給 aos-exec；
  D 段命令列（usage：多給、`--cfg`、不認得的旗標；`--` 結束旗標；設定檔 `檔#/指標`、指不到、`#` 後沒 `/`；`exec` 陣列）；
  E 段 state 在但讀不了（是資料夾、不是 UTF-8、沒權限）退 1 不跑、state 不在表上、state 去全形空白、開跑時查整張表（12 種壞法）、start／states／格／exec／next 的指示詞、解不開＝`DirectiveBad` 不跑、格的 body 不解；
  F 段 exec 直接放單子——`AOS_CF`／`AOS_CD`／`AOS_CO`（名字帶 `/` 跳脫）／cwd 與換 next、非 0、逾時（trace 143／15）、形狀壞（`EntryBad`／`DirectiveBad`，不寫 trace）、SIGTERM、`states` 拆檔時 `$ref` 的起點；設定檔 `檔#/指標` 的 `AOS_CO`、相對 `AOS_STACK`、捷徑 fsm.json。
  外層逾時那案要 `../aos-exec/bin/aos-exec`。
- `test_demo`（`tests/test_demo.py`）：**整合測試**。照 `proto8/demo/run.sh`，PATH 最前面放 impls 的 aos-exec、aos-loop、aos-fsm 的 `bin/`，把 `proto8/demo` 的 agent-bob（含它叫的 cathy、stamp）與 agent-ann 各跑一次，
  看結束碼 0、stderr 空、答案寫出來（`out/q1.txt`、`done/q1.txt`）。要先建好 `../aos-exec`、`../aos-loop` 自己的 `bin/`。（Python 版已刪：使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」。）
- `proto8/tests/test_fsm.py` 也拿這支跑。
