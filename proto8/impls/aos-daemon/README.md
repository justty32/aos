# aos-daemon

`aos-daemon - 照一張名單，把幾個 aos-loop 各自起在自己的小格裡、看著它們`（NAME，C-54 R1）

**一句話：`aos-daemon [旗標] daemon.json`——一個開了窗的 aos-loop，外加一張子 loop 的表：照表把子 loop（經 aos-exec）起起來、看著、收掉。**
一個 lib（`lib/libaos-daemon.a`，沒有公開標頭）加一支薄命令列（`bin/aos-daemon`）。連 [aos-loop](../aos-loop/README.md) 的公開 API
（骨架 `aos::loop::Loop`；它又帶進 aos-exec、inst、aos-util、aos-directive）與 [aos-post](../aos-post/README.md) 的庫（信箱模式；它再帶進 aos-lock）。全家慣例見 [impls/README.md](../README.md)。

照新做法寫（使用者 10-19 晚「daemon也用新做法重寫吧」、10-20「照預設」，[ideas § 25](../../thinking/2026-10-19-ideas.md)；
計畫 [PLAN-2026-10-19.md](PLAN-2026-10-19.md)；ideas 10-21 § 9、計畫 D7）。行為照 `proto8/bin/aos-daemon`（Python）——計畫跟 bin 版不一樣的地方（例：`ctl`／`state` 是檔名不是布林、
`loops` 的值收字串、沒有「另一個 daemon 還活著」的檢查）一律照 bin 版。
命令列同 aos-loop（收旗標、設定檔可寫 `檔#/指標`）；`exec` 與 `loops` 的值收陣列；子 loop **經 aos-exec 起**（exec 成 PATH 上的 aos-loop）；收工時最後一次之後才自己結束的子項標 `done`。
10-30 起另有 **exec 型子項**（`execs`）：一次性的，daemon 直接 `aos-exec` 它一次、中間不包 aos-loop（見下「exec 型子項 execs」）。

像一個領班：手上一張名單（`loops`），名單上每個人各有一個小隔間（`$AOS_STACK/<名字>/`）。他每隔一會兒（`interval_ms`）看一眼兩塊佈告欄：
一塊管他自己（ctl 窗：暫停、收工、節奏），一塊管名單（loops_ctl 窗）。名單改了就把多的請走、少的叫來；誰自己下班了就在名單白板（loops_state 窗）上記「done、結束碼幾」
（被他請走的記「stopped」），**不會再叫他回來**；他自己的狀況寫在另一塊白板（state 窗）。他自己收工時（不論為什麼）先把每個人都請走、寫好白板，才走人。

```sh
cat daemon.json
# {"max": 10, "interval_ms": 200, "ctl": "ctl.json", "state": "state.json",
#  "loops": {"bob": {"exec": "daemon.json#/loops/bob/body", "max": 1,
#                    "body": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}},
#            "ann": {"exec": "daemon.json#/loops/ann/body", "max": 1,
#                    "body": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "ann"}, "../agent-ann"]}}}}
AOS_STACK=$PWD/.stack/ aos-daemon daemon.json     # 慣例用法是 aos-exec 它（proto8/demo/daemon）；PATH 上要有 aos-exec、aos-loop
```

## 用法

```
aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] daemon.json
```

命令列同 [aos-loop](../aos-loop/README.md)（共用 `loop_cli`）：唯一的位置參數＝設定檔（必給、只能一個；可寫 `檔#/指標`）；旗標放前面；起跑時 旗標 ＞ daemon.json ＞ 預設；
`loops`、`adopt`、`loops_ctl`、`loops_state`、`loops_mailbox` 只在 daemon.json（沒有旗標）。usage 錯一行 `aos-daemon: ArgumentsBad usage: aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] 設定檔.json（原因）`。

daemon.json＝loop.json 的超集（N-28）：

