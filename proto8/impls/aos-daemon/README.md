# aos-daemon

`aos-daemon - 照一張名單，把幾個 aos-loop 各自起在自己的小格裡、看著它們`（NAME，C-54 R1）

**一句話：`aos-daemon [旗標] daemon.json`——一個開了窗的 aos-loop，外加一張子 loop 的表：照表把子 loop（經 aos-exec）起起來、看著、收掉。**
一個 lib（`lib/libaos-daemon.a`，沒有公開標頭）加一支薄命令列（`bin/aos-daemon`）。連 [aos-loop](../aos-loop/README.md) 的公開 API
（骨架 `aos::loop::Loop`；它又帶進 aos-exec、inst、aos-util、aos-directive）。全家慣例見 [impls/README.md](../README.md)。

**10-21 照新做法重寫**（使用者 10-19 晚「daemon也用新做法重寫吧」、10-20「照預設」，[ideas § 25](../../thinking/2026-10-19-ideas.md)；
計畫 [PLAN-2026-10-19.md](PLAN-2026-10-19.md)）。行為照 `proto8/bin/aos-daemon`（10-20，Python）——計畫跟 bin 版不一樣的地方（例：`ctl`／`state` 是檔名不是布林、
`loops` 的值收字串、沒有「另一個 daemon 還活著」的檢查）一律照 bin 版。舊的 10-16～17 那代（控制資料夾、策略格、table 窗）整個換掉，
舊碼在 `../backup/aos-impls-loop-fsm-daemon-2026-10-19-pre-rewrite.tar.gz` 與 `../backup/aos-impls-2026-10-21-pre-align.tar.gz`（10-23 都已刪）。
**10-21 晚對齊 bin 版 10-21 傍晚**（ideas 10-21 § 9、計畫 D7）：命令列同 aos-loop（收旗標、設定檔可寫 `檔#/指標`）；`run` 與 `loops` 的值收陣列；
子 loop 改成**經 aos-exec 起**（exec 成 PATH 上的 aos-loop），換掉 10-20 頂層代定的「fork 後在子行程裡直接跑 Loop」；收工時最後一次之後才自己結束的子項也標結束（現行叫 `done`）。

像一個領班：手上一張名單（`loops`，10-23 統合前叫 children），名單上每個人各有一個小隔間（`$AOS_STACK/<名字>/`）。他每隔一會兒（`interval_ms`）看一眼佈告欄（ctl 窗）：
名單改了就把多的請走、少的叫來；誰自己下班了就在白板（state 窗）上記「done、結束碼幾」（被他請走的記「stopped」），**不會再叫他回來**。他自己收工時（不論為什麼）先把每個人都請走、
寫好白板，才走人。

