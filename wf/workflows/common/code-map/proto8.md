← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（10-19 proto8-2 併入、舊 lib 進 git 後重寫）

（新增或刪檔時這裡與 [proto8/bin/README.md](../../../../proto8/bin/README.md) 一起改。）

### `proto8/bin/`（Python 純標準庫）

逐支說明在 [proto8/bin/README.md](../../../../proto8/bin/README.md)。

- `aos-exec`（Python，10-19 晚從 sh 改寫，照 ideas § 14～§ 20、對齊 impls/aos-exec）：`aos-exec [--ws WS] XXX [args...]`（10-21 改：旗標在 XXX 前面、旗標表 `FLAGS`＋`parse()`、目前只有 `--ws`，舊的位置參數 WS 拿掉；10-21 下午 `parse()` 改用 `aos_flags`；impls 10-21 晚已對齊）——XXX 是資料夾／檔／`檔#/指標`、補找 `.json`；入口四種（`+x` 可執行檔 exec、argv 陣列 exec——兩者遇 +x 沒 `#!`（ENOEXEC）都同 execvp 改用 `/bin/sh` 跑（ideas § 22）；10-20 起 argv 陣列元素可放 `$env`／`$ref`（開跑前用 `aos_inst.resolve` 解）、argv[0] 帶 `/` 又 exec 不了＝前面插 `aos-exec`（`aos_inst.argv0`）、inst 單子行程內 `aos_inst.run()`、`js[$AOS_ENTRY]` 字串轉向含繞圈偵測）；export `AOS_WS`／`AOS_STACK`／`AOS_CF`／`AOS_CD`、cd 到入口檔所在的資料夾（PATH 不動，ideas § 24）、讀那裡的 `.env`（10-21：`load_env()`；`hop()`＝一次 aos-exec，`main()` 的迴圈讓字串轉向每一跳都是全新的一次、旗標只在第一跳；10-21 晚改順序：`locate()` 遇資料夾只回資料夾，`hop()` 走進去（cd、讀 `.env`、旗標蓋回）才照當下的 `$AOS_ENTRY` 挑，挑到資料夾就再走進去、一路往下；`find()` 判種類，沒 `argv` 的 JSON 物件當資料夾（`json_env()` 套 `.env` key、一路往下）；`set_env()` 是 `.env` 檔與 key 共用的一行規則；export 第六個 `AOS_CO`（入口在 JSON 檔裡的指標）；10-21 晚審後：多段 `$AOS_ENTRY` 中間經過的資料夾也進繞圈偵測、空的段不算一段（`_exec/`＝`_exec`），`AOS_CF`／`AOS_CD`／`AOS_CO` 自己設了就不蓋只看最後讀的那一份 `.env`（`find()` 回最後一份 JSON `.env` key 的名字、沒讀＝None）；impls 10-21 晚已對齊）；自己的錯退 1、一行 `aos-exec: 原因`。
- `aos-inst`＋`aos_inst.py`：讀一張單子（JSON，第一行 `#!` 丟掉）跑一次子程式；子程式自成行程群組、逾時與轉來的訊號打整群；單子裡 `{"$env": 名, "$path": …}` 換成環境變數底下的路徑、`{"$ref": "檔[#/指標]", "at": …}` 換成那份檔（或檔內位置）的值（10-20，`resolve(x, ref_base)`；`run(x, args, ref_base)`）；argv[0] 帶 `/` 又 exec 不了（資料夾、沒 +x、不在、帶 `#/`）改跑 PATH 上的 `aos-exec`（10-20，`argv0`）；`argv[0]` 是 +x 沒 `#!` 的檔就改用 `/bin/sh` 跑（同 execvp）；行程內用 `aos_inst.run()`（10-21 起只剩 aos-exec 用；結果多一個 `received`＝轉給子程式的第一個訊號；aos-inst 命令列留著，aos-exec 不再叫它）。
- `aos_beat.py`（§ 24）：loop、fsm 共用的「跑一拍」——接住三個訊號（`block`／`take`），`run(目標, args)`＝子行程 `aos-exec -- <目標> args...`、轉訊號給它；只收字串（10-21）；起不了丟 `StartError`。
- `aos_flags.py`（10-21）：旗標解析 `parse()`（aos-exec、loop、daemon、fsm 共用）、設定檔 `load_cfg()`（`檔[#/指標]`）、`run`／`val` 的 `target()`。
- `aos-loop`＋`aos_loop.py`（骨架＋薄命令列，aos-daemon 共用）：`aos-loop [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] loop.json`（10-21 傍晚：設定檔是唯一的位置參數、可寫 `檔#/指標`；旗標 ＞ 設定檔 ＞ 預設）；`run`＝aos-exec 的目標或 `[目標, 參數...]`、`max` 沒寫＝不限，選填 `interval_ms`、`ctl`、`state`；每圈 `aos-exec -- <run> 參數...`，退 10 就停、其他非 0 原碼結束；收到訊號轉給那拍、收完 128＋N；state 只在拍與拍之間寫。
- `aos_window.py`（10-20）：ctl／state 窗——`Ctl.read()`（paused／stop／max／interval_ms／seq＋程式多認的 key，壞的不採用、留上一份、記 `last_warning`）、`write()`（先寫 `.` 暫存再改名）、`beat()`（pid／started／boot_id／beat 心跳欄位）、`started(pid)`。
- `aos-daemon`（`aos_loop.Loop` 的子類別）：daemon.json＝loop.json 超集，加 `children`、`adopt`；每個子項的小格 `$AOS_STACK/<名字>/` 裡寫 loop.json（`run` 轉絕對、蓋上 `_exec`），經 `aos-exec -- 小格/loop.json#/_exec` 起子 loop（10-21 傍晚）；ctl 的 `children` 增減表；子 loop 結束不重起；結束前收掉所有子項（D7）；收到訊號 128＋N；重起時接回活著的子項。
- `aos-fsm`：`aos-fsm [旗標] fsm.json`（旗標表是空的；10-22 USAGE 補 `[旗標]`；10-21 傍晚：設定檔是唯一的位置參數、可寫 `檔#/指標`）；一拍只跑一格，`$AOS_STACK/state`（純文字一行）接著上一拍，`val`＝aos-exec 的目標或 `[目標, 參數...]`，每拍在 `trace.jsonl` 記一行；格的碼 0 才換狀態；收到訊號轉給那格、trace 與 state 照寫、再 128＋N。
- `aos-tick`（10-21 晚，計畫第 4 段）：`aos-tick [旗標] FILE`＝時鐘往前走一格，讀 n 寫 n＋1（沒檔＝0，先寫 `.名字` 再改名）；唯一的位置參數、旗標表是空的；錯退 1 一行、檔不動。