| key | 型別 | 沒寫 | 意思 |
|---|---|---|---|
| `exec` | 字串、`[目標, 參數...]` 或單子物件 | 不跑 | 自己每次的身體（同 aos-loop：每次 `aos-exec -- 目標 參數...`；物件＝單子、行程內 `run_inst`，`AOS_CF`＝daemon.json、`AOS_CO`＝`/exec`；使用者「exec，loop／daemon 的 run 也一起改 exec」）；純監工不寫 |
| `max` | 非負整數 | 不限 | 跑幾次就收工（寫 `null` 不行，同 bin 版） |
| `interval_ms` | 非負整數 | 200 | 兩次之間至少隔幾毫秒 |
| `ctl`、`state` | 檔名 | 不開 | loop 面向的兩扇窗，在 `$AOS_STACK` 底下（同 aos-loop；10-29 起不放名單，見下「兩個手把、兩扇狀態窗」） |
| `loops_ctl`、`loops_state` | 檔名或 `null` | `loops_ctl.json`、`loops_state.json` | 管轄（名單）的手把與狀態窗，在 `$AOS_STACK` 底下（10-29 拆窗）；寫 `null`＝不開 |
| `loops_mailbox` | 路徑或 `null` | 不開 | 信箱模式（10-29）：管轄的增減改成一封封信投進這個信箱（在 `$AOS_STACK` 底下，絕對路徑照寫）；寫了＝`loops_ctl` 不開，`loops_ctl` 也明寫（非 `null`）＝`CfgBad`。見下「信箱模式」 |
| `loops` | `{名字: 字串、陣列或物件}` | `{}` | 字串或陣列＝aos-exec 的目標（包成 `{"exec": 它}`）；物件＝一份 loop.json 的內容（不驗，原樣交給子 loop，寫錯了子 loop 自己退 1）。子項要內嵌單子直接寫 `{"exec": 單子}`（使用者「不過exec本來就應該要可以直接放內嵌單子吧」，[thinking 10-24](../../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）：子 loop 在自己行程內跑，`AOS_CF`＝小格的 `loop.json`、`AOS_CO`＝`/exec`；daemon 寫小格時單子沒寫 `cwd`＝補上 daemon 的 cwd、相對的 `cwd` 接在 daemon 的 cwd 後面（指示詞不動），單子裡相對的 `$ref` 檔名照它來自的檔轉成絕對（`abs_refs`，不解）——相對路徑從 daemon 的 cwd 算；ctl 加的子項同一套。也可寫 `{"exec": "daemon.json#/loops/<名字>/body", "body": 單子}`。拆成好幾份檔寫 `{"$ref": ["loops-1.json", "loops-2.json"]}`（見下「指示詞與切檔」） |
| `execs` | `{名字: 字串、陣列或 {"exec": 目標}}` | `{}` | exec 型子項（10-30，見下「exec 型子項 execs」）：一次性的，daemon 直接 `aos-exec` 它一次、不包 aos-loop；目標＝aos-exec 的目標（字串或 `[目標, 參數...]`），單子物件不收；跟 `loops` 共用名字空間 |
| `adopt` | 布林 | true | 起來時讀自己上次的 loops_state，把還活著的子 loop（與 exec 型子項）接回、不重起 |

- 要 `$AOS_STACK`（沒設＝`StackMissing`）。名字不能當資料夾名或會被 aos-exec 誤認（空、`.`、`..`、含 `/`、含 `#`、以 `.` 開頭）＝`CfgBad`。
- **名字不能跟自己的窗撞名**（使用者 10-22，ideas 10-22 § 6；`taken_names`／`check_names`）：會撞的名字＝ctl、state（含旗標 `--ctl`／`--state` 給的）、loops_ctl、loops_state、
  loops_state 的分檔資料夾、loops_mailbox（信箱模式）落在 `$AOS_STACK` 底下時相對路徑的第一段（`state.json`、`ctl.json`、預設的 `loops_ctl.json`、`loops_state.json`、`loops_state_loops`；`"w/c.json"` 的 `w`；
  `./x/../s.json` 整理成 `s.json`；在 stack 外面的、沒開的不算）。起來時撞＝`CfgBad`、退 1；loops_ctl 改名單撞＝那份 loops_ctl 整份不採用、維持上一份好的、原因進 loops_state 的 `ctl_warning`。
- **起子 loop**（經 aos-exec，同 bin 版）：小格 `$AOS_STACK/<名字>/` mkdir（只建這一層；`$AOS_STACK` 不在＝開了 state 或 loops_state 窗就 `WriteFailed`〔loops_state 沒寫＝開著〕、兩扇都沒開才 `MkdirFailed`，都退 1——建 stack 只在 aos-exec 做，N-59 第 1 件）；設定補上 `"ctl": "ctl.json"`、`"state": "state.json"`（沒寫才補），
  **一律蓋上 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]`**，相對的 `exec`（字串，或陣列的第一個元素）照 daemon 的 cwd 轉成絕對路徑（子 loop 的 cwd 會是小格），
  先寫 `.loop.json` 再改名成 `loop.json`；fork 一個子行程：`setsid` 自成 session、stdin／stdout 接 `/dev/null`、stderr 附加到小格的 `stderr.txt`、`AOS_STACK=小格/`、
  解開三個訊號、cd 到 daemon 的 cwd，呼叫 aos-exec 的 `run_cli({"--", "小格/loop.json#/_entry"})`——它 cd 進小格、讀小格的 `.env`（若有）、
  設好 `AOS_CF`＝小格的 loop.json，再 **exec 成 PATH 上的 aos-loop**（pid 不變；指到 `#/_entry` 不受 `$AOS_ENTRY` 影響）。
  所以 **PATH 上要有 aos-loop 和 aos-exec**（`_entry` 的 `aos-loop` 照 PATH 找；子項裡要叫的 aos-exec 也是）；沒有＝子 loop 以 1 結束、原因寫在小格的 `stderr.txt`。
