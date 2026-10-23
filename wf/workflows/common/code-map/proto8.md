← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（10-19 proto8-2 併入、舊 lib 進 git 後重寫）

（新增或刪檔時這裡與 [proto8/bin/README.md](../../../../proto8/bin/README.md)（aos-tick）、[proto8/impls/README.md](../../../../proto8/impls/README.md)（四支 C++ 與庫）一起改。）

### `proto8/bin/`（只剩 aos-tick，Python 純標準庫）

逐支說明在 [proto8/bin/README.md](../../../../proto8/bin/README.md)。**10-23 Python 版刪了**（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 也改 C++、tick 先留 Python）：`aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 與只有它們用的 `aos_inst.py`、`aos_loop.py`、`aos_run.py`、`aos_window.py` 刪了（在 git 歷史，刪前最後一版 60d677cc），四支只剩 C++ 版，見下面 `proto8/impls/`。

- `aos_flags.py`（10-21）：旗標解析 `parse()`（10-22 多收一張不帶值的旗標表 `switches`）；`Error.code`＝錯誤代號。10-23 起只有 aos-tick 用，設定檔的 `load_cfg()`、`target()` 跟著刪。
- `aos-tick`（10-21 晚，計畫第 4 段）：`aos-tick [旗標] FILE`＝時鐘往前走一格，讀 n 寫 n＋1（沒檔＝0，先寫 `.名字` 再改名）；唯一的位置參數、旗標表是空的；錯退 1 一行 `aos-tick: 代號 原因`（10-23 起帶代號）、檔不動。

### `proto8/demo/`

說明在 [proto8/demo/README.md](../../../../proto8/demo/README.md)；`run.sh` 各建暫時工作區（題目 `new/` → `cur/` → `done/`、答案 `out/`）跑一遍並印整棵 stack 樹（`.stack/`）。

- `agent-bob/`（混合範本）：`_entry`＝`exec aos-loop loop.json`、`loop.json`＝`{"exec": "fsm.json", "max": 20}`；`fsm.json` 帶 `_entry`（本身是 aos-exec 入口，10-21）、idle／act 是子資料夾、think 是那格 `body` 裡的單子；`act/tools/cathy/` 是另一隻完整 agent（同一套範本），她的 `act/tools/stamp/` 是最底層的工具——一次跑完四層巢狀。
- `agent-ann/`（全內嵌對照）：零子資料夾，`_entry`＝`exec aos-exec loop.json`（loop.json 帶 `_entry`），`fsm.json` 三格全是 `body` 裡的單子，各指 `idle.py`／`brain.py`／`act.py`。`.env`（10-22）是 demo 唯一的 `.env` 範例，全是註解（API key 與 `PATH=${AOS_CD}/bin:${PATH}` 的寫法；PATH 那行要最外層加 `--dotenv-override` 才生效、只多一份），不設任何東西。
- `agent-dan/`（10-23，真腦＋工具；慣例 [P-41](../../../../proto8/CONVENTION/02-題目stack停錯腦.md)）：`_entry`＝`exec aos-loop loop.json`；`loop.json`＝`{"exec": "fsm.json", "max": 40}`；`fsm.json` 三態不變，idle 是資料夾、think／act 是 `body` 裡的單子（120 秒、60 秒）；`.env` 給 `AOS_BRAIN_MODEL`（預設 `chatgpt-gpt-6-luna-low`）；`system.txt` 是 system 訊息（不進 history）；`idle/_entry` 同 bob；`brain.py`（think：認領題目、組 tools、帶 `$AOS_STACK/history.jsonl` 問腦、回覆接一行；沒設 `AOS_BRAIN_URL`＝假腦叫一次 clock）；`act.py`（act：有 `tool_calls` 就逐個 `aos-exec tools/<名>`、arguments 進 stdin、stdout 接回 history；沒有就寫答案、搬 `done/`）；`tools/math/`（四則運算，stdin 收 `{"expr"}`）、`tools/clock/`（印 UTC 時間）；各工具的 `tool.json`＝給模型看的說明（function 物件去掉 name）。
- `daemon/`（10-20）：`_entry`＝`exec aos-daemon daemon.json`、子項 `exec`＝`daemon.json#/loops/<名字>/body`（10-21；10-23 深夜改名，原 `run`）；一個 daemon 同時管 bob、ann 兩個子 loop（工作區 `$AOS_WS/bob`、`$AOS_WS/ann`，stack 在 daemon 的小格裡）。
- `tick/`（10-21 晚）：`_entry`＝`exec aos-loop loop.json`、`loop.json` 跑 5 次 `loop.json#/body`（`aos-tick $AOS_STACK/tick.txt`），跑完時鐘檔是 5。

### `proto8/tests/`

逐字下放到 [proto8/02-tests](proto8/02-tests.md)（2026-10-21 晚，本檔超過 8 KB）：每個測試檔涵蓋什麼、幾個；共 247 個（10-23 改跑 C++ 版後 233，加 `test_dan.py` 14），`python3 -m unittest discover -s proto8/tests`（先建 impls）。

### `proto8/impls/` 與舊 lib

逐字下放到 [proto8/01-impls與舊lib](proto8/01-impls與舊lib.md)（2026-10-21 下午，本檔超過 8 KB）：impls 是使用者的 C／C++ 實作（10-23 起進 git；舊快照 `backup/` 10-23 已刪）；舊 lib 是 10-16 那套、10-19 刪進 git 歷史。

改 proto8 的檔就同步那份。
