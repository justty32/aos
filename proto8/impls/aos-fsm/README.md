# aos-fsm

**一句話：`aos-fsm [旗標] 設定檔.json`——一拍只跑一格：看 `$AOS_STACK/state` 記的現在狀態，跑那一格，格退 0 才把狀態換成 `next`，然後以格的碼結束。**
一個 lib（`lib/libaos-fsm.a`，沒有公開標頭）加一支薄薄的命令列（`bin/aos-fsm`）。連 [aos-loop](../aos-loop/README.md) 的公開 API（跑一格＝`run_beat`；它又帶進 aos-exec、inst、aos-util、aos-directive）。全家慣例見 [impls/README.md](../README.md)。

像大富翁只擲一次骰子：桌上一張地圖（`fsm.json`：每格寫著「走到這裡做什麼、做完去哪格」），棋子停在哪格記在一張小紙條上（`$AOS_STACK/state`）。
叫它一次，它就看紙條、做那格的事、做成了（0）才把棋子移到下一格，在流水帳（`trace.jsonl`）記一行，然後下班；做不成就留在原地、帶著那個碼回去。
要一直玩下去，就讓 aos-loop 一拍拍叫它。

```sh
cat fsm.json
# {"start": "idle", "states": {"idle": {"val": "idle", "next": "think"},
#   "think": {"val": "fsm.json#/states/think/body", "next": "act",
#             "body": {"argv": ["python3", "brain.py"], "stdout": {"$env": "AOS_STACK", "$path": "plan"}, "timeout_ms": 120000}},
#   "act": {"val": ["act", "--fast"], "next": "idle"}}}
AOS_STACK=st/ aos-fsm fsm.json; echo $?   # 跑 idle 那格（aos-exec -- idle）；退 0 → st/state 變 think
cat st/trace.jsonl   # {"at": "2026-10-19T14:07:00.123+00:00", "state": "idle", "code": 0, "signal": null, "elapsed_ms": 3}
```

行為比照 Python 版 `proto8/bin/aos-fsm`（10-21 傍晚版）；規則出處：CONVENTION P-07～P-10、P-20、P-21、P-36、P-38，NORMS N-36、N-38、N-39、N-41、N-05、N-43、N-60，ideas § 20、§ 23、§ 24。
**10-21 晚對齊 bin 版**（ideas 10-21 § 9、計畫 F2／F4）：命令列收旗標的寫法（目前沒有旗標）、設定檔可寫 `檔#/指標`；`val` 只收字串或 `[目標, 參數...]`；trace 拿掉 `timed_out`。
舊的 10-17 設計稿（`DESIGN.md`：stdin 讀表、格吐 `next`、state 窗 `{"phase"}`）已過時、刪掉，舊版在備份 `proto8/impls/backup/aos-impls-loop-fsm-daemon-2026-10-19-pre-rewrite.tar.gz`（10-23 已刪）。

## 用法

```
aos-fsm [旗標] 設定檔.json
```

- **命令列**：唯一的位置參數就是設定檔——必給、只能一個；可寫 `檔#/指標`（aos-util 的 `load_cfg`；例 `agent.json#/fsm`）。
  目前**沒有旗標**（旗標表是空的，規則同 aos-exec，aos-util 的 `parse_cli`）；`--` 結束旗標。不認得的旗標（含舊的 `--cfg`）＝`FlagUnknown`；沒給、多給＝`ArgumentsBad`
  （原因 `usage: aos-fsm [旗標] 設定檔.json（原因）`；10-22 bin 補 `[旗標]`，10-23 跟上）。