- **每次**（Loop 讀完 ctl 之後）：讀 loops_ctl → 期望表＝loops_ctl 的 `loops`（有寫）或 daemon.json 的 → 表上多出來的送 SIGTERM（`phase: stopping`）就往下走、**不等**；
  之後每次看一眼：退了標 `stopped`、從表上拿掉（小格留著），滿 10 秒還在就 SIGKILL 整群（子 loop 那群，加上它底下自成一群的——inst 起的單子）→ 看誰自己結束了（`phase: done`，記 `code`／`signal`）→
  起表上少掉的（收的途中的同名項還在表上，等它退了下一次才起）→ 跑 `exec`（有寫才跑）→ 寫 state、接著寫 loops_state（`loops`：`{名字: {"pid", "started_at_ticks", "phase", "code", "signal"}}`）。
  ctl 是 `stopped` 或 `paused` 的那圈不調表（見下）。
  `phase`：`running`＝還在跑、`stopping`＝送了 SIGTERM 還沒退、`done`＝子 loop 自己結束、`stopped`＝daemon 收掉它（送了 SIGTERM／SIGKILL）。
  效能（使用者「都修都處理」，[thinking](../../thinking/2026-10-23-daemon-bench.md)）：收子項不原地等；表＝「照加入順序的串列＋名字→那一列的雜湊表」，期望表的名字每圈收成雜湊集合、state 的 `loops` 直接接在尾巴；
  沒有 `exec` 時一圈只讀一次 ctl、只對一次表、只寫一份 state（`waiting`，不寫 `running`）；起子項之前先寫一份 state、起很久時每秒一份（`Loop::beat`）。
- **子 loop 被 SIGKILL 時**來不及寫最後一份，它小格裡的 `state.json` 停在最後那份（多半 `running`）：daemon 不替它改（N-09 只有它自己寫）。
  看死活照 N-17 用 pid＋`started_at_ticks`；daemon 自己 state 的那一列是準的（`stopped`、`signal` 9、`code` 137）。
- **子 loop 結束後不自動重起**：停在表上 `done`；要再起就從 loops_ctl 的 `loops` 拿掉再放回（或寫進 `loops_removed` 再拿掉），或重起 daemon。
- **loops_ctl** 認 `loops`、`loops_added`、`loops_removed`、`seq`（驗法同上，壞＝整份不採用、記 loops_state 的 `ctl_warning`）；見下「loops_ctl 只寫變動」。
- **adopt**：讀上次的 loops_state（沒開 loops_state 窗＝沒東西可接；10-29 前的 state.json 裡的 `loops` 不讀），`phase` 是 `running`、pid＋`started_at_ticks`（/proc 第 22 欄）對得上的放回表上、不重起；接回來的不是自己的子行程，之後看 /proc 判斷活不活，結束時 `code` 是 null。

### 兩個手把、兩扇狀態窗（10-29 拆窗，[medium-plan § 四](../../thinking/2026-10-29-medium-plan.md)）

| 面向 | 手把（人寫） | 狀態窗（daemon 寫） |
|---|---|---|
| loop 面向與自身 | `ctl.json`：`paused`、`stopped`、`max`、`interval_ms`、`seq`（同 aos-loop） | `state.json`：同 aos-loop（`kind`、`phase`、`counter_runs`、`max`、`interval_ms`、`paused`、`ctl_seq`、`ctl_warning`、心跳四欄、收尾的 `code`），**沒有 `loops`** |
| 管轄（名單） | `loops_ctl.json`：`loops`、`loops_added`、`loops_removed`、`execs_added`、`execs_removed`（10-30）、`seq`（信箱模式＝改成信箱 `loops_mailbox`，見下） | `loops_state.json`：`{"kind": "state", "ctl_seq", "ctl_warning", "letter_warning"（信箱模式才有）, "loops", "execs"（10-30）, "pid", "started_at_ticks", "boot_id", "recorded_at"}` |

- 每圈先讀 `ctl.json`、再讀 `loops_ctl.json`，**各自**採用或不採用（一份壞不影響另一份；壞的原因進各自那扇狀態窗的 `ctl_warning`、`ctl_seq` 回各自的 `seq`）。
- `loops_state.json` 跟 `state.json` 一起寫（`Loop::write_more`，每寫一份 state 就寫一份；沒開 state 也照寫），心跳四欄同一個行程的值——只讀這扇也能判 daemon 死活（N-17）。
- **`stopped`**＝這圈收工（收子項照 P-36），不再看名單。**`paused`**＝整圈暫停：不跑 `exec`、**也不調表**（不收多的、不起少的；`loops_ctl` 的變動等解除暫停那圈才生效），
  但照讀兩份 ctl（`ctl_seq` 照回）、照寫兩扇 state、照收已送 SIGTERM 的、照記自己結束的（`done`）。10-29 前暫停時照樣對表。
- **過渡期**（衝突 5，使用者 10-29「都照建議」）：`ctl.json` 寫了 `loops`／`loops_added`／`loops_removed`＝那幾個 key 不採用（其他照採），`state.json` 的 `ctl_warning`
  寫一句「已搬到 loops_ctl.json」；之後會拿掉這句、回到不認得的 key 一律忽略。

### exec 型子項 execs（10-30，[thinking 10-30 agent-lifecycle](../../thinking/2026-10-30-agent-lifecycle.md) B-12 ②、實作第 7 步）

使用者 10-30「包成max:1也是可以」「不過可以的話，我也覺得讓daemon可以掛aos-exec，也是不錯的」：一次性的東西（射後不理的 agent、`claude -p` 的腳本）可以照舊寫成
`"loops": {"名字": {"exec": 目標, "max": 1}}`（①，多一層 aos-loop），也可以寫成 exec 型子項（②）。條文是草稿（N-28／N-54 的 10-30 補，NORMS 正文還沒落）。兩種並排的例子：[demo/daemon-3](../../demo/daemon-3/README.md)。

```json
{"execs": {"bob": "/path/agent-bob", "carl": ["../job", "a", "b"], "dan": {"exec": "daemon.json#/jobs/dan"}}}
```