```sh
cat daemon.json
# {"max": 10, "interval_ms": 200, "ctl": "ctl.json", "state": "state.json",
#  "loops": {"bob": {"run": "daemon.json#/loops/bob/body", "max": 1,
#                    "body": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}},
#            "ann": {"run": "daemon.json#/loops/ann/body", "max": 1,
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
| `run` | 字串或 `[目標, 參數...]` | 不跑 | 自己每次的身體（同 aos-loop：每次 `aos-exec -- 目標 參數...`；物件＝`CfgBad`；10-23 統合一度改叫 val，同晚改回 run）；純監工不寫 |
| `max` | 非負整數 | 不限 | 跑幾次就收工（寫 `null` 不行，同 bin 版） |
| `interval_ms` | 非負整數 | 200 | 兩次之間至少隔幾毫秒 |
| `ctl`、`state` | 檔名 | 不開 | 兩扇窗，在 `$AOS_STACK` 底下（同 aos-loop） |
| `loops` | `{名字: 字串、陣列或物件}` | `{}` | 字串或陣列＝aos-exec 的目標（包成 `{"run": 它}`）；物件＝一份 loop.json 的內容（不驗，原樣交給子 loop，寫錯了子 loop 自己退 1）。子項要內嵌單子寫 `{"run": "daemon.json#/loops/<名字>/body", "body": 單子}`。拆成好幾份檔寫 `{"$ref": ["loops-1.json", "loops-2.json"]}`（見下「指示詞與切檔」） |
| `adopt` | 布林 | true | 起來時讀自己上次的 state，把還活著的子 loop 接回、不重起 |

- 要 `$AOS_STACK`（沒設＝`StackMissing`）。名字不能當資料夾名或會被 aos-exec 誤認（空、`.`、`..`、含 `/`、含 `#`、以 `.` 開頭）＝`CfgBad`。
- **名字不能跟自己的 ctl／state 撞名**（使用者 10-22，ideas 10-22 § 6；`taken_names`／`check_names`）：會撞的名字＝ctl、state（含旗標 `--ctl`／`--state` 給的）落在 `$AOS_STACK` 底下時
  相對路徑的第一段（`state.json`、`ctl.json`、`"w/c.json"` 的 `w`；`./x/../s.json` 整理成 `s.json`；在 stack 外面的、沒開的不算）。起來時撞＝`CfgBad`、退 1（10-23 統合前叫 Conflict）；
  ctl 改 `loops` 撞＝那份 ctl 整份不採用、維持上一份好的、原因進 state 的 `ctl_warning`。
- **起子 loop**（經 aos-exec，同 bin 版 10-21 傍晚）：小格 `$AOS_STACK/<名字>/` mkdir（只建這一層；10-23 前是 mkdir -p、會順手建出 `$AOS_STACK`。現在 `$AOS_STACK` 不在＝開了 state 窗就 `WriteFailed`、沒開就 `MkdirFailed`，都退 1——建 stack 只在 aos-exec 做，N-59 第 1 件）；設定補上 `"ctl": "ctl.json"`、`"state": "state.json"`（沒寫才補），
  **一律蓋上 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]`**，相對的 `run`（字串，或陣列的第一個元素）照 daemon 的 cwd 轉成絕對路徑（子 loop 的 cwd 會是小格），
  先寫 `.loop.json` 再改名成 `loop.json`；fork 一個子行程：`setsid` 自成 session、stdin／stdout 接 `/dev/null`、stderr 附加到小格的 `stderr.txt`（10-23 起帶 `.txt`，原 `stderr`）、`AOS_STACK=小格/`、
  解開三個訊號、cd 到 daemon 的 cwd，呼叫 aos-exec 的 `run_cli({"--", "小格/loop.json#/_entry"})`——它 cd 進小格、讀小格的 `.env`（若有）、
  設好 `AOS_CF`＝小格的 loop.json，再 **exec 成 PATH 上的 aos-loop**（pid 不變；指到 `#/_entry` 不受 `$AOS_ENTRY` 影響）。
  所以 **PATH 上要有 aos-loop 和 aos-exec**（`_entry` 的 `aos-loop` 照 PATH 找；子項裡要叫的 aos-exec 也是）；沒有＝子 loop 以 1 結束、原因寫在小格的 `stderr.txt`。
