← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（10-19 proto8-2 併入、舊 lib 進 git 後重寫）

（新增或刪檔時這裡與 [proto8/bin/README.md](../../../../proto8/bin/README.md)（aos-tick、aos-tools）、[proto8/impls/README.md](../../../../proto8/impls/README.md)（四支 C++ 與庫）一起改。）

### `proto8/bin/`（Python 純標準庫）

逐支說明在 [proto8/bin/README.md](../../../../proto8/bin/README.md)。**10-23 Python 版刪了**（使用者 10-23）：`aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 與只有它們用的 `aos_inst.py`、`aos_loop.py`、`aos_run.py`、`aos_window.py` 刪了（在 git 歷史，刪前最後一版 60d677cc），四支只剩 C++ 版，見下面 `proto8/impls/`。

- `aos_flags.py`（10-21）：旗標解析 `parse()`（10-22 多收一張不帶值的旗標表 `switches`）；`Error.code`＝錯誤代號。aos-tick、aos-tools 用（10-23 刪了 `load_cfg()`、`target()`）。
- `aos-tools`（10-28）：agent 資料夾工具註冊檔 `tools.json` 的命令列；aos agent 範本與 aos-mcp 都經它。
- `aos-tick`（10-21 晚，計畫第 4 段）：`aos-tick [旗標] FILE`＝時鐘往前走一格，讀 n 寫 n＋1（沒檔＝0，先寫 `.名字` 再改名）；唯一的位置參數、旗標表是空的；錯退 1 一行 `aos-tick: 代號 原因`（10-23 起帶代號）、檔不動。

### `proto8/demo/`

說明在 [proto8/demo/README.md](../../../../proto8/demo/README.md)；`run.sh` 各建暫時工作區（題目 `new/` → `cur/` → `done/`、答案 `out/`）跑一遍並印整棵 stack 樹（`.stack/`）。

- `agent-bob/`（混合範本）：`_entry`＝`exec aos-loop loop.json`、`loop.json`＝`{"exec": "fsm.json", "max": 20}`；`fsm.json` 帶 `_entry`（本身是 aos-exec 入口，10-21）、idle／act 是子資料夾、think 是那格 `body` 裡的單子〔10-24 起單子直接寫在 `exec`〕；`act/tools/cathy/` 是另一隻完整 agent（同一套範本），她的 `act/tools/stamp/` 是最底層的工具——一次跑完四層巢狀。
- `agent-ann/`（全內嵌對照）：零子資料夾，`_entry`＝`exec aos-exec loop.json`（loop.json 帶 `_entry`），`fsm.json` 三格全是 `body` 裡的單子〔10-24 起直接寫在 `exec`，loop.json 的 `exec` 也是單子〕，各指 `idle.py`／`brain.py`／`act.py`。`.env`（10-22）是 demo 唯一的 `.env` 範例，全是註解（API key 與 `PATH=${AOS_CD}/bin:${PATH}` 的寫法；PATH 那行要最外層加 `--dotenv-override` 才生效、只多一份），不設任何東西。
- `agent-dan/`（10-23，真腦＋工具；慣例 [P-41](../../../../proto8/docs/CONVENTION/02-題目stack停錯腦.md)）：`_entry`＝`exec aos-loop loop.json`；`loop.json`＝`{"exec": "fsm.json", "max": 40}`；`fsm.json` 三態不變，idle 是資料夾、think／act 是 `body` 裡的單子〔10-24 起直接寫在 `exec`〕（120 秒、60 秒）；`.env` 給 `AOS_BRAIN_MODEL`（預設 `chatgpt-gpt-6-luna-low`）；`system.txt` 是 system 訊息（不進 history）；`idle/_entry` 同 bob；`brain.py`（think：認領題目、組 tools、帶 `$AOS_STACK/history.jsonl` 問腦、回覆接一行；沒設 `AOS_BRAIN_URL`＝假腦叫一次 clock）；`act.py`（act：有 `tool_calls` 就逐個 `aos-exec tools/<名>`、arguments 進 stdin、stdout 接回 history；沒有就寫答案、搬 `done/`；工具退非 0、沒有的工具、arguments 壞都接成 tool 訊息回給腦、不停，10-24 晚）；`tools/math/`（四則運算，stdin 收 `{"expr"}`；錯 stderr 與 stdout 各一行）、`tools/clock/`（印 UTC 時間）；各工具的 `_tooldef.json`＝給模型看的說明（function 物件去掉 name）。
- `agent-eve/`（10-24，agent 當工具；[thinking](../../../../proto8/thinking/2026-10-24-agent-as-tool.md)）：主 agent 照抄 agent-dan（`brain.py`、`act.py` 只改錯誤訊息開頭；act 逾時 30 分鐘），唯一的工具 `tools/pyfix/`：`_tooldef.json`（task、dir）、`_entry`（python3 轉接：開小格 `$AOS_STACK/runs/NNN/`、備份 `before/`、task 寫進子 agent 的 `ws/new/task.txt`、`aos-exec --dotenv-override --ws … agent`、印 `out/task.txt`＋實際 diff）、`agent/`（子 agent pyfix-agent，也是 agent-dan 範本：自己的 `system.txt`、`.env`、`loop.json` max 60；`tools/list_files`、`read_file`、`write_file`、`edit_file`、`run_python` 只碰 `$PYFIX_DIR`）。
- `daemon/`（10-20）：`_entry`＝`exec aos-daemon daemon.json`、子項 `exec`＝`daemon.json#/loops/<名字>/body`（10-21；10-23 深夜改名，原 `run`）〔10-24 起子項 `exec` 直接是單子〕；一個 daemon 同時管 bob、ann 兩個子 loop（工作區 `$AOS_WS/bob`、`$AOS_WS/ann`，stack 在 daemon 的小格裡）。
- `kernel-llm/`（10-24，[thinking](../../../../proto8/thinking/2026-10-24-llm-kernel.md)）：`_entry`（shell）設 `AOS_KERNEL=$AOS_STACK/mailbox` 並先建好、`exec aos-daemon "$@" daemon.json`（後面的參數原樣給 daemon，`--max` 改收工次數，10-24 真腦實測加）；`daemon.json` 管 kernel（`aos-kernel-llm kernel.json`，`interval_ms` 300）與 a、b、c 三個子項（各跑一次 `agent-ivy/`，環境變數 `BRAIN` 選腦的單子）；`kernel.json`＝`{"mailbox": {"$env": "AOS_KERNEL"}, "slots": 1, "budget": {…}}`（budget 10-24 下午 3fbcefcc 加）；`agent-ivy/`＝ann 式 agent（`idle.py`、`brain.py`〔假腦睡 1 秒〕、`act.py`），think 格 `exec` 是 `aos-gate $BRAIN`、stdout 導到 `plan.txt`；`agent-ivy/brains/` 三張腦的單子（`plain.json` normal、`quick.json` normal＋`_metainfo.time_ms` 800、`urgent.json` high＋5000）。
- `tick/`（10-21 晚）：`_entry`＝`exec aos-loop loop.json`、`loop.json` 跑 5 次 `loop.json#/body`〔10-24 起單子直接寫在 `exec`〕（`aos-tick $AOS_STACK/tick.txt`），跑完時鐘檔是 5。