- **寫法**：形狀同 `loops`——`{名字: 目標}` 或 `{名字: {"exec": 目標}}`（物件只看 `exec`，其他 key 忽略）；目標＝aos-exec 的目標（字串或 `[目標, 參數...]`，非空字串陣列），**單子物件不收**（`CfgBad`；要跑單子就寫 `"daemon.json#/…"` 指進去）。名字規則、指示詞（`$ref` 拆檔、每層的起點）同 `loops`（`read_execs` 先走 `read_loops`）。
- **怎麼起**（`spawn_exec`）：小格 `$AOS_STACK/<名字>/`（只建一層）、`AOS_STACK`＝小格/、stdin／stdout 接 `/dev/null`、stderr 附加到小格的 `stderr.txt`、`setsid` 自成群組、cd 到 daemon 的 cwd——跟起子 loop 一樣，**只是不包 aos-loop、不寫 `loop.json`、不補 `ctl`／`state`**：子行程直接 `run_cli({"--", 目標, 參數...})`（aos-exec），所以表上的 pid 就是那支程式；相對路徑從 daemon 的 cwd 算（不轉絕對，子行程本來就在那裡叫）。
- **退了**＝`phase: done`、記 `code`／`signal`，**不重起**；列留在 `execs` 表上，直到名單拿掉（跟 loop 型同一條規則，方向題 2）。要再跑一次＝從名單拿掉再放回。
- **收**：同子 loop——名單少了它或 daemon 收工＝SIGTERM（直接給那支程式，少一跳）、`stopping`，滿 10 秒還在就 SIGKILL 整群（連底下自成一群的）；收掉的標 `stopped`。
- **名字空間**：`execs` 與 `loops` 共用（小格同一個資料夾）。daemon.json 兩邊同名＝`CfgBad` 退 1；loops_ctl 合出來同名＝整份不採用（`ctl_warning`）；信箱模式的信套完同名＝壞信（`letter_warning`）。撞自己的窗同 `loops`。
- **換種類**：表上的種類跟期望表的不一樣（例：loops_ctl 寫 `{"loops_removed": ["bob"], "execs_added": {"bob": "agent-bob"}}`）＝當成不在期望表上：舊的收掉（`stopped`、拿掉），下一次起新的（同「收的途中同名放回來」那條）。
- **狀態**：`loops_state.json` 多一張 `execs` 表（沒有就是 `{}`），列的形狀同 `loops`（`pid`、`started_at_ticks`、`phase`、`code`、`signal`）；超過 100 列一樣切檔，分檔跟 `loops` 放同一個 `loops_state_loops/`（檔名是內容的雜湊，不會撞）。`adopt` 兩張表都接（10-30 前的 loops_state 沒有 `execs`＝沒東西接）。
- **手把**：`loops_ctl.json` 與信箱模式的信多認 `execs_added`／`execs_removed`（語意同 `loops_added`／`loops_removed`；loops_ctl 沒有整份的 `execs`，`execs` 那半的底永遠是 daemon.json 的 `execs`）。
- **命令列**：要從外面掛上去、拿下來，可以用 [aos-daemon-ctl](../../bin/README.md)（`add XXX`＝投一封 `loops_added`／`execs_added` 的信進信箱模式的 `loops_mailbox/`，有 `loop.json`＝loop 子項、沒有＝`execs`；`rm`、`ls`；哪個 daemon＝`--daemon` ＞ `$AOS_DAEMON`）。

### loops_ctl 只寫變動（N-54）

使用者「ctl這塊我會想要是"啓動XXX loop/刪除XXX loop"，而不是每次都讓他讀全部」，選「維持宣告式，但可以只寫變動的」：

```json
{"seq": 3, "loops_added": {"carl": "agent-carl"}, "loops_removed": ["bob"]}
```

- `loops_added`＝名單上要多這些（寫法同 `loops`，也能 `{"$ref": [檔, …]}`）；`loops_removed`＝名單上要少這些（名字的陣列）。key 名照 C-54 R4（ctl 用狀態詞，同 `stopped`）。
- **期望表＝（loops_ctl 的 `loops`，沒寫＝daemon.json 的 `loops`）＋`loops_added`－`loops_removed`**，先加後減：同一個名字兩邊都寫＝不要；`loops_removed` 裡名單上沒有的名字不管；
  名單上已有的名字寫進 `loops_added`＝設定換成這份，已在跑的不重起。
- 還是宣告（N-06）：只看這一份 loops_ctl 與 daemon.json，讀幾次都一樣；**loops_ctl 拿掉 `loops_added`＝加進來的收掉**、拿掉 `loops_removed`＝減掉的照 daemon.json 重新起。要一直加著就一直寫著。
- 壞（不是 JSON 物件、`seq` 不是非負整數、`loops_removed` 不是字串陣列、`loops_added` 名字不合或撞名、指示詞解不開）＝整份不採用、記 loops_state 的 `ctl_warning`。daemon.json 不認這兩個 key。
- **10-30 多認 `execs_added`／`execs_removed`**（exec 型子項，語意同 `loops_added`／`loops_removed`；見下「exec 型子項 execs」）：`execs` 那半的期望表＝daemon.json 的 `execs`＋`execs_added`－`execs_removed`（loops_ctl **沒有整份的 `execs`**）。合出來 `loops` 與 `execs` 同名＝整份不採用（`ctl_warning`「同時在 loops 與 execs」）。