- **每次**（Loop 讀完 ctl 之後）：期望表＝ctl 的 `loops`（有寫）或 daemon.json 的 → 表上多出來的送 SIGTERM（`phase: stopping`）就往下走、**不等**；
  之後每次看一眼：退了標 `stopped`、從表上拿掉（小格留著），滿 10 秒還在就 SIGKILL 整群 → 看誰自己結束了（`phase: done`，記 `code`／`signal`）→
  起表上少掉的（收的途中的同名項還在表上，等它退了下一次才起）→ 跑 `run`（有寫才跑）→ 寫 state（多一欄 `loops`：`{名字: {"pid", "started_at_ticks", "phase", "code", "signal"}}`）。
  `phase`：`running`＝還在跑、`stopping`＝送了 SIGTERM 還沒退、`done`＝子 loop 自己結束、`stopped`＝daemon 收掉它（送了 SIGTERM／SIGKILL）（`done`、`stopped` 10-23 統合前都叫 exited；`started_at_ticks` 統合前叫 started）。
  **10-23 壓測後**（使用者「都修都處理」，[thinking](../../thinking/2026-10-23-daemon-bench.md)）：收子項原本原地等滿 10 秒（那段 state 不寫、ctl 不讀、別的子 loop 沒人顧），改成上面那樣不等；
  表改成「照加入順序的串列＋名字→那一列的雜湊表」，期望表的名字每圈收成雜湊集合、state 的 `loops` 直接接在尾巴（原本逐個比，N 個名字 N×N）；
  沒有 `run` 時一圈只讀一次 ctl、只對一次表、只寫一份 state（`waiting`，不寫 `running`）；起子項之前先寫一份 state、起很久時每秒一份（`Loop::beat`）。
  1 萬個子 loop：一圈 483 → 205 ms、daemon CPU 86 → 6 %，state 第一份 1 秒 → 0.1 秒。
- **子 loop 被 SIGKILL 時**來不及寫最後一份，它小格裡的 `state.json` 停在最後那份（多半 `running`）：daemon 不替它改（N-09 只有它自己寫）。
  看死活照 N-17 用 pid＋`started_at_ticks`；daemon 自己 state 的那一列是準的（`stopped`、`signal` 9、`code` 137）。
- **子 loop 結束後不自動重起**：停在表上 `done`；要再起就從 ctl 的 `loops` 拿掉再放回（或寫進 `loops_removed` 再拿掉），或重起 daemon。
- **ctl** 多認 `loops`、`loops_added`、`loops_removed`（驗法同上，壞＝整份不採用、記 `ctl_warning`）；見下「ctl 只寫變動」。
- **adopt**：讀上次的 state（沒開 state 窗＝沒東西可接），`phase` 是 `running`、pid＋`started_at_ticks`（/proc 第 22 欄）對得上的放回表上、不重起；接回來的不是自己的子行程，之後看 /proc 判斷活不活，結束時 `code` 是 null。

### ctl 只寫變動（10-23 晚，N-54）

使用者「ctl這塊我會想要是"啓動XXX loop/刪除XXX loop"，而不是每次都讓他讀全部」，選「維持宣告式，但可以只寫變動的」：

```json
{"seq": 3, "loops_added": {"carl": "agent-carl"}, "loops_removed": ["bob"]}
```

- `loops_added`＝名單上要多這些（寫法同 `loops`，也能 `{"$ref": [檔, …]}`）；`loops_removed`＝名單上要少這些（名字的陣列）。key 名照 C-54 R4（ctl 用狀態詞，同 `stopped`）。
- **期望表＝（ctl 的 `loops`，沒寫＝daemon.json 的 `loops`）＋`loops_added`－`loops_removed`**，先加後減：同一個名字兩邊都寫＝不要；`loops_removed` 裡名單上沒有的名字不管；
  名單上已有的名字寫進 `loops_added`＝設定換成這份，已在跑的不重起。
- 還是宣告（N-06）：只看這一份 ctl 與 daemon.json，讀幾次都一樣；**ctl 拿掉 `loops_added`＝加進來的收掉**、拿掉 `loops_removed`＝減掉的照 daemon.json 重新起。要一直加著就一直寫著。
- 壞（`loops_removed` 不是字串陣列、`loops_added` 名字不合或撞名、指示詞解不開）＝整份不採用、記 `ctl_warning`。daemon.json 不認這兩個 key。

### 指示詞與切檔（N-28、N-45）

- **daemon.json 與 ctl 的指示詞**（使用者「aos 讀的 JSON 全部支援」）：同 aos-loop 只解自己讀的格——再加 `loops`（本身、每個子項本身）、`adopt`；
  子項是目標＝整個解，是 loop 設定＝只解 `run`、`max`、`interval_ms`、`ctl`、`state` 再寫進小格（搬進小格後相對 `$ref` 會從小格算，所以 daemon 先解），其他 key（`body`…）原樣。
  相對 `$ref` 從寫著它的那份檔所在的資料夾算（daemon.json 的資料夾；ctl＝`$AOS_STACK` 底下 ctl 的資料夾）。解不開：daemon.json＝`DirectiveBad` 退 1；ctl＝不採用。