### `proto8/tests/`

逐字下放到 [proto8/02-tests](proto8/02-tests.md)（2026-10-21 晚，本檔超過 8 KB）；10-24 新增的測試檔在 [proto8/08-tests-10-24](proto8/08-tests-10-24.md)（10-24 收尾實跑全部 452 個，5 個 skip；同日函式庫遷移後 453 個）。每個測試檔涵蓋什麼、幾個；共 248 個（10-23 改跑 C++ 版後 233，加 `test_dan.py` 14；10-24 `test_fsm.py` 的「物件＝表壞」換成兩案：物件＝內嵌單子、形狀壞＝自己的錯），`python3 -m unittest discover -s proto8/tests`（先建 impls）。

### `proto8/impls/` 與舊 lib

逐字下放到 [proto8/01-impls與舊lib](proto8/01-impls與舊lib.md)（2026-10-21 下午，本檔超過 8 KB）：impls 是使用者的 C／C++ 實作（10-23 起進 git；舊快照 `backup/` 10-23 已刪）；舊 lib 是 10-16 那套、10-19 刪進 git 歷史。

LLM kernel 兩支（`aos-kernel-llm`、`aos-gate`，10-24）的逐檔表另開一份：[proto8/03-kernel-llm](proto8/03-kernel-llm.md)。改 JSON 的工具集 `aos-json`（10-24）：[proto8/07-aos-json](proto8/07-aos-json.md)。

### 10-24 一天的嘗試（收尾補）

各作者做的時候沒改 code map，10-24 下午收尾一次補成幾份分檔：

- demo 的 agent（eve、fay、gus、hal、kai、liv、meg、pip、kernel-llm/agent-ivy）逐檔：[proto8/04-demo-agents](proto8/04-demo-agents.md)、[04-demo-agents-2](proto8/04-demo-agents-2.md)。
- demo 的 talk、self-improve、pi-tools、file-tools、kernel-llm 頂層：[proto8/05-demo-其他](proto8/05-demo-其他.md)、[05-demo-其他-2](proto8/05-demo-其他-2.md)。
- `proto8/extras/` 周邊工具 human、ai_tools、grow、langs/janet、langs/lua、editors/nvim、sandbox（10-26 從頂層收進）、cli_hub（10-27）：[proto8/06-周邊工具](proto8/06-周邊工具.md)、[06-周邊工具-2](proto8/06-周邊工具-2.md)；`proto8/lib`（函式庫，10-24 下午遷移後三層）：[proto8/09-lib](proto8/09-lib.md)。
- 10-24 新增的測試檔：[proto8/08-tests-10-24](proto8/08-tests-10-24.md)。
- 10-25 由上而下拆：`proto8/topdown/` 總覽與甲隊 galtxt-a [proto8/11-topdown-galtxt-a](proto8/11-topdown-galtxt-a.md)；乙隊 galtxt-b [proto8/10-topdown-galtxt-b](proto8/10-topdown-galtxt-b.md)。

改 proto8 的檔就同步那份。