### 信箱模式（10-29，[medium-plan § 四 3](../../thinking/2026-10-29-medium-plan.md)、NORMS N-28 的 10-29 補、N-16）

多個人要改名單時，不必搶寫同一份 `loops_ctl.json`：daemon.json 寫 `"loops_mailbox": "loops_mailbox"`，大家各自投一封信（[aos-post](../aos-post/README.md) 的 `send`），daemon 每圈收。

```sh
echo '{"loops_added": {"bob": "../agent-bob"}}' | aos-post send "$AOS_STACK/loops_mailbox"   # 加 bob
echo '{"loops_removed": ["bob"]}' | aos-post send --reply-to 我的信箱 "$AOS_STACK/loops_mailbox"   # 刪 bob，套用完回一封 {"applied": true}
```

- **起來時**：`aos::post::init` 建好 `tmp/`、`new/`、`cur/`（已在就沿用；`$AOS_STACK` 不在＝`MkdirFailed`、不替人建）；`loops_ctl` 不開（不讀 `loops_ctl.json`，那個名字也不擋撞名）。
- **期望表**＝daemon.json 的 `loops`＋重起時 adopt 接回、不在 daemon.json 裡的子項＋依序套用的每封信。期望表只在記憶體裡（重起時從 daemon.json＋adopt 重建）；
  **接回的子項留在名單上，直到有信把它 `loops_removed`**（方向題 1）——它的設定 daemon 不知道（只留名），所以它自己結束了也只會停在 `done`。
- **每圈**（`stopped`／`paused` 那圈不認領，信留在 `new/`，解除暫停那圈才套）：`new/` 全部認領（照名字排序）→ 逐封驗、好的依序套進期望表（後面的蓋前面的）→ **全部套完才對一次表** →
  有 `reply_to` 的好信回一封 `body: {"applied": true}`（`in_reply_to`＝原信號）→ 信收掉（rename 回 `tmp/` 再刪，不留 `done/`）。
  起來時 `cur/` 不空（上次認領了、沒收完就死）＝當成第一個認領的圈的信，排在 `new/` 的前面重做（信是宣告式的增減，重做無害）。
- **信的 `body`**：物件，只認 `loops_added`（寫法同 `loops`）、`loops_removed`（名字的陣列）、`execs_added`、`execs_removed`（10-30，同 loops_ctl；先在副本上套，`loops` 與 `execs` 同名＝壞信、不套），其他 key 忽略；同一封先加後減（同 loops_ctl）。沒有整份的 `loops`（信是增減，整份宣告留給 ctl 模式）。
  相對的 `exec` 與相對的 `$ref` 都從 daemon 的 cwd 算（信收完就刪了，不能從信的資料夾算）。
- **壞信**＝信封壞（`aos::post::check`：`letter.json` 讀不了、`kind` 不是 `"letter"`、缺 `sender`／`sent_at`／`body`…）、`body` 不是物件、那兩個 key 型別錯、`loops_added` 的子項不合格（同 loops_ctl 的檢查，含撞名）、指示詞解不開：
  **丟掉、不套、不回信**（決定 27 不通知寄信人），原因寫進 `loops_state.json` 的 `letter_warning`（`"信 <信號> 不採用：原因"`，最後一封壞信的；之後的圈沒有壞信就維持原值）；不影響同一圈的好信。
- 回信寄不出去（`reply_to` 不是信箱）、收信失敗都不管，照樣往下走。要知道「加進去了沒」的標準做法是讀 `loops_state.json`。
- 誰能寄：純靠 Linux 檔案權限（`new/`、`tmp/` 開給誰寫，誰就能寄；N-54 末）。`loops_state.json` 在信箱模式照寫（`ctl_seq`、`ctl_warning` 是 `null`）。

### 指示詞與切檔（N-28、N-45）

- **daemon.json、ctl 與 loops_ctl 的指示詞**（使用者「aos 讀的 JSON 全部支援」）：同 aos-loop 只解自己讀的格——再加 `loops`（本身、每個子項本身）、`adopt`、`loops_ctl`、`loops_state`；
  子項是目標＝整個解，是 loop 設定＝只解 `exec`、`max`、`interval_ms`、`ctl`、`state` 再寫進小格（搬進小格後相對 `$ref` 會從小格算，所以 daemon 先解），其他 key（`body`…）原樣。
  相對 `$ref` 從寫著它的那份檔所在的資料夾算（daemon.json 的資料夾；ctl、loops_ctl＝`$AOS_STACK` 底下那份的資料夾）。解不開：daemon.json＝`DirectiveBad` 退 1；ctl、loops_ctl＝不採用。
- **`loops` 拆成好幾份**（使用者「當loop太多的時候，json超大，我會希望他會自動用$ref切，每個檔案一百個」）：用 `$ref` 陣列（aos-directive，N-45）——幾份照順序合成一份物件，同名後面的蓋前面的：

  ```json
  {"interval_ms": 200, "ctl": "ctl.json", "state": "state.json",
   "loops": {"$ref": ["loops-1.json", "loops-2.json"]}}
  ```

  `loops-1.json`＝`{"bob": {"exec": "loops-1.json#/bob/body", "body": {...}}, "ann": "agent-ann", ...}`；合不起來（有一份不是物件）＝`DirectiveBad`、合出來不是物件＝`CfgBad`。不拆也能整份 `"loops": {"$ref": "loops.json"}`。
  每個子項裡的相對 `$ref` 從它來自的那份檔的資料夾算。`#/` 指標走原文、不穿過 `$ref`：子項 `exec` 要指進拆出去的那份檔（`loops-1.json#/bob/body`，相對路徑照舊從 daemon 的 cwd 算）。
