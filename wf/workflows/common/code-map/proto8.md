← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（10-19 proto8-2 併入、舊 lib 進 git 後重寫）

（新增或刪檔時這裡與 [proto8/bin/README.md](../../../../proto8/bin/README.md) 一起改。）

### `proto8/bin/`（Python 純標準庫）

逐支說明在 [proto8/bin/README.md](../../../../proto8/bin/README.md)。

- `aos-exec`（Python，10-19 晚從 sh 改寫，照 ideas § 14～§ 20、對齊 impls/aos-exec）：`aos-exec [--ws WS] XXX [args...]`（10-21 改：旗標在 XXX 前面、旗標表 `FLAGS`＋`parse()`、目前只有 `--ws`，舊的位置參數 WS 拿掉；impls 未對齊）——XXX 是資料夾／檔／`檔#/指標`、補找 `.json`；入口四種（`+x` 可執行檔 exec、argv 陣列 exec——兩者遇 +x 沒 `#!`（ENOEXEC）都同 execvp 改用 `/bin/sh` 跑（ideas § 22）；10-20 起 argv 陣列元素可放 `$env`／`$ref`（開跑前用 `aos_inst.resolve` 解）、argv[0] 帶 `/` 又 exec 不了＝前面插 `aos-exec`（`aos_inst.argv0`）、inst 單子行程內 `aos_inst.run()`、`js[$AOS_ENTRY]` 字串轉向含繞圈偵測）；export `AOS_WS`／`AOS_STACK`／`AOS_CF`／`AOS_CD`、cd 到入口檔所在的資料夾（PATH 不動，ideas § 24）、讀那裡的 `.env`（10-21：`load_env()`；`hop()`＝一次 aos-exec，`main()` 的迴圈讓字串轉向每一跳都是全新的一次、旗標只在第一跳；impls 尚未支援）；自己的錯退 1、一行 `aos-exec: 原因`。
- `aos-inst`＋`aos_inst.py`：讀一張單子（JSON，第一行 `#!` 丟掉）跑一次子程式；子程式自成行程群組、逾時與轉來的訊號打整群；單子裡 `{"$env": 名, "path": …}` 換成環境變數底下的路徑、`{"$ref": "檔[#/指標]", "at": …}` 換成那份檔（或檔內位置）的值（10-20，`resolve(x, ref_base)`；`run(x, args, ref_base)`）；argv[0] 帶 `/` 又 exec 不了（資料夾、沒 +x、不在、帶 `#/`）改跑 PATH 上的 `aos-exec`（10-20，`argv0`）；`argv[0]` 是 +x 沒 `#!` 的檔就改用 `/bin/sh` 跑（同 execvp）；行程內用 `aos_inst.run()`（aos-exec 直接用、aos-loop／aos-fsm 經 `aos_beat`；結果多一個 `received`＝轉給子程式的第一個訊號；aos-inst 命令列留著，aos-exec 不再叫它）。
- `aos_beat.py`（§ 24）：aos-loop、aos-fsm 共用的「跑一拍」——接住 SIGINT／SIGTERM／SIGHUP（`block`／`take`），`run` 字串＝子行程 `aos-exec`、轉訊號給它，單子＝`aos_inst.run()`；回碼、訊號、逾時、毫秒、`received`。
- `aos-loop`＋`aos_loop.py`（10-20 拆成骨架＋薄命令列，aos-daemon 共用）：`loop.json` 的 `{"run", "max"}`，選填 `interval_ms`（拍間至少隔幾毫秒）、`ctl`、`state`（窗的檔名，在 `$AOS_STACK` 底下）；每圈 `aos-exec` 子資料夾或跑一張單子，子程式退 10 就停（loop 以 0 結束）、其他非 0 原碼結束；收到訊號轉給那拍、收完 128＋N；state 只在拍與拍之間寫（心跳）。
- `aos_window.py`（10-20）：ctl／state 窗——`Ctl.read()`（paused／stop／max／interval_ms／seq＋程式多認的 key，壞的不採用、留上一份、記 `last_warning`）、`write()`（先寫 `.` 暫存再改名）、`beat()`（pid／started／boot_id／beat 心跳欄位）、`started(pid)`。
- `aos-daemon`（10-20，`aos_loop.Loop` 的子類別）：daemon.json＝loop.json 超集，加 `children`（`{名字: loop 設定}`）、`adopt`；每個子項的小格 `$AOS_STACK/<名字>/`，在裡面寫 loop.json、起 `aos-loop`；ctl 的 `children` 增減表；子 loop 結束不重起；結束前收掉所有子項；收到訊號 128＋N；重起時照 state 接回活著的子項。
- `aos-fsm`：一拍只跑一格，`$AOS_STACK/state`（純文字一行）接著上一拍，每拍在 `trace.jsonl` 記一行；格的碼 0 才換狀態；收到訊號轉給那格、trace 與 state 照寫、再 128＋N。