- **`loops` 拆成好幾份**（使用者「當loop太多的時候，json超大，我會希望他會自動用$ref切，每個檔案一百個」）：用 `$ref` 陣列（aos-directive，N-45）——幾份照順序合成一份物件，同名後面的蓋前面的：

  ```json
  {"interval_ms": 200, "ctl": "ctl.json", "state": "state.json",
   "loops": {"$ref": ["loops-1.json", "loops-2.json"]}}
  ```

  `loops-1.json`＝`{"bob": {"run": "loops-1.json#/bob/body", "body": {...}}, "ann": "agent-ann", ...}`；合不起來（有一份不是物件）＝`DirectiveBad`、合出來不是物件＝`CfgBad`。不拆也能整份 `"loops": {"$ref": "loops.json"}`。
  每個子項裡的相對 `$ref` 從它來自的那份檔的資料夾算。`#/` 指標走原文、不穿過 `$ref`：子項 `run` 要指進拆出去的那份檔（`loops-1.json#/bob/body`，相對路徑照舊從 daemon 的 cwd 算）。
- **state 自動切檔**：`loops` 表超過 100 列（`PART_ROWS`，不開 key）才切，每份最多 100 列、照表的順序；100 列以內維持物件：

  ```json
  {"kind": "state", "phase": "waiting", ..., "loops": {"$ref": ["state_loops/3f9a2c1e07d45b6a.json", "state_loops/<雜湊>.json", ...]}, "pid": ..., "at": ...}
  ```

  分檔資料夾＝state 檔名去副檔名＋`_loops`、跟 state 同一層（也算子項撞名）；檔名＝內容的 FNV-1a 64 雜湊。每份先寫 `.` 開頭暫存再改名，內容沒變的沿用不重寫；
  分檔都寫好才寫主檔（**主檔改名是唯一的提交點**）；寫完清掉這次與上一次主檔都沒用到的分檔（行程第一次寫時不清）；縮回 100 以內、清空後拿掉資料夾。
  讀的人用 aos-directive 解主檔（`aos-directive < state.json`，cwd＝state 的資料夾）就拿回整張 `loops` 物件，一定是同一次寫的表；讀得比兩次寫入還慢時分檔可能已清掉、`$ref` 讀不到，重讀主檔即可。`adopt` 也是這樣解。

### 結束碼

| 怎麼結束 | 結束碼 | stderr |
|---|---|---|
| 跑滿 `max`、ctl `stopped`、身體退 10 | 0 | 不寫 |
| 身體退其他非 0 | 那個碼 | 一行 `aos-daemon: 第 N 次 誰 失敗，結束碼 C`（10-23 統合前寫「第 N 圈」） |
| 收到 SIGINT／SIGTERM／SIGHUP | 128＋N | 不寫 |
| 自己的錯（設定壞、沒 AOS_STACK、子項起不來、state 寫不了） | 1 | 一行 `aos-daemon: 代號 原因` |

不論哪一種，都先收掉所有子 loop（全部送 SIGTERM，等它們退；等的這段每秒寫一份 state、頂層 `phase` 是 `stopping`；滿 10 秒還在的 SIGKILL 整群）、寫好 state 再結束（P-36）：收掉的標 `stopped`；最後一次之後才自己結束的子項標 `done`、記 `code`（計畫 D7）。子項的結束碼不影響 daemon 的。

## 元素

