# bin — aos-tick、aos-tools（Python）

← [proto8](../README.md)｜慣例：[CONVENTION](../docs/CONVENTION.md)｜demo：[demo](../demo/README.md)｜C++ 實作：[impls](../impls/README.md)｜測試：`python3 -m unittest discover -s proto8/tests`（先建 impls，見 [testing](../../wf/workflows/testing.md)）

> **C++（[proto8/impls](../impls/README.md)）是唯一實作**（使用者 10-23：「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 和 tick，使用者選「fsm 也改用 C++、tick 先留 Python」）：
> `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 的說明在各自的 README：[aos-exec](../impls/aos-exec/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-fsm](../impls/aos-fsm/README.md)、[aos-daemon](../impls/aos-daemon/README.md)；inst 是 C lib [inst](../impls/inst/README.md)。
> 這裡是 `aos-tick` 與 10-28 加的 `aos-tools`（Python，都用 `aos_flags.py` 的旗標解析 `parse`）。
> 刪掉的 bin 版各支逐支說明在 git 歷史：`git show 60d677cc:proto8/bin/README.md`。

```
sh proto8/demo/run.sh                                  # 建暫時工作區、放一題、跑 agent-bob、agent-ann，再用 aos-daemon 同時管兩隻，最後讓 aos-loop 跑 5 次 aos-tick；印工作區與 stack 樹
python3 -m unittest discover -s proto8/tests           # 四支 C++ 在 impls/<名>/bin/、aos-tick 在這裡（tests/aos_bins.py 放 PATH）
```

aos 的程式都不動 PATH（ideas § 24）：自己跑時把 `proto8/impls/<名>/bin/`（四支）與這個 `bin/`（aos-tick、aos-tools）放進 PATH，`demo/run.sh` 就是這樣做。

## 逐支說明

> **分層（[C-74](../docs/CONCEPTS/01-設計理念.md#分層10-22-使用者定)）**：`aos-tick` 擱置中、不歸層。（基礎層、標準庫那幾支只有 C++ 版，見 [impls](../impls/README.md)。）

- **`aos-tools - 一個 agent 資料夾一份工具註冊檔（tools.json），登記這隻 agent 能叫哪些工具`**（10-28；決定與代定 [thinking 10-28 aos-tools](../thinking/2026-10-28-aos-tools.md)；完整說明在檔頭 docstring）
  用法 `aos-tools [--file F] add [--override] [--name N] XXX｜rm XXX｜ls [--json]｜get XXX｜call 名`，註冊檔＝`--file`＞`./tools.json`（沒有＝沒登記任何工具）。
  **三種登記對象**（種類照 aos-exec 的認法，N-61）：資料夾（裡面 `_tooldef`，沒有再找 `_tooldef.json`）、沒 `+x` 的 JSON 檔（頂層 `_tooldef` key）、有 `+x` 的 python／可執行檔（`XXX --tooldef` 在 stdout 吐定義，結果依檔的 mtime＋大小快取在註冊檔）；不符合就報錯。工具定義＝OpenAI function 物件去掉 `name`。工具名＝`--name`＞檔名去副檔名（資料夾名），只收 `[A-Za-z0-9_-]`；撞名 `ToolExists`，`--override` 蓋掉。
  **存法**：`{"tools": {名: {"path": 絕對路徑, "cache"?: {...}}}}`；add 的相對路徑從 cwd 算、一律存絕對；手寫的相對路徑從註冊檔的資料夾算（範本用這個，搬家不斷）。有 `$ref`／`$env` 就交給 aos-json 解與改（`$ref` 陣列＝拆成好幾份，add 寫進最後一份）。
  **叫**：`call 名`——資料夾、JSON＝`aos-exec 路徑`，arguments 原樣從 stdin 進（P-41）；可執行檔＝arguments 寫成 `$AOS_STACK/tool_call.json`（沒設＝暫存檔、用完刪），`aos-exec 檔 --tool-call 那個檔`。結束碼是工具的。
  **錯**：stderr 一行 `aos-tools: 代號 原因`、退 1（`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`RegistryBad`、`PathMissing`、`ToolDefMissing`、`ToolDefBad`、`NameBad`、`ToolExists`、`ToolMissing`、`DirectiveBad`、`CommandMissing`、`WriteFailed`）；ls／get 碰到登記了但壞掉的工具也報錯。要 PATH 上有 aos-exec、aos-json。測試 `proto8/tests/test_aos_tools.py`。