- **fsm.json**：`{"start": 起始狀態名, "states": {狀態名: {"val": 格, "next": 下一個狀態名}}}`。表一定明寫、`next` 只在表上（N-36）；其他 key 忽略（`body`、`_entry`…）。
  - `val`（aos-loop 的 `parse_target`，跟 loop.json 的 `val` 同一個名字、同一套寫法，C-55）＝**字串**（每拍 `aos-exec -- 它`）或**陣列 `[目標, 參數...]`**（`aos-exec -- 目標 參數...`）；
    相對路徑從 cwd 算（cwd 通常是 agent 資料夾，fsm 不轉）；WS 沿用 `$AOS_WS`、AOS_STACK 沿用（由那格的 aos-exec 定）。
  - `val` 寫成**物件＝`CfgBad`**（訊息提「要內嵌單子寫 fsm.json#/states/<名>/body」）：要內嵌單子就把單子放在同一格的 `body`、`val` 寫 `fsm.json#/states/<名>/body`，
    由那格的 aos-exec 在子行程裡跑、當監工（單子裡的 `$ref` 從 fsm.json 所在的資料夾算）。
  - **開跑時查整張表**（10-22 ideas § 7，`check`）：讀表後、跑格前，`start` 要在表上；每一格要是 `{"val", "next"}`、`val` 合法、`next` 是表上的狀態名、
    不是空字串、頭尾沒空白（認 Unicode 空白）、沒換行。哪一格不合都＝表壞 `CfgBad`、不跑格（原本只查這拍那一格）。
  - fsm.json 帶 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]` 時 `aos-exec fsm.json` 就是一拍；表在大 JSON 裡時寫 `{"$env": "AOS_CF", "$path": "#/fsm"}`（`$path` 字串拼接）。
- **`$AOS_STACK`**（必要）：fsm 自己的兩個檔都在這裡（只有 fsm 自己寫，N-39）：
  - `state`：純文字一行狀態名（跟 shell 版 fsm 同格式，可互換，P-07）。沒有、空的＝`start`；前後空白去掉（認 Unicode 空白，同 bin 的 `str.strip()`）。
    10-22 起**在但讀不了**（沒權限、是資料夾、不是 UTF-8）＝`StateBad`、不跑格（原本當沒有檔、從 `start` 起）；裡面的狀態不在表上＝`StateUnknown`。
    寫的時候先寫 `.state` 再改名蓋過去（N-05）。
  - `trace.jsonl`：每拍追加一行 `{"at", "state", "code", "signal", "elapsed_ms"}`（排版同 Python `json.dumps`；`at`＝這拍開始的時間，
    ISO 8601 UTC 到毫秒，同 Python `datetime.now(timezone.utc).isoformat(timespec="milliseconds")`（例 `2026-10-23T01:58:45.123+00:00`），P-38；
    `elapsed_ms`＝那格花了幾毫秒；`signal`＝停掉那格的訊號，沒有＝`null`；10-23 統合前 `at` 只到秒、`elapsed_ms` 叫 ms）。**沒有 `timed_out`**（C-52：fsm 看不到格裡有沒有逾時；
    單子格逾時＝那格的 aos-exec 以 128＋N 正常結束，trace 是 `code` 143、`signal` null）。
- 只看格的結束碼：**不讀格的 stdout**（原樣接呼叫者的）、**不轉述格的 stderr**（N-38）。不開 ctl、lock，心跳不適用（N-39）。不讀 stdin。

### 一拍

1. 命令列不對、沒設 `AOS_STACK`、設定檔讀不到或指不到、表壞、查不到現在那格、`val` 型別不對 → 自己的錯（state、trace 都不動）。
2. 跑那格（那層 aos-exec 的錯——入口不在、單子壞…：stderr 一行 `aos-exec: 代號 原因`、格的碼＝1，同 Python 版的子程序）。
3. 追加 trace 一行。
4. 格的碼 **0** 才寫 `next`；10 與其他非 0（含被訊號停掉 128＋N、逾時）state 不動（下一拍重跑同一格，P-20）。
5. 以格的碼結束（10 原樣往上，由 loop 決定停；fsm 不說話）。

### 訊號

同 aos-loop：整支程式擋著 SIGINT／SIGTERM／SIGHUP。跑格的期間收到就轉給那格（`kill` 給那格的 aos-exec 子行程；單子格再由它轉給整群），
等格結束，**trace 與 state 照常寫完**（格收好自己、退 0 就照樣換狀態），再以 **128＋N** 結束（P-36「寫好狀態再結束，但結束碼非 0」）。
跑格之前就收到：不跑，直接 128＋N。

## 元素

```
 main ──▶ block_signals ──▶ parse_cli ──▶ 要 AOS_STACK ──▶ read_table ──▶ read_state ──▶ pick ──▶ run_beat（aos-loop）──▶ append_trace ──▶ write_state（碼 0）
```

| 檔 | 做什麼 |
|---|---|
| `src/common/common.hpp` | `using`；代號（沿用 aos-loop 的，含 `StackMissing`；再加 `StateUnknown`） |
| `src/table/table.hpp`、`table.cpp` | `read_table`（`load_cfg` 讀 `檔` 或 `檔#/指標`、驗 `start`／`states`）、`pick`（狀態名 → 那格：`val` 用 aos-loop 的 `parse_target` 拆成目標與參數、物件＝CfgBad；`next`） |
| `src/state/state.hpp`、`state.cpp` | `read_state`、`write_state`（`.state` 再改名）、`append_trace`、`utc_now` |
| `src/main.cpp` | 命令列：`parse_cli`（旗標表空的）、要剛好一個設定檔；串上面；出錯印「aos-fsm: 代號 原因」 |

## 為什麼這樣做

- **跑一格借 aos-loop 的 `run_beat`**：格的 `val` 跟 loop.json 的 `val` 是同一個東西（`aos-exec -- 目標 參數...`），訊號轉送也一樣，寫一份。
  fsm 不知道格是什麼（C-52）：`run_beat` 只回碼、訊號、毫秒（沒有逾時）。
- **不開公開標頭**：沒有別的專案要用 fsm 的庫；之後真有人要再開。
- **trace 在 state 之前寫**：同 Python 版的順序；trace 寫不了就不換狀態（下一拍重跑同一格）。

## 錯誤代號

