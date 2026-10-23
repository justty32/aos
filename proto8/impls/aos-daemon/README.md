# aos-daemon

**一句話：`aos-daemon [旗標] daemon.json`——一個開了窗的 aos-loop，外加一張子 loop 的表：照表把子 loop（經 aos-exec）起起來、看著、收掉。**
一個 lib（`lib/libaos-daemon.a`，沒有公開標頭）加一支薄命令列（`bin/aos-daemon`）。連 [aos-loop](../aos-loop/README.md) 的公開 API
（骨架 `aos::loop::Loop`；它又帶進 aos-exec、inst、aos-util、aos-directive）。全家慣例見 [impls/README.md](../README.md)。

**10-21 照新做法重寫**（使用者 10-19 晚「daemon也用新做法重寫吧」、10-20「照預設」，[ideas § 25](../../thinking/2026-10-19-ideas.md)；
計畫 [PLAN-2026-10-19.md](PLAN-2026-10-19.md)）。行為照 `proto8/bin/aos-daemon`（10-20，Python）——計畫跟 bin 版不一樣的地方（例：`ctl`／`state` 是檔名不是布林、
`loops` 的值收字串、沒有「另一個 daemon 還活著」的檢查）一律照 bin 版。舊的 10-16～17 那代（控制資料夾、策略格、table 窗）整個換掉，
舊碼在 `../backup/aos-impls-loop-fsm-daemon-2026-10-19-pre-rewrite.tar.gz` 與 `../backup/aos-impls-2026-10-21-pre-align.tar.gz`（10-23 都已刪）。
**10-21 晚對齊 bin 版 10-21 傍晚**（ideas 10-21 § 9、計畫 D7）：命令列同 aos-loop（收旗標、設定檔可寫 `檔#/指標`）；`val` 與 `loops` 的值收陣列；
子 loop 改成**經 aos-exec 起**（exec 成 PATH 上的 aos-loop），換掉 10-20 頂層代定的「fork 後在子行程裡直接跑 Loop」；收工時最後一拍之後才自己結束的子項也標結束（現行叫 `done`）。

像一個領班：手上一張名單（`loops`，10-23 統合前叫 children），名單上每個人各有一個小隔間（`$AOS_STACK/<名字>/`）。他每隔一會兒（`interval_ms`）看一眼佈告欄（ctl 窗）：
名單改了就把多的請走、少的叫來；誰自己下班了就在白板（state 窗）上記「done、結束碼幾」（被他請走的記「stopped」），**不會再叫他回來**。他自己收工時（不論為什麼）先把每個人都請走、
寫好白板，才走人。

```sh
cat daemon.json
# {"max": 10, "interval_ms": 200, "ctl": "ctl.json", "state": "state.json",
#  "loops": {"bob": {"val": "daemon.json#/loops/bob/body", "max": 1,
#                    "body": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}},
#            "ann": {"val": "daemon.json#/loops/ann/body", "max": 1,
#                    "body": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "ann"}, "../agent-ann"]}}}}
AOS_STACK=$PWD/.stack/ aos-daemon daemon.json     # 慣例用法是 aos-exec 它（proto8/demo/daemon）；PATH 上要有 aos-exec、aos-loop
```

## 用法

```
aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] daemon.json
```

命令列同 [aos-loop](../aos-loop/README.md)（共用 `loop_cli`）：唯一的位置參數＝設定檔（必給、只能一個；可寫 `檔#/指標`）；旗標放前面；起跑時 旗標 ＞ daemon.json ＞ 預設；
`loops`、`adopt` 只在 daemon.json。usage 錯一行 `aos-daemon: ArgumentsBad usage: aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] 設定檔.json（原因）`。

daemon.json＝loop.json 的超集（N-28）：

| key | 型別 | 沒寫 | 意思 |
|---|---|---|---|
| `val` | 字串或 `[目標, 參數...]` | 不跑 | 自己每拍的身體（同 aos-loop：每拍 `aos-exec -- 目標 參數...`；物件＝`CfgBad`；10-23 統合前叫 run）；純監工不寫 |
| `max` | 非負整數 | 不限 | 跑幾拍就收工（寫 `null` 不行，同 bin 版） |
| `interval_ms` | 非負整數 | 200 | 拍與拍之間至少隔幾毫秒 |
| `ctl`、`state` | 檔名 | 不開 | 兩扇窗，在 `$AOS_STACK` 底下（同 aos-loop） |
| `loops` | `{名字: 字串、陣列或物件}` | `{}` | 字串或陣列＝aos-exec 的目標（包成 `{"val": 它}`）；物件＝一份 loop.json 的內容（不驗，原樣交給子 loop，寫錯了子 loop 自己退 1）。子項要內嵌單子寫 `{"val": "daemon.json#/loops/<名字>/body", "body": 單子}` |
| `adopt` | 布林 | true | 起來時讀自己上次的 state，把還活著的子 loop 接回、不重起 |