- **`aos-tick - 把時鐘檔的回合數往前走一格`**（NAME，C-54 R1）
  用法 `aos-tick [旗標] FILE`（Python）：時鐘往前走一格（C-44：只是時鐘，不包任務、不保證什麼）。FILE 裡是回合數（十進位＋換行），讀出 n、寫回 n＋1 就退 0；FILE 不在＝0（第一次寫 1）；寫進 n＋1＝第 n 回合結束、第 n＋1 回合開始，mtime＝這回合從什麼時候開始。先寫同資料夾的 `.名字` 再改名蓋過去（N-05），不 fsync，stdout 不吐東西。**命令列**：唯一的位置參數就是 FILE（必給、只能一個、相對路徑從 cwd 算）；FILE 照字面用，`#` 不切指標（它是時鐘檔不是設定檔）；目前沒有旗標（旗標表是空的、走 `aos_flags`，`--` 結束旗標）。**自己的錯**退 1、stderr 一行 `aos-tick: 代號 原因`、FILE 不動：`ArgumentsBad usage: aos-tick [旗標] FILE（原因）`（跟 aos-loop、aos-fsm 同一個寫法）（沒給、多給；不認得的旗標是 `FlagUnknown usage: …`）、`ClockBad 時鐘檔讀不到：`（例：它是資料夾）、`ClockBad 時鐘檔壞：`（內容不是 `[0-9]+` 加可有可無的一個 `\n`；空檔、`\r\n`、空白、負號、全形數字都算壞）、`WriteFailed 時鐘檔寫不了：`（資料夾不在或沒寫入權限；不替人建資料夾，暫存檔會清掉）。節奏、停、只走 N 回合交給 loop（`max`、`interval_ms`、ctl 的 `paused`）；同一個 FILE 兩個人同時 tick 不管。

- `aos_flags.py`：命令列旗標解析 `parse(argv, 旗標表)` 回 `(opts, [XXX, args...])`（`--x V`／`--x=V`、重複給最後一個算、`--` 結束旗標、第一個不是旗標的參數起原樣；不認得＝`FlagUnknown`、缺值＝`ArgumentsBad`）。aos-tick、aos-tools 用。

執行中狀態（`state.txt`、`trace.jsonl`、`plan.txt`、`current.txt`）在 `$AOS_STACK`（預設 `$AOS_WS/.stack/`）；工作區只放交辦的東西與成果（題目 `new/` → 認領 `cur/` → `done/`，答案 `out/`）；定義資料夾不被寫，所以同一個 agent 可同時被兩個工作區跑。結果＝工作區內容；沒有別的結果通道。

## 已定值

- `AOS_ENTRY` 預設 `_entry`（使用者已定，[ideas § 13](../thinking/2026-10-19-ideas.md)），環境變數可覆寫。入口只佔資料夾的一層，跟 table 的一個 key 對上（`js["_entry"]`，C-72）；工作區的 `.stack/` 是 stack 的預設位置，跟入口無關。
- `AOS_STACK`（使用者已定）：預設 `$AOS_WS/.stack/`，是被叫的那個程式自己的 stack。它的子程式的 stack 由它自己訂（例如給 `$AOS_STACK/think`、`$AOS_STACK/act`），aos 不管巢狀。
- 工作區變數名 `AOS_WS`（使用者已定）。
- `aos-exec [--ws WS] XXX [args...]`（N-58；使用者「放前面吧。舊的寫法也要改」）：`--ws -`／沒給＝沿用 `$AOS_WS`，沒設才用 `.`（使用者 10-19 定）。
- `AOS_CF`、`AOS_CD`（使用者 10-19 下班前定，「同意做」）：實際被執行的檔、它所在的資料夾，aos-exec 每層覆寫（N-57；已做）。
- `AOS_CO`（使用者 10-21 晚「AOS_CF不動。但是我們再加上AOS_CO」「aos current obj」）：入口在 JSON 檔裡的指標，aos-exec 每層覆寫（N-57；已做）。aos-loop、aos-fsm、aos-daemon 的 `exec` 直接放單子物件時，跑那張單子的期間也把 `AOS_CF`／`AOS_CD`／`AOS_CO` 設成它的位置（設定檔、資料夾、`/exec` 或 `/states/<名>/exec`），跑完還原，見 [impls/aos-loop](../impls/aos-loop/README.md)、[thinking 10-24](../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)。
- `#/` 尋址（使用者 10-19 下班前定，「#/。」「尋址一定值得。」）：`檔#/指標` 指進 JSON（N-62；已做）。