- **loops_state 自動切檔**：`loops` 表超過 100 列（`PART_ROWS`，不開 key）才切，每份最多 100 列、照表的順序；100 列以內維持物件：

  ```json
  {"kind": "state", "ctl_seq": null, "ctl_warning": null, "loops": {"$ref": ["loops_state_loops/3f9a2c1e07d45b6a.json", "loops_state_loops/<雜湊>.json", ...]}, "pid": ..., "recorded_at": ...}
  ```

  分檔資料夾＝loops_state 檔名去副檔名＋`_loops`、跟它同一層（預設 `loops_state_loops/`；也算子項撞名；10-29 前跟著 state 叫 `state_loops/`）；檔名＝內容的 FNV-1a 64 雜湊。每份先寫 `.` 開頭暫存再改名，內容沒變的沿用不重寫；
  分檔都寫好才寫主檔（**主檔改名是唯一的提交點**）；寫完清掉這次與上一次主檔都沒用到的分檔（行程第一次寫時不清）；縮回 100 以內、清空後拿掉資料夾。
  讀的人用 aos-directive 解主檔（`aos-directive < loops_state.json`，cwd＝它的資料夾）就拿回整張 `loops` 物件，一定是同一次寫的表；讀得比兩次寫入還慢時分檔可能已清掉、`$ref` 讀不到，重讀主檔即可。`adopt` 也是這樣解。

### 結束碼

| 怎麼結束 | 結束碼 | stderr |
|---|---|---|
| 跑滿 `max`、ctl `stopped`、身體退 10 | 0 | 不寫 |
| 身體退其他非 0 | 那個碼 | 一行 `aos-daemon: 第 N 次 誰 失敗，結束碼 C` |
| 收到 SIGINT／SIGTERM／SIGHUP | 128＋N | 不寫 |
| 自己的錯（設定壞、沒 AOS_STACK、子項起不來、state／loops_state 寫不了、信箱模式的信箱建不了） | 1 | 一行 `aos-daemon: 代號 原因` |

不論哪一種，都先收掉所有子 loop（全部送 SIGTERM，等它們退；等的這段每秒寫一份 state、頂層 `phase` 是 `stopping`；滿 10 秒還在的 SIGKILL 整群，連底下自成一群的單子）、寫好 state 再結束（P-36）：收掉的標 `stopped`；最後一次之後才自己結束的子項標 `done`、記 `code`（計畫 D7）。子項的結束碼不影響 daemon 的。

## 元素

```
 main ──▶ block_signals ──▶ loop_cli ──▶ Daemon(opts, 設定檔)（Loop 的建構子＋AOS_STACK／loops／adopt／loops_ctl／loops_state）──▶ Loop::serve
   每次 Daemon::tend ──▶ read_loops_ctl ──▶（ctl stopped／paused＝只看一眼）term（多的，不等）／settle（收的途中的）──▶ alive（看誰結束）──▶ spawn（少的：寫小格 loop.json、fork ──▶ run_cli({"--", 小格/loop.json#/_entry}) ──▶ exec 成 aos-loop）
                                                                                                    ／spawn_exec（少的 exec 型：fork ──▶ run_cli({"--", 目標, 參數...})，10-30）
   信箱模式的 tend ──▶ take_letters（claim_all、check、apply_letter）──▶ 對表 ──▶ done_letters（reply、finish）
   Daemon::write_more ──▶ loops_state（loops 表＋write_parts）；Daemon::finish ──▶ term（全部）＋settle 等到退（每秒 beat）＋剛死的標 done；Daemon::check_ctl ──▶ ctl.json 的 loops* 不採用、過渡期提醒
```