- 要 `$AOS_STACK`（沒設＝`StackMissing`）。名字不能當資料夾名或會被 aos-exec 誤認（空、`.`、`..`、含 `/`、含 `#`、以 `.` 開頭）＝`CfgBad`。
- **名字不能跟自己的 ctl／state 撞名**（使用者 10-22，ideas 10-22 § 6；`taken_names`／`check_names`）：會撞的名字＝ctl、state（含旗標 `--ctl`／`--state` 給的）落在 `$AOS_STACK` 底下時
  相對路徑的第一段（`state.json`、`ctl.json`、`"w/c.json"` 的 `w`；`./x/../s.json` 整理成 `s.json`；在 stack 外面的、沒開的不算）。起來時撞＝`CfgBad`、退 1（10-23 統合前叫 Conflict）；
  ctl 改 `loops` 撞＝那份 ctl 整份不採用、維持上一份好的、原因進 state 的 `last_warning`。
- **起子 loop**（經 aos-exec，同 bin 版 10-21 傍晚）：小格 `$AOS_STACK/<名字>/` mkdir -p；設定補上 `"ctl": "ctl.json"`、`"state": "state.json"`（沒寫才補），
  **一律蓋上 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]`**，相對的 `val`（字串，或陣列的第一個元素）照 daemon 的 cwd 轉成絕對路徑（子 loop 的 cwd 會是小格），
  先寫 `.loop.json` 再改名成 `loop.json`；fork 一個子行程：`setsid` 自成 session、stdin／stdout 接 `/dev/null`、stderr 附加到小格的 `stderr.txt`（10-23 起帶 `.txt`，原 `stderr`）、`AOS_STACK=小格/`、
  解開三個訊號、cd 到 daemon 的 cwd，呼叫 aos-exec 的 `run_cli({"--", "小格/loop.json#/_entry"})`——它 cd 進小格、讀小格的 `.env`（若有）、
  設好 `AOS_CF`＝小格的 loop.json，再 **exec 成 PATH 上的 aos-loop**（pid 不變；指到 `#/_entry` 不受 `$AOS_ENTRY` 影響）。
  所以 **PATH 上要有 aos-loop 和 aos-exec**（`_entry` 的 `aos-loop` 照 PATH 找；子項裡要叫的 aos-exec 也是）；沒有＝子 loop 以 1 結束、原因寫在小格的 `stderr.txt`。
- **每拍**（Loop 讀完 ctl 之後）：期望表＝ctl 的 `loops`（有寫）或 daemon.json 的 → 表上多出來的收掉（SIGTERM 給那支子 loop，等 10 秒，還在就 SIGKILL 整群）並從表上拿掉（小格留著）
  （`phase: stopped`）→ 看誰自己結束了（`phase: done`，記 `code`／`signal`）→ 起表上少掉的 → 跑 `val`（有寫才跑）→ 寫 state（多一欄 `loops`：`{名字: {"pid", "start_ticks", "phase", "code", "signal"}}`）。
  `phase`：`running`＝還在跑、`done`＝子 loop 自己結束、`stopped`＝daemon 收掉它（送了 SIGTERM／SIGKILL）（`done`、`stopped` 10-23 統合前都叫 exited；`start_ticks` 統合前叫 started）。
- **子 loop 結束後不自動重起**：停在表上 `done`；要再起就從 ctl 的 `loops` 拿掉再放回，或重起 daemon。
- **ctl** 多認 `loops`（驗法同上，壞＝整份不採用、記 `last_warning`）。
- **adopt**：讀上次的 state（沒開 state 窗＝沒東西可接），`phase` 是 `running`、pid＋`start_ticks`（/proc 第 22 欄）對得上的放回表上、不重起；接回來的不是自己的子行程，之後看 /proc 判斷活不活，結束時 `code` 是 null。

### 結束碼

| 怎麼結束 | 結束碼 | stderr |
|---|---|---|
| 跑滿 `max`、ctl `stop`、身體退 10 | 0 | 不寫 |
| 身體退其他非 0 | 那個碼 | 一行 `aos-daemon: 第 N 拍 誰 失敗，結束碼 C`（10-23 統合前寫「第 N 圈」） |
| 收到 SIGINT／SIGTERM／SIGHUP | 128＋N | 不寫 |
| 自己的錯（設定壞、沒 AOS_STACK、子項起不來、state 寫不了） | 1 | 一行 `aos-daemon: 代號 原因` |

不論哪一種，都先收掉所有子 loop（同上：SIGTERM、10 秒、SIGKILL 整群）、寫好 state 再結束（P-36）：收掉的標 `stopped`；最後一拍之後才自己結束的子項標 `done`、記 `code`（計畫 D7）。子項的結束碼不影響 daemon 的。

## 元素

```
 main ──▶ block_signals ──▶ loop_cli ──▶ Daemon(opts, 設定檔)（Loop 的建構子＋AOS_STACK／loops／adopt）──▶ Loop::serve
   每拍 Daemon::tend ──▶ stop（多的）──▶ alive（看誰結束）──▶ spawn（少的：寫小格 loop.json、fork ──▶ run_cli({"--", 小格/loop.json#/_entry}) ──▶ exec 成 aos-loop）
   Daemon::info ──▶ loops 表；Daemon::finish ──▶ stop（全部，標 stopped）＋剛死的標 done；Daemon::check_ctl ──▶ ctl 的 loops
```