```
 main ──▶ block_signals ──▶ loop_cli ──▶ Daemon(opts, 設定檔)（Loop 的建構子＋AOS_STACK／loops／adopt）──▶ Loop::serve
   每次 Daemon::tend ──▶ term（多的，不等）／settle（收的途中的）──▶ alive（看誰結束）──▶ spawn（少的：寫小格 loop.json、fork ──▶ run_cli({"--", 小格/loop.json#/_entry}) ──▶ exec 成 aos-loop）
   Daemon::info ──▶ loops 表；Daemon::finish ──▶ term（全部）＋settle 等到退（每秒 beat）＋剛死的標 done；Daemon::check_ctl ──▶ ctl 的 loops
```

| 檔 | 做什麼 |
|---|---|
| `src/common/common.hpp` | `using`、代號（全沿用 aos-loop 的） |
| `src/child/child.hpp`、`child.cpp` | 一支子 loop：`spawn`（小格、loop.json（補 ctl／state、蓋 `_entry`、相對 run 轉絕對）、fork＋子行程 `run_child` 呼叫 aos-exec 的 `run_cli`）、`alive`、`row` |
| `src/daemon/daemon.hpp`、`daemon.cpp` | `Daemon`（`aos::loop::Loop` 的子類別）：`read_loops`（`loops` 的指示詞：本身、每個子項各從它來自的檔算）、`write_parts`（state 切檔：`{"$ref": [分檔, …]}`）、ctl 的 `loops_added`／`loops_removed`；建構子、`adopt`、`tend`、`term`／`settle`（收子項不等：送 SIGTERM、之後每次看一眼、滿 10 秒 SIGKILL）、`finish`（收全部、等的時候每秒寫 state，標 stopped、剛死的標 done）、表＝串列＋名字的雜湊表、`info`、`check_ctl`；名字不能帶 `/`、`#`、不能 `.` 開頭（`read_loops`，10-23 晚前叫 `check_loops`）；`taken_names`、`check_names`（跟自己的 ctl／state 撞名，10-22） |
| `src/main.cpp` | 命令列：`block_signals` → `loop_cli` → `Daemon` → `serve`；出錯印「aos-daemon: 代號 原因」 |

## 為什麼這樣做

- **繼承 aos-loop 的 `Loop`**：daemon.json 是 loop.json 的超集，每次讀 ctl、睡 interval、跑身體、寫 state、轉訊號都一樣；daemon 只多 tend／finish／info／check_ctl 四個掛鉤（同 bin 版 `aos_loop.Loop` 的子類別）。
- **子 loop 經 aos-exec 起**（使用者 10-21 傍晚「5.要」，同 bin 版 `aos-exec -- 小格/loop.json#/_entry`）：子 loop 跟別的程式一樣是「一個資料夾程式」——
  小格就是它的資料夾、`loop.json` 的 `_entry` 就是入口，所以小格裡放 `.env` 也有作用。fork 後在子行程裡呼叫 aos-exec 的 `run_cli`（不必在 PATH 上找 aos-exec），
  它最後 exec 成 PATH 上的 aos-loop，所以 `ps` 看到的子 loop 叫 `aos-loop`。原本 10-20 頂層代定的「fork 後在子行程裡直接跑 aos-loop 的 `Loop`、`ps` 上叫 `aos-daemon`」換掉。
  fork 時 daemon 只有一條執行緒，子行程裡 C++ 配置、setenv 安全；三個訊號 daemon 一開始就擋著，子行程 exec 之前解開（遮罩會跨 exec 繼承；同 bin 版 Popen 起的子行程沒擋）。
- **相對的 run 照 daemon 的 cwd 轉絕對**：子 loop 經 aos-exec 起之後 cwd 是小格，不轉的話 `"run": "../agent-bob"` 會從小格算。只轉字串與陣列的第一個元素，其他不動、不驗。

## 跟 Python 版 `proto8/bin/aos-daemon` 的差異