### `proto8/demo/`

說明在 [proto8/demo/README.md](../../../../proto8/demo/README.md)；`run.sh` 各建暫時工作區跑一遍並印整棵 stack 樹。

- `agent-bob/`（混合範本）：`_exec`＝`exec aos-loop loop.json`、`loop.json`＝`{"run": "fsm.json", "max": 20}`；`fsm.json` 帶 `_exec`（本身是 aos-exec 入口，10-21）、idle／act 是子資料夾、think 是那格 `body` 裡的單子；`act/tools/cathy/` 是另一隻完整 agent（同一套範本），她的 `act/tools/stamp/` 是最底層的工具——一次跑完四層巢狀。
- `agent-ann/`（全內嵌對照）：零子資料夾，`_exec`＝`exec aos-exec loop.json`（loop.json 帶 `_exec`），`fsm.json` 三格全是 `body` 裡的單子，各指 `idle.py`／`brain.py`／`act.py`。`.env`（10-22）是 demo 唯一的 `.env` 範例，全是註解（`PATH=${AOS_CD}/bin:${PATH}` 的寫法與「四層各讀一次、PATH 疊四份」的提醒），不設任何東西。
- `daemon/`（10-20）：`_exec`＝`exec aos-daemon daemon.json`、子項 `run`＝`daemon.json#/children/<名字>/body`（10-21）；一個 daemon 同時管 bob、ann 兩個子 loop（工作區 `$AOS_WS/bob`、`$AOS_WS/ann`，stack 在 daemon 的小格裡）。
- `tick/`（10-21 晚）：`_exec`＝`exec aos-loop loop.json`、`loop.json` 拍 5 次 `loop.json#/body`（`aos-tick $AOS_STACK/tick`），跑完時鐘檔是 5。

### `proto8/tests/`

逐字下放到 [proto8/02-tests](proto8/02-tests.md)（2026-10-21 晚，本檔超過 8 KB）：每個測試檔涵蓋什麼、幾個；共 223 個，`python3 -m unittest discover -s proto8/tests`。

### `proto8/impls/` 與舊 lib

逐字下放到 [proto8/01-impls與舊lib](proto8/01-impls與舊lib.md)（2026-10-21 下午，本檔超過 8 KB）：impls 是使用者的 C／C++ 實作（git 未追蹤、只在家中 Manjaro）；舊 lib 是 10-16 那套、10-19 刪進 git 歷史。

改 proto8 的檔就同步那份。