| 檔 | 做什麼 |
|---|---|
| `src/common/common.hpp` | `using`、代號（全沿用 aos-loop 的） |
| `src/child/child.hpp`、`child.cpp` | 10-30 起 `spawn_exec`（exec 型子項：小格、`launch` 同下，不寫 loop.json、`run_cli({"--", 目標, 參數...})`；`Child::once`）。一支子 loop：`spawn`（小格、loop.json（補 ctl／state、蓋 `_entry`、相對 exec 轉絕對；exec 是單子＝補／接 `cwd`）、fork＋子行程 `run_child` 呼叫 aos-exec 的 `run_cli`）、`alive`、`row` |
| `src/daemon/daemon.hpp`、`daemon.cpp` | 10-30：`read_execs`（`execs` 每項收成目標）、`merge_want`（期望表的一半，loops、execs 共用）、`check_apart`（兩邊同名）、`reconcile` 收兩份期望表、`adopt` 接兩張表。`Daemon`（`aos::loop::Loop` 的子類別）：`read_loops`（`loops` 的指示詞：本身、每個子項各從它來自的檔算；子項 `exec` 是單子＝只換一層、`abs_refs` 把相對 `$ref` 轉絕對）；建構子（含 `loops_ctl`／`loops_state` 的路徑）、`adopt`（讀 loops_state）、`tend`（期望表＝loops_ctl＋增減；ctl stopped／paused 不調表）、`term`／`settle`（收子項不等：送 SIGTERM、之後每次看一眼、滿 10 秒 SIGKILL，連 `leaders_below` 掃到的、子 loop 底下自成一群的單子）、`finish`（收全部、等的時候每秒寫 state，標 stopped、剛死的標 done）、表＝串列＋名字的雜湊表、`check_ctl`（ctl.json 的 `loops*` 不採用、過渡期進 `ctl_warning`）；名字不能帶 `/`、`#`、不能 `.` 開頭（`read_loops`）；`taken_names`、`check_names`（跟自己的窗撞名） |
| `src/daemon/windows.cpp` | 管轄那一對窗（10-29）：`read_loops_ctl`（每圈讀 loops_ctl.json，同 read_ctl 的不採用規則）、`check_lists`（`loops`／`loops_added`／`loops_removed`）、`write_more`（loops_state.json：`kind`、`ctl_seq`、`ctl_warning`、`letter_warning`、`loops`、心跳）、`write_parts`（切檔：`{"$ref": [分檔, …]}`） |
| `src/daemon/mailbox.cpp` | 信箱模式（10-29）：`open_mailbox`（建四格、期望表＝daemon.json＋接回的、記下 `cur/` 的殘骸）、`take_letters`（認領、`check` 驗信封、逐封套進期望表、壞信記 `letter_warning`）、`apply_letter`（驗 body：`check_lists`）、`done_letters`（回 `applied`、收信）；連 aos-post 的庫 |
| `src/main.cpp` | 命令列：`block_signals` → `loop_cli` → `Daemon` → `serve`；出錯印「aos-daemon: 代號 原因」 |

## 實作注意

- **繼承 aos-loop 的 `Loop`**：daemon.json 是 loop.json 的超集，每次讀 ctl、睡 interval、跑身體、寫 state、轉訊號都一樣；daemon 用 tend／finish／check_ctl／write_more 四個掛鉤（同 bin 版 `aos_loop.Loop` 的子類別；10-29 拆窗起不用 info、多 write_more 寫 loops_state）。
- **子 loop 經 aos-exec 起**（使用者 10-21 傍晚「5.要」，同 bin 版 `aos-exec -- 小格/loop.json#/_entry`）：子 loop 跟別的程式一樣是「一個資料夾程式」——
  小格就是它的資料夾、`loop.json` 的 `_entry` 就是入口，所以小格裡放 `.env` 也有作用。fork 後在子行程裡呼叫 aos-exec 的 `run_cli`（不必在 PATH 上找 aos-exec），
  它最後 exec 成 PATH 上的 aos-loop，所以 `ps` 看到的子 loop 叫 `aos-loop`。
  fork 時 daemon 只有一條執行緒，子行程裡 C++ 配置、setenv 安全；三個訊號 daemon 一開始就擋著，子行程 exec 之前解開（遮罩會跨 exec 繼承；同 bin 版 Popen 起的子行程沒擋）。
- **相對的 exec 照 daemon 的 cwd 轉絕對**：子 loop 經 aos-exec 起之後 cwd 是小格，不轉的話 `"exec": "../agent-bob"` 會從小格算。只轉字串與陣列的第一個元素，其他不動、不驗。

## 跟 Python 版 `proto8/bin/aos-daemon` 的差異

