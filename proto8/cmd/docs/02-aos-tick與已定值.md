← [回入口 README.md](../README.md)｜段落：逐支說明、已定值｜上一份：[01-逐支說明](01-逐支說明.md)｜下一份：[03-aos-daemon-ctl](03-aos-daemon-ctl.md)

- **`aos-tick - 把時鐘檔的回合數往前走一格`**（NAME，C-54 R1）
  用法 `aos-tick [FLAGS] FILE`（Python）：時鐘往前走一格（C-44：只是時鐘，不包任務、不保證什麼）。FILE 裡是回合數（十進位＋換行），讀出 n、寫回 n＋1 就退 0；FILE 不在＝0（第一次寫 1）；寫進 n＋1＝第 n 回合結束、第 n＋1 回合開始，mtime＝這回合從什麼時候開始。先寫同資料夾的 `.名字` 再改名蓋過去（N-05），不 fsync，stdout 不吐東西。**命令列**：唯一的位置參數就是 FILE（必給、只能一個、相對路徑從 cwd 算）；FILE 照字面用，`#` 不切指標（它是時鐘檔不是設定檔）；目前沒有旗標（旗標表是空的、走 `aos_flags`，`--` 結束旗標）。**自己的錯**退 1、stderr 一行 `aos-tick: error: 代號 原因`、FILE 不動：`ArgumentsBad 原因 (usage: aos-tick [FLAGS] FILE)`（11-05 stdio-unify R5：原因在前；沒給、多給；不認得的旗標是 `FlagUnknown unknown flag … (usage: …)`）、`ClockBad cannot read clock file FILE: …`（例：它是資料夾）、`ClockBad clock file FILE is bad: …`（內容不是 `[0-9]+` 加可有可無的一個 `\n`；空檔、`\r\n`、空白、負號、全形數字都算壞）、`WriteFailed cannot write clock file FILE: …`（資料夾不在或沒寫入權限；不替人建資料夾，暫存檔會清掉）。節奏、停、只走 N 回合交給 loop（`max`、`interval_ms`、ctl 的 `pause`）；同一個 FILE 兩個人同時 tick 不管。

- `aos_flags.py`（在 [proto8/py](../../py/README.md)）：命令列旗標解析 `parse(argv, 旗標表)` 回 `(opts, [XXX, args...])`（`--x V`／`--x=V`、重複給最後一個算、`--` 結束旗標、第一個不是旗標的參數起原樣；不認得＝`FlagUnknown`、缺值＝`ArgumentsBad`）。cmd 的 Python 支都用。
  11-05 [stdio-unify](../../thinking/2026-11/05/stdio-unify/README.md) 加三扇門的共用小函式：`aos_flags.HELP`＝英文說明，設了 `parse` 在旗標的位置（子命令後再 parse 也算）看到 `--help` 就印到 stdout、退 0（R3）；`die(程式, 代號, 原因)`＝stderr 一行 `程式: error: 代號 原因`、退 1（`also_stdout=True` 兩邊各一行，給腦用的工具形）；`warn(程式, 句子)`＝提醒行 `程式: warning: 句子`（R1）；`error_line` 只組那一行；`run(main)`＝Ctrl-C 不吐 traceback、退 130（R12）。

執行中狀態（`stage.txt`、`plan.txt`、`current.txt`）在 `$AOS_STACK`（預設 `$AOS_WS/.stack/`）；工作區只放交辦的東西與成果（題目 `new/` → 認領 `cur/` → `done/`，答案 `out/`）；定義資料夾不被寫，所以同一個 agent 可同時被兩個工作區跑。結果＝工作區內容；沒有別的結果通道。

## 已定值

環境變數（`AOS_ENTRY` 預設 `_entry`、`AOS_WS`、`AOS_STACK` 預設 `$AOS_WS/.stack/`、`AOS_CF`、`AOS_CD`、`AOS_CO`）、`aos-exec [--ws WS] [--stack S] [--dotenv-override] XXX [args...]`、`#/` 尋址的定值在 [NORMS/10](../../docs/NORMS/10-基礎設施-定義與工作區.md)（N-57～N-62）與 [aos-exec](../../impls/aos-exec/README.md)；loop／fsm／daemon 跑內嵌單子時的 `AOS_CF`／`AOS_CD`／`AOS_CO` 見 [impls/aos-loop](../../impls/aos-loop/README.md)。使用者原話：旗標放前面（「放前面吧。舊的寫法也要改」）、`--stack` 預設（「預設還是要放工作區。要自動建。要沿用外面的。」）、`AOS_CF`／`AOS_CD`（「同意做」）、`AOS_CO`（「AOS_CF不動。但是我們再加上AOS_CO」「aos current obj」）、`#/` 尋址（「#/。」「尋址一定值得。」）。
