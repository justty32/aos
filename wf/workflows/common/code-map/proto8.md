← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（10-19 proto8-2 併入、舊 lib 進 git 後重寫）

（新增或刪檔時這裡與 [proto8/bin/README.md](../../../../proto8/bin/README.md) 一起改。）

### `proto8/bin/`（Python 純標準庫＋一支 sh）

逐支說明在 [proto8/bin/README.md](../../../../proto8/bin/README.md)。

- `aos-exec`（sh）：`aos-exec DIR [WS [args...]]`——設 `AOS_WS`、`AOS_STACK`，bin 放進 PATH，`cd DIR`，`exec` 入口（`$AOS_ENTRY`，預設 `.aos/exec`；沒有可執行檔但有旁邊的 `.json` 就交給 aos-inst）；自己的錯退 1。
- `aos-inst`＋`aos_inst.py`：讀一張單子（JSON，第一行 `#!` 丟掉）跑一次子程式；子程式自成行程群組、逾時與轉來的訊號打整群；單子裡 `{"$env": 名, "path": …}` 換成環境變數底下的路徑；行程內用 `aos_inst.run()`。
- `aos-loop`：`loop.json` 的 `{"run", "max"}`，每圈 `aos-exec` 子資料夾或跑一張單子，子程式退 10 就停（loop 以 0 結束）、其他非 0 原碼結束。
- `aos-fsm`：一拍只跑一格，`$AOS_STACK/state`（純文字一行）接著上一拍，每拍在 `trace.jsonl` 記一行；格的碼 0 才換狀態。

### `proto8/demo/`

說明在 [proto8/demo/README.md](../../../../proto8/demo/README.md)；`run.sh` 各建暫時工作區跑一遍並印整棵 stack 樹。

- `agent-bob/`（混合範本）：`.aos/exec`＝`exec aos-loop loop.json`；`fsm.json` 一份看完整張表（idle／act 是子資料夾、think 是內嵌單子 `python3 brain.py`）；`act/tools/cathy/` 是另一隻完整 agent（同一套範本），她的 `act/tools/stamp/` 是最底層的工具——一次跑完四層巢狀。
- `agent-ann/`（全內嵌對照）：零子資料夾，`fsm.json` 三格全是單子，各指 `idle.py`／`brain.py`／`act.py`。

### `proto8/tests/`（65 個）

`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與巢狀、N-05／N-43 的寫法）、`test_inst.py`（aos-inst）、`test_fsm.py`（aos-fsm）；`python3 -m unittest discover -s proto8/tests`，在 WSL／Linux 跑。

### 舊 lib（10-16 那套，已刪）

`proto8/lib/`（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick，27 支模組＋說明＋12 個測試檔 169 個）與舊 `bin/aos`、六組舊 demo（daemon、fsm、paint、kernels、tasks、tick），10-19 刪進 git 歷史；要找回：`git show aa2fec1f:proto8/lib/README.md`（逐檔表）。daemon、kernel、tasks、tick、腦的工具呼叫現無實作，待照新做法重寫（[NORMS 待定](../../../../proto8/NORMS/08-待定.md)）。

改 proto8 的檔就同步那份。