- 錯誤一行多了代號（Python 版 `aos-daemon: 原因`）。
- 起子 loop 不叫 PATH 上的 `aos-exec`，在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`（效果一樣）；之後 exec 成 PATH 上的 aos-loop 這段兩版一樣，PATH 上都要有 aos-loop。
- state 窗寫不了：這版是 `WriteFailed` 一行、先收子 loop、退 1；Python 版是 traceback。
- **10-23 壓測後的修改只做在這一版**（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」）：收子項不等、`stopping` 寫進 state、一圈一份 state、
  起子項前先寫 state、雜湊表、不建 `$AOS_STACK`，bin 版都沒跟。拿 `proto8/tests` 跑這一版（PATH 換成 impls 四支）照樣只差兩個 inst 訊息字面。
- 其他行為一樣：`proto8/tests/test_daemon.py` 15 案拿這支跑，只差 usage 那行的代號（抹掉代號全過；10-21 晚）；demo/daemon 兩條線結果逐檔一樣（`tests/test_demo.py`）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`，20 案、unittest）：10-21 傍晚照 `proto8/tests/test_daemon.py` 重新逐案抄一次 15 案（loop.json 直接丟給 daemon、要 AOS_STACK、loops 壞、小格與窗、
  不自動重起、子項 stderr 在小格、ctl 增減、SIGTERM 收子項 143、旗標蓋過設定、run 陣列與設定檔規則、子 loop 經 aos-exec 起、字串子項是 aos-exec 的目標、
  收工時剛死的子項標 done、收掉的標 stopped、adopt、`adopt: false`），加錯誤代號、子 loop 的 state 心跳是自己的 pid；10-23 再抄 bin 10-22 的 3 案（daemon 重開照名單起停機期間死掉的子項、子項撞名起來時退 1〔另驗 `--state` 旗標也算〕、ctl 撞名不採用）；
  10-23 壓測後加 4 案（共 24 案，約 25 秒）：不肯退的子 loop 不卡住 daemon（收的途中照寫 state、照起別的、那列 `stopping`，收工也等、每秒寫；被 SIGKILL 的那列 `stopped`／signal 9，
  它自己的 state 停在 `running`、pid 已不在）、一圈一份 state（inotify 數改名次數）與 `at` 間隔、起子項之前先有 state（小格放 FIFO 讓起子項卡住）、`$AOS_STACK` 不在不建。
  四案拿修前的碼跑都紅；10-23 晚加 G 段 6 案（共 30 案，約 30 秒）：`loops` 用 `$ref` 陣列拆檔與每層的 `$ref`（兩份同名後蓋前、各份從自己的資料夾算、子項 loop key 先解、body 原樣、`adopt` 也解）、拆檔與指示詞寫壞（舊的物件陣列不收、物件與陣列混著、一份讀不到、合成陣列、解不開＝`DirectiveBad`）、
  ctl 的 `loops_added`／`loops_removed`（加、減、拿掉回 daemon.json、跟 ctl 的 `loops` 一起、兩邊都寫＝不要）、寫壞不採用與 ctl 的相對 `$ref`（`$ref` 陣列、兩份在不同資料夾）、
  state 超過 100 列切檔（`{"$ref": [...]}`、每份 100＋1、檔名是雜湊、aos-directive 解回整張表、只留兩代、分檔資料夾撞名）、切了檔照樣 adopt、縮回 100 以內變回物件並清掉分檔——六案拿改前的碼跑都紅。
  PATH 放 impls 的 aos-exec、aos-loop 兩支的 `bin/`（子 loop 要 exec 成 PATH 上的 aos-loop）。
- `test_demo`（`tests/test_demo.py`）：`proto8/demo/daemon` 在 impls 線（PATH 只放 impls 四支的 `bin/`）與 bin 線各跑一次，比結束碼、stderr、整棵工作區與 stack 的檔與內容。〔10-23 起只跑 impls 線、看結束碼 0、stderr 空、答案寫出來：Python 版刪了（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」），沒有 bin 線可比〕
  要先建好 ../aos-exec、../aos-loop、../aos-fsm 的 `bin/`（`test_cli` 也要前兩支）。
