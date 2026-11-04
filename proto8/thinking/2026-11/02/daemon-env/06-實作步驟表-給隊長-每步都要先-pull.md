← [入口](README.md)｜涵蓋：實作步驟表（給隊長；每步都要先 pull）；工人提的三點（11-02，使用者）；aos-daemon-ctl 的定位（11-02，使用者）｜上一份 [05-方案-A-B-C-怎麼選-fable-的](05-方案-A-B-C-怎麼選-fable-的.md)

## 實作步驟表（給隊長；每步都要先 pull）

**前提**：另一位 Opus 隊長**正在改** `aos-daemon-ctl`、aos-daemon C++（子項小格搬 `loops/<名>/`、拿掉擋名字）、aos-mcp。**實作者要等那輪 commit 進 main、`git pull` 之後再開工**，不然 `aos-daemon-ctl` 的 `link_stack`／`unlink_stack`、eca_hub README 的小格路徑會改在舊版上。開工前在 WSL 跑 `python3 -m unittest proto8/tests/test_aos_daemon_ctl.py proto8/tests/test_eca_hub.py proto8/tests/test_daemon.py` 當基線（要先建好 `proto8/impls`）。

| # | 改哪 | 做什麼 | 驗證 |
|---|---|---|---|
| 1 | `proto8/bin/aos-daemon-ctl` | `daemon_dir()`：`--stack` ＞ `$AOS_DAEMON_STACK`；`DaemonMissing` 訊息加一句「`AOS_DAEMON` 現在是定義資料夾（若方向題 1 選 (b)），投遞請設 `AOS_DAEMON_STACK` 或 `--stack`」；docstring、USAGE 同步；`--daemon` 不再認（`FlagUnknown`，不留別名——KISS） | `test_aos_daemon_ctl.py`：`ctl()` 的 env 改 `AOS_DAEMON_STACK`；「`--daemon` 蓋過」那案改 `--stack`；加 1 案「只設 `AOS_DAEMON`＝`DaemonMissing`、訊息含 `AOS_DAEMON_STACK`」 |
| 2 | `proto8/extras/eca_hub/bin/aos-eca-hub` | 同第 1 步（`DAEMON` 從 `--stack`／`$AOS_DAEMON_STACK` 定；叫 aos-daemon-ctl 時改傳 `--stack`） | `test_eca_hub.py`：`CLEAR` 加 `AOS_DAEMON_STACK`（方案 A 再加另外兩個）、`e["AOS_DAEMON"]` 改名；DaemonMissing 那案照跑 |
| 3 | `proto8/bin/README.md`、`proto8/extras/eca_hub/README.md`（9 處）、`proto8/impls/aos-daemon/README.md`、`proto8/demo/daemon-3/README.md`（指令塊） | `$AOS_DAEMON` → `$AOS_DAEMON_STACK`、`--daemon` → `--stack`；eca README 的小格路徑照隊長那輪的 `loops/<名字>/` | 讀一遍；`grep -rn 'AOS_DAEMON\b' proto8 --include=*.md` 只剩 thinking 的歷史與 N-63 的「舊名」說明 |
| 4 | 條文：`NORMS/10-基礎設施-定義與工作區.md` N-63（加 11-02 補：改名、`--stack`、三名制當保留約定或退場〔照方向題 1〕、「一個 hub 一個變數」改讀成「一個資料夾一個名字」）、`NORMS/04` N-28 末句、`NORMS.md` 總表那列、`NORMS/附錄1-條號表.md` N-63 列、`NORMS/附錄2-各批出處.md` 加 11-02 一條、`CONCEPTS/附錄1-名詞.md`（若加三名制：一行「daemon 的三個變數」） | 原文與決定引本檔；不改 10-30 的歷史句，只加「11-02 改」 | `/wf-lint` 無壞連結 |
| 5 | code map：`wf/workflows/common/code-map/proto8.md`（aos-daemon-ctl 那行）、`code-map/proto8/06-周邊工具-3.md`（eca-hub 兩處）、`code-map/proto8/02-tests-2.md`（測試案數） | 同步名字與案數 | 跟程式對一遍 |
| 6 | **（方案 A 或方向題 2 選「做」才做）** `impls/aos-daemon/src/child/child.cpp`（`run_child` 多三個 `setenv`：`AOS_DAEMON`＝設定檔所在資料夾絕對路徑、`AOS_DAEMON_STACK`＝`stack_`、`AOS_DAEMON_WS`＝daemon 的 `AOS_WS`、沒有就不設）、`daemon.cpp`（建構時算定義資料夾、傳給 child）、impls README「給子項的三個變數」一段、N-64 ④ 加 daemon 例子 | `test_daemon.py` 加 1 案：exec 子項把 `env` 寫進檔，驗三個值；巢狀不測 | ctest／unittest 全綠 |
| 7 | `proto8/thinking/2026-11-02-playground-daemon.md`「給使用者的指令」 | `export AOS_DAEMON=$PWD/.stack` → `export AOS_DAEMON_STACK=$PWD/.stack`；本檔「決定」節補使用者的裁定 | — |
| 8 | `wf/WAIT_USER.md` | 一條：使用者在 `~/code/playground/ws` 親手試 `export AOS_DAEMON_STACK=$PWD/.stack && aos-daemon-ctl ls`、投一封信；（做了第 6 步）看 `.stack/loops/bob/stderr.txt` 或讓 bob 印 `env | grep AOS_DAEMON` | 使用者回報 |
| 9（方案 C） | `proto8/impls/aos-daemon/README.md` 加「把對外的窗切出 stack」一段＋`proto8/demo/daemon-3`（或新 demo）一份用 `{"$env": "控制口", "$path": …}` 的 daemon.json；`daemon.cpp`／`state` 寫法：`loops_state.json` 每列多一欄 `stack`＝小格絕對路徑；aos-daemon-ctl `link_stack`／`unlink_stack`、aos-eca-hub 的小格與歸檔改讀那欄；`extras/sandbox/root/setup.sh` 加 `--daemon-ctl 控制口`（信箱 2770＋ACL、state 644、ctl 600、說明 stack 700 不綁）；N-28 補一句「窗可用指示詞放到 stack 外」、N-17 loops_state 補 `stack` 欄 | 變數名等使用者定了才動；`test_daemon.py` 加 1 案（窗寫到另一夾、stack 裡沒有）、`test_aos_daemon_ctl.py` 加 1 案（控制口≠stack 時 `--ws` 捷徑仍指對小格）；setup.sh 乾跑 |
| 10 | 收尾 | `grep -rn 'AOS_DAEMON\b' proto8 wf --include=* \| grep -v thinking \| grep -v digest \| grep -v session_logs` 應只剩 N-63 說明舊名那幾行；session log 一行；一個 commit（程式＋測試＋README＋條文＋code map 同一個） | ctest 全綠（repo 根）、`python3 -m unittest discover -s proto8/tests` 在 WSL 全綠、`/wf-lint` |