| 檔 | 做什麼 |
|---|---|
| `src/common/common.hpp` | `using`、代號（全沿用 aos-loop 的） |
| `src/child/child.hpp`、`child.cpp` | 一支子 loop：`spawn`（小格、loop.json（補 ctl／state、蓋 `_entry`、相對 val 轉絕對）、fork＋子行程 `run_child` 呼叫 aos-exec 的 `run_cli`）、`alive`、`row` |
| `src/daemon/daemon.hpp`、`daemon.cpp` | `Daemon`（`aos::loop::Loop` 的子類別）：建構子、`adopt`、`tend`、`stop`、`finish`（收全部標 stopped、剛死的標 done）、`info`、`check_ctl`；`check_loops`（名字不能帶 `/`、`#`、不能 `.` 開頭；值字串、陣列或物件）；`taken_names`、`check_names`（跟自己的 ctl／state 撞名，10-22） |
| `src/main.cpp` | 命令列：`block_signals` → `loop_cli` → `Daemon` → `serve`；出錯印「aos-daemon: 代號 原因」 |

## 為什麼這樣做

- **繼承 aos-loop 的 `Loop`**：daemon.json 是 loop.json 的超集，每拍讀 ctl、睡 interval、跑身體、寫 state、轉訊號都一樣；daemon 只多 tend／finish／info／check_ctl 四個掛鉤（同 bin 版 `aos_loop.Loop` 的子類別）。
- **子 loop 經 aos-exec 起**（使用者 10-21 傍晚「5.要」，同 bin 版 `aos-exec -- 小格/loop.json#/_entry`）：子 loop 跟別的程式一樣是「一個資料夾程式」——
  小格就是它的資料夾、`loop.json` 的 `_entry` 就是入口，所以小格裡放 `.env` 也有作用。fork 後在子行程裡呼叫 aos-exec 的 `run_cli`（不必在 PATH 上找 aos-exec），
  它最後 exec 成 PATH 上的 aos-loop，所以 `ps` 看到的子 loop 叫 `aos-loop`。原本 10-20 頂層代定的「fork 後在子行程裡直接跑 aos-loop 的 `Loop`、`ps` 上叫 `aos-daemon`」換掉。
  fork 時 daemon 只有一條執行緒，子行程裡 C++ 配置、setenv 安全；三個訊號 daemon 一開始就擋著，子行程 exec 之前解開（遮罩會跨 exec 繼承；同 bin 版 Popen 起的子行程沒擋）。
- **相對的 val 照 daemon 的 cwd 轉絕對**：子 loop 經 aos-exec 起之後 cwd 是小格，不轉的話 `"val": "../agent-bob"` 會從小格算。只轉字串與陣列的第一個元素，其他不動、不驗。

## 跟 Python 版 `proto8/bin/aos-daemon` 的差異

- 錯誤一行多了代號（Python 版 `aos-daemon: 原因`）。
- 起子 loop 不叫 PATH 上的 `aos-exec`，在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`（效果一樣）；之後 exec 成 PATH 上的 aos-loop 這段兩版一樣，PATH 上都要有 aos-loop。
- state 窗寫不了：這版是 `WriteFailed` 一行、先收子 loop、退 1；Python 版是 traceback。
- 其他行為一樣：`proto8/tests/test_daemon.py` 15 案拿這支跑，只差 usage 那行的代號（抹掉代號全過；10-21 晚）；demo/daemon 兩條線結果逐檔一樣（`tests/test_demo.py`）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`，20 案、unittest）：10-21 傍晚照 `proto8/tests/test_daemon.py` 重新逐案抄一次 15 案（loop.json 直接丟給 daemon、要 AOS_STACK、loops 壞、小格與窗、
  不自動重起、子項 stderr 在小格、ctl 增減、SIGTERM 收子項 143、旗標蓋過設定、val 陣列與設定檔規則、子 loop 經 aos-exec 起、字串子項是 aos-exec 的目標、
  收工時剛死的子項標 done、收掉的標 stopped、adopt、`adopt: false`），加錯誤代號、子 loop 的 state 心跳是自己的 pid；10-23 再抄 bin 10-22 的 3 案（daemon 重開照名單起停機期間死掉的子項、子項撞名起來時退 1〔另驗 `--state` 旗標也算〕、ctl 撞名不採用）。PATH 放 impls 的 aos-exec、aos-loop 兩支的 `bin/`（子 loop 要 exec 成 PATH 上的 aos-loop）。
- `test_demo`（`tests/test_demo.py`）：`proto8/demo/daemon` 在 impls 線（PATH 只放 impls 四支的 `bin/`）與 bin 線各跑一次，比結束碼、stderr、整棵工作區與 stack 的檔與內容。
  要先建好 ../aos-exec、../aos-loop、../aos-fsm 的 `bin/`（`test_cli` 也要前兩支）。
