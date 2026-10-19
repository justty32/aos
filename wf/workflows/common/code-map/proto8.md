← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（10-19 proto8-2 併入、舊 lib 進 git 後重寫）

（新增或刪檔時這裡與 [proto8/bin/README.md](../../../../proto8/bin/README.md) 一起改。）

### `proto8/bin/`（Python 純標準庫）

逐支說明在 [proto8/bin/README.md](../../../../proto8/bin/README.md)。

- `aos-exec`（Python，10-19 晚從 sh 改寫，照 ideas § 14～§ 20、對齊 impls/aos-exec）：`aos-exec XXX [WS [args...]]`——XXX 是資料夾／檔／`檔#/指標`、補找 `.json`；入口四種（`+x` 可執行檔 exec、argv 陣列 exec——兩者遇 +x 沒 `#!`（ENOEXEC）都同 execvp 改用 `/bin/sh` 跑（ideas § 22）、inst 單子行程內 `aos_inst.run()`、`js[$AOS_ENTRY]` 字串轉向含繞圈偵測）；export `AOS_WS`／`AOS_STACK`／`AOS_CF`／`AOS_CD`、bin 放進 PATH、cd 到入口檔所在的資料夾；自己的錯退 1、一行 `aos-exec: 原因`。
- `aos-inst`＋`aos_inst.py`：讀一張單子（JSON，第一行 `#!` 丟掉）跑一次子程式；子程式自成行程群組、逾時與轉來的訊號打整群；單子裡 `{"$env": 名, "path": …}` 換成環境變數底下的路徑；`argv[0]` 是 +x 沒 `#!` 的檔就改用 `/bin/sh` 跑（同 execvp）；行程內用 `aos_inst.run()`（aos-exec、aos-loop、aos-fsm 都這樣用；aos-inst 命令列留著，aos-exec 不再叫它）。
- `aos-loop`：`loop.json` 的 `{"run", "max"}`，每圈 `aos-exec` 子資料夾或跑一張單子，子程式退 10 就停（loop 以 0 結束）、其他非 0 原碼結束。
- `aos-fsm`：一拍只跑一格，`$AOS_STACK/state`（純文字一行）接著上一拍，每拍在 `trace.jsonl` 記一行；格的碼 0 才換狀態。

### `proto8/demo/`

說明在 [proto8/demo/README.md](../../../../proto8/demo/README.md)；`run.sh` 各建暫時工作區跑一遍並印整棵 stack 樹。

- `agent-bob/`（混合範本）：`_exec`＝`exec aos-loop loop.json`；`fsm.json` 一份看完整張表（idle／act 是子資料夾、think 是內嵌單子 `python3 brain.py`）；`act/tools/cathy/` 是另一隻完整 agent（同一套範本），她的 `act/tools/stamp/` 是最底層的工具——一次跑完四層巢狀。
- `agent-ann/`（全內嵌對照）：零子資料夾，`fsm.json` 三格全是單子，各指 `idle.py`／`brain.py`／`act.py`。

### `proto8/tests/`（93 個）

`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與巢狀、N-05／N-43 的寫法）、`test_exec_rules.py`（aos-exec 的 § 14～§ 20 新規則，28 個，移植自 impls/aos-exec 的 test_cli.py）、`test_inst.py`（aos-inst）、`test_fsm.py`（aos-fsm）；`python3 -m unittest discover -s proto8/tests`，在 WSL／Linux 跑。

### 舊 lib（10-16 那套，已刪）

`proto8/lib/`（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick，27 支模組＋說明＋12 個測試檔 169 個）與舊 `bin/aos`、六組舊 demo（daemon、fsm、paint、kernels、tasks、tick），10-19 刪進 git 歷史；要找回：`git show aa2fec1f:proto8/lib/README.md`（逐檔表）。daemon、kernel、tasks、tick、腦的工具呼叫現無實作，待照新做法重寫（[NORMS 待定](../../../../proto8/NORMS/08-待定.md)）。

改 proto8 的檔就同步那份。