自己出錯：stderr 一行 **`aos-fsm: 代號 原因`**、退 1（N-38、N-60）。跑格時才發現的錯，原因開頭是「狀態 X：」。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`（共用） | 沒給、多給設定檔 |
| `FlagUnknown`（共用） | 不認得的旗標（含 `--cfg`） |
| `StackMissing` | 沒設 `AOS_STACK`（或空的） |
| `CfgMissing`（共用） | 設定檔不在；`#/` 指標指不到 |
| `CfgBad`（共用） | 設定檔讀不了、不是 JSON；`#` 後面不是 `/`；不是 `{"start": 字串, "states": 物件}`；開跑時查整張表不合（10-22）：`start` 不在表上、某格不是 `{"val", "next": 字串}`、`next` 不在表上／空字串／頭尾有空白／有換行、`val` 不是字串或非空字串陣列（物件也不行） |
| `StateBad` | `$AOS_STACK/state` 在但讀不了（沒權限、是資料夾、不是 UTF-8；10-22） |
| `StateUnknown` | state 檔裡的狀態不在表上（10-22 起格的形狀不對改算表壞 `CfgBad`） |
| `WriteFailed`（共用） | `trace.jsonl`、`.state` 寫不了、改名不了（例 `AOS_STACK` 資料夾不在、單子格又沒人建它） |
| `LaunchFailed`、`Internal`（共用） | 跑格時 fork 失敗、準備轉送訊號失敗（原因開頭「狀態 X：」） |

代號照 [10-23 命名統合](../../thinking/2026-10-23-naming.md)；統合前 `ArgumentsBad`／`FlagUnknown` 都叫 Usage、`CfgMissing`／`CfgBad` 叫 ReadFailed／JsonSyntax／FieldType、`StateBad` 叫 ReadFailed。

單子格壞、`$env` 沒設、起不來都是那格 aos-exec 的錯（它印一行、碼 1），fsm 只當那格非 0。

## 跟 Python 版 `proto8/bin/aos-fsm` 的差異

- 錯誤一行多了代號（Python 版 `aos-fsm: 原因`）。
- 每格不叫 PATH 上的 `aos-exec`，在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`（效果一樣）；PATH 不動、原樣傳給那格（ideas § 24，見 aos-loop README 同一條）。
- `trace.jsonl`／`.state` 寫不了：一行 `WriteFailed`、退 1（Python 版是 traceback）。
- 其他一樣：`proto8/tests/test_fsm.py` 19 案拿這支跑，只差錯誤一行的代號（抹掉代號全過；10-21 晚，方法見 [aos-exec](../aos-exec/README.md) 的「拿 proto8/tests 對照」）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`，29 組，約 1 秒）。10-21 起 `val` 不收內嵌單子：寫內嵌單子的案例由 `table()` 小工具換成 `fsm.json#/states/<名>/body`。
  A 段從 `proto8/tests/test_fsm.py` 移植（state 在 stack 換、改名寫入、10 與失敗不換、字串格走 aos-exec、
  單子格逾時＝143、`$env`、trace 一拍一行且沒有 `timed_out`、要 AOS_STACK、自己的錯一行、外層逾時整棵收掉），B 段是用法、表／格壞的代號（含 `val` 是物件、空陣列、元素不是字串）、空 state、trace 排版、
  字串格被訊號停掉、格的入口不在、不讀格的 stdout、相對路徑、PATH 原樣傳給格（§ 24），C 段是訊號（SIGTERM：格收好退 0 → state 照換、143；SIGINT 停掉單子格 → 130）與單子格的 `$ref` 從 fsm.json 的資料夾算、`argv[0]` 帶 `/` 又 exec 不了交給 aos-exec（10-20），
  D 段是 10-21 傍晚的命令列（usage：多給、`--cfg`、不認得的旗標；`--` 結束旗標；設定檔 `檔#/指標`、指不到、`#` 後沒 `/`；`val` 陣列）；
  E 段是 10-22（對照 `proto8/tests/test_fsm.py`）：state 在但讀不了（是資料夾、不是 UTF-8、沒權限）退 1 不跑、state 不在表上、state 去全形空白、開跑時查整張表（13 種壞法）。
  外層逾時那案要 `../aos-exec/bin/aos-exec`。
- `test_demo`（`tests/test_demo.py`，約 1 秒）：**整合測試**。照 `proto8/demo/run.sh`，把 `proto8/demo` 的 agent-bob（含它叫的 cathy、stamp）與 agent-ann
  各跑兩次——PATH 最前面放 impls 的 aos-exec、aos-loop、aos-fsm 的 `bin/`（拿掉 `proto8/bin`）一次、放 `proto8/bin` 一次——比結束碼、stderr、
  工作區（含 `.aos/` 整棵 stack 樹）的每個檔（`trace.jsonl` 的 `at`／`elapsed_ms`、stamp 的時間那行先抹掉）。要先建好 `../aos-exec`、`../aos-loop` 自己的 `bin/`。