不動的：wf/digest 兩處（歷史快照）、`wf/session_logs/archive`、proto2／舊 playground 的 `AOS_DAEMON_DIR`／`AOS_DAEMON_HOME`（凍結的舊 proto）、10-30 以前的 thinking。

## 工人提的三點（11-02，使用者）

小格改 `loops/<名>/` 時（[11-02 stack-tools § 實作結論](../stack-tools.md#實作結論11-02隊長代定可翻案)）工人提的三點；使用者原文在上面[決定](01-使用者原文-11-02-逐字.md#決定11-02使用者)那段（「3.a.那就是後續使用者要自己小心。b.自己小心。c.不用測試。」）。

- **(a) `loops` 成了 daemon stack 的保留名**（子項小格在 `.stack/loops/<名>/`，窗或信箱路徑取名 `loops` 會撞、程式不檢查）：使用者自己小心，不加檢查。
- **(b) 路徑 `./x/../s.json` 在 x 不存在時 `WriteFailed`**（沒先化簡路徑）：使用者自己小心，不改。
- **(c) 子項與信箱同名缺正向測試**：不補測試。

## aos-daemon-ctl 的定位（11-02，使用者）

使用者原文（逐字）：

> 對的，aos-daemon-ctl目前主要是對daemon底下的procs進行操作，對daemon本身操作這塊目前還是繼承於loop那樣，用ctl/state.json，往後可以給aos-daemon-ctl添加一些相關指令，但那是以後的事情

- aos-daemon-ctl 現在管 daemon **底下的子項**（add／rm／ls）。
- 對 daemon **本身**的操作（停、暫停、節奏）照 loop 的做法，寫它的 ctl 窗、讀它的 state 窗。
- 給 aos-daemon-ctl 加管 daemon 本身的指令：以後再說。