### `proto8/demo/`

說明在 [proto8/demo/README.md](../../../../proto8/demo/README.md)；`run.sh` 各建暫時工作區跑一遍並印整棵 stack 樹。

- `agent-bob/`（混合範本）：`_exec`＝`exec aos-loop loop.json`；`fsm.json` 一份看完整張表（idle／act 是子資料夾、think 是內嵌單子 `python3 brain.py`）；`act/tools/cathy/` 是另一隻完整 agent（同一套範本），她的 `act/tools/stamp/` 是最底層的工具——一次跑完四層巢狀。
- `agent-ann/`（全內嵌對照）：零子資料夾，`fsm.json` 三格全是單子，各指 `idle.py`／`brain.py`／`act.py`。
- `daemon/`（10-20）：`_exec`＝`exec aos-daemon daemon.json`；一個 daemon 同時管 bob、ann 兩個子 loop（工作區 `$AOS_WS/bob`、`$AOS_WS/ann`，stack 在 daemon 的小格裡）。

### `proto8/tests/`（168 個）

`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與巢狀、N-05／N-43 的寫法）、`test_exec_rules.py`（aos-exec 的 § 14～§ 20 新規則，28 個，移植自 impls/aos-exec 的 test_cli.py）、`test_inst.py`（aos-inst）、`test_fsm.py`（aos-fsm，含訊號與 PATH 原樣）、`test_loop.py`（直接叫 aos-loop：訊號、PATH 原樣，§ 24；interval_ms、ctl、state 窗）、`test_daemon.py`（aos-daemon：children、ctl 增減、不重起、收工、接回）、`test_directive_argv.py`（10-20 ideas D1～D8：`$ref` 的 `#/` 與 `at`、argv 陣列放指示詞、argv[0] 交給 aos-exec，17 個）、`test_directive_lenient.py`（10-20 D9～D15）、`test_exec_env.py`（10-21 `.env`：設值、`${}` 與 PATH、優先順序、轉向兩層、錯誤不印值，12 個）；`python3 -m unittest discover -s proto8/tests`，在 WSL／Linux 跑。

### `proto8/impls/`（使用者的 C／C++ 實作，git 未追蹤）

總入口與逐專案說明在 `proto8/impls/README.md`（未追蹤，只在家中 Manjaro）。10-21 對齊 bin 版 10-20：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（`inst` C lib、`aos-util`、`aos-directive`、`aos-schema` 是庫）；
aos-loop 的骨架是公開的 `aos::loop::Loop`（`src/engine/`），aos-daemon 繼承它、子 loop 是 fork 後在子行程裡跑同一個 Loop；指示詞（`$ref` 的 `#/`／`at`、`$path`、`$prefix`、寫法寬容）在 aos-directive，
argv 陣列入口的指示詞與「argv[0] 帶 `/` 又 exec 不了交給 aos-exec」在 aos-exec（`launch.cpp`、`run_inst`）。動工前的樣子備份在 `proto8/impls/backup/aos-impls-2026-10-21-pre-align.tar.gz`。

### 舊 lib（10-16 那套，已刪）

`proto8/lib/`（inst、loop、daemon、fsm、agent 格庫、兩種 kernel、tasks、tick，27 支模組＋說明＋12 個測試檔 169 個）與舊 `bin/aos`、六組舊 demo（daemon、fsm、paint、kernels、tasks、tick），10-19 刪進 git 歷史；要找回：`git show aa2fec1f:proto8/lib/README.md`（逐檔表）。daemon 10-20 已照新做法重寫（上面 `aos-daemon`）；kernel、tasks、tick、腦的工具呼叫現無實作，待照新做法重寫（[NORMS 待定](../../../../proto8/NORMS/08-待定.md)）。

改 proto8 的檔就同步那份。