- 錯誤一行多了代號（Python 版 `aos-daemon: 原因`）。
- 起子 loop 不叫 PATH 上的 `aos-exec`，在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`（效果一樣）；之後 exec 成 PATH 上的 aos-loop 這段兩版一樣，PATH 上都要有 aos-loop。
- state 窗寫不了：C++ 版是 `WriteFailed` 一行、先收子 loop、退 1；Python 版是 traceback。
- **只有 C++ 版有的**（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」）：收子項不等、`stopping` 寫進 state、一圈一份 state、
  起子項前先寫 state、雜湊表、不建 `$AOS_STACK`。拿 `proto8/tests` 跑 C++ 版（PATH 換成 impls 四支）只差兩個 inst 訊息字面。
- 其他行為一樣：`proto8/tests/test_daemon.py` 15 案拿這支跑，只差 usage 那行的代號（抹掉代號全過）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`，58 案、unittest，約 80 秒）：
  照 `proto8/tests/test_daemon.py` 逐案抄的 15 案（loop.json 直接丟給 daemon、要 AOS_STACK、loops 壞、小格與窗、
  不自動重起、子項 stderr 在小格、ctl 增減、SIGTERM 收子項 143、旗標蓋過設定、exec 陣列與設定檔規則、子 loop 經 aos-exec 起、字串子項是 aos-exec 的目標、
  收工時剛死的子項標 done、收掉的標 stopped、adopt、`adopt: false`），加錯誤代號、子 loop 的 state 心跳是自己的 pid；抄 bin 10-22 的 3 案（daemon 重開照名單起停機期間死掉的子項、子項撞名起來時退 1〔另驗 `--state` 旗標也算〕、ctl 撞名不採用）；
  效能 4 案：不肯退的子 loop 不卡住 daemon（收的途中照寫 state、照起別的、那列 `stopping`，收工也等、每秒寫；被 SIGKILL 的那列 `stopped`／signal 9，
  它自己的 state 停在 `running`、pid 已不在）、一圈一份 state（inotify 數改名次數）與 `recorded_at` 間隔、起子項之前先有 state（小格放 FIFO 讓起子項卡住）、`$AOS_STACK` 不在不建；
  G 段 6 案：`loops` 用 `$ref` 陣列拆檔與每層的 `$ref`（兩份同名後蓋前、各份從自己的資料夾算、子項 loop key 先解、body 原樣、`adopt` 也解）、拆檔與指示詞寫壞（物件陣列不收、物件與陣列混著、一份讀不到、合成陣列、解不開＝`DirectiveBad`）、
  ctl 的 `loops_added`／`loops_removed`（加、減、拿掉回 daemon.json、跟 ctl 的 `loops` 一起、兩邊都寫＝不要）、寫壞不採用與 ctl 的相對 `$ref`（`$ref` 陣列、兩份在不同資料夾）、
  state 超過 100 列切檔（`{"$ref": [...]}`、每份 100＋1、檔名是雜湊、aos-directive 解回整張表、只留兩代、分檔資料夾撞名）、切了檔照樣 adopt、縮回 100 以內變回物件並清掉分檔；
  exec 直接放單子 4 案：daemon 自己的 exec（`AOS_CF`＝daemon.json、`/exec`、cwd）、非 0／逾時 143／形狀壞 `EntryBad`、子項的單子（`AOS_CF`＝小格、cwd 補成 daemon 的 cwd、相對 `cwd` 接上、相對 `$ref` 轉絕對）、ctl 半路加的子項是單子；
  5 案：子項跑內嵌單子後 `AOS_CF`／`AOS_CD`／`AOS_CO` 還原成原本的值（loops_ctl 的 loops 用 `$env` 讀）、daemon 收 SIGTERM 時子 loop 轉給單子、daemon 自己的單子跑一半收 SIGTERM、`abs_refs` 邊界（絕對、`$ref` 陣列、只有 `#/`、寫法不合、往裡走）、不理 SIGTERM 的單子隨子 loop 一起被 SIGKILL；
  H 段 6 案（10-29 拆窗）：`ctl.json` 寫 `loops_added` 不採用、`ctl_warning` 提醒搬家、寫進 `loops_ctl.json` 才起；同一圈 `ctl.json` 改 `interval_ms`、`loops_ctl.json` 加子項兩邊都生效（各回各的 `seq`）；
  `ctl.json` 壞、`loops_ctl.json` 好＝只有 `state.json` 有 `ctl_warning`；`paused` 時 `loops_ctl` 的變動不生效（照讀、照寫）、解除後生效；`loops_state`／`loops_ctl` 寫 `null` 不開與型別壞；撞名多兩扇窗與分檔資料夾。
  I 段 6 案（10-29 信箱模式）：兩封信同一圈（一加一刪）照名字順序後面的贏、`paused` 時信留在 `new/`、解除後才套；重起後接回的子項留著、有信 `loops_removed` 才收；壞信（body 不是物件、撞名、型別錯、`letter.json` 壞）不影響同一圈的好信、`letter_warning` 記最後一封、只有好信的圈維持、壞信不回；`reply_to` 收到 `{"applied": true}`；`loops_ctl`＋`loops_mailbox`＝`CfgBad`、型別錯、撞名、`` 不在不建；`cur/` 的殘骸排在 `new/` 前面重做。
  J 段 7 案（10-30 exec 型子項 `execs`）：三種寫法各跑一次、退 3＝`done`／`code` 3、不重起、小格只有 `stderr.txt` 與程式自己的檔、`AOS_STACK`＝小格/、stdin 空、pgrp＝pid＝表上的 pid；`execs_removed` 的 SIGTERM 直接打那支程式（cmdline 不是 aos-loop）、不理的 10 秒後連它的 sleep 整群 SIGKILL；daemon.json 的同名／撞窗／寫法不合＝`CfgBad`，loops_ctl 合出來同名不採用、`loops_removed`＋`execs_added` 同名＝收掉舊 loop 起 exec 型；adopt 兩張表；`{"exec": X, "max": 1}` 的 loop 型照舊（小格有 loop.json、stderr 有 aos-loop 那行）；信箱的 `execs_added`／`execs_removed` 與同名壞信；`execs` 超過 100 列切檔。
  前面各段讀名單、改名單的地方 10-29 起改讀 `loops_state.json`、改寫 `loops_ctl.json`。
  PATH 放 impls 的 aos-exec、aos-loop 兩支的 `bin/`（子 loop 要 exec 成 PATH 上的 aos-loop）。
- `test_demo`（`tests/test_demo.py`）：`proto8/demo/daemon`、`daemon-2`（信箱模式，10-29）、`daemon-3`（同一支 tick 用 `max: 1` 的 loop 與 `execs` 各掛一次、看兩張表，10-30）在 impls 線（PATH 只放 impls 四支的 `bin/`）跑，看結束碼 0、stderr 空、答案寫出來（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，沒有 bin 線可比）。
  要先建好 ../aos-exec、../aos-loop、../aos-fsm 的 `bin/`（`test_cli` 也要前兩支）。
