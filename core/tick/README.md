# core/tick — 心跳判定與定期事務登記（子命令 `tick`、`heartbeat`、`routine`、`schedule`）

← [core/README](../README.md)｜協定 [PROTOCOL](../../wf/workflows/dispatch/proto/PROTOCOL.md) §1、§2、§6｜慣例 [conventions](../../wf/workflows/common/conventions.md)｜工作流原型 [routines](../../wf/workflows/routines.md)、[schedule](../../wf/workflows/schedule.md)、[tick](../../wf/workflows/tick.md)

## 這個小專案做什麼

讓「該定期做的事」在 aos 上真的會到期自動投遞執行。引擎就是 `aos run`：`aos heartbeat init` 在
`.aos/every/tick.json` 放一條 `aos tick`，於是每回合 `aos tick` 都被叫起一次；`aos tick` 做**純機械判定**——
讀 `.aos/heartbeat/` 底下的 `routines.json`（固定循環）與 `schedule.json`（一次性）、把到期的投進 `inbox/`
（argv 型）或交給 agent（ask 型）、更新表、在 `log.md` 追加一行。**`aos tick` 自己絕不呼叫 LLM。**
相依 `aos::loop`（版面、`deliver`、`current_folder`、`read_turn`）與 `aos::agent`（只呼叫 `say()`，不改它）。

所有判定函式都收一個 `Instant now`（UTC epoch 秒）；函式庫裡沒有任何地方讀真實時鐘，只有 CLI 層才
`system_clock::now()`。測試因此不 sleep、不靠牆上時鐘。

## 資料：`<folder>/.aos/heartbeat/`

| 檔 | 內容 |
|---|---|
| `routines.json` | `wf-table/1`，columns＝`["id","kind","every","slot","last_run","run","note"]` |
| `schedule.json` | `wf-table/1`，columns＝`["id","at","run","note"]` |
| `log.md` | append-only，一次**有事的**心跳一行（見「log.md 一行」） |
| `config.json` | 可選：`{"tz":"Asia/Taipei","missed_after":"6h"}`。缺檔＝全預設；缺欄＝該欄預設 |

`wf-table/1` 表頭：`contract` 固定 `"wf-table/1"`；`source` **固定填 `""`**——那欄的意思是「抽出自哪份 md」，
這兩張表沒有來源 md、JSON 本身就是正本，跨 repo 指向 `wf/workflows/routines.md` 只會是一條壞掉的相對路徑；
`extracted`＝最後一次改寫時 `now` 在 `tz` 的日期 `YYYY-MM-DD`；`link_columns`＝`[]`。
讀表時缺欄視為空字串、未知欄位忽略；改寫時整檔原子換掉（`.tmp`＋`rename`），未知欄位**不保留**。

### routines 一列

| 欄 | 值 |
|---|---|
| `id` | `^[A-Za-z0-9_.-]{1,64}$`（會進檔名 `hb-<id>-<turn>.json`）。表內唯一；重複 id 讀表就失敗 |
| `kind` | `interval` 或 `slot` |
| `every` | interval 用。`Nd`／`Nh`／`Nm`／`Ns`，N 為正整數、單一單位（`90m` 可，`1h30m` 不可） |
| `slot` | slot 用。`HH:MM` 或 `HH:MM <遮罩>`：遮罩恰 7 字元，位置＝週一…週日，`1`＝該天要、`.`＝不要。省略遮罩＝每天。例：`09:30 11111..`＝平日 09:30 起 |
| `last_run` | `YYYY-MM-DDTHH:MM:SS+08:00`（`format_timestamp`，固定用 `tz` 的位移）；空＝從未執行 |
| `run` | `{"argv":["…"]}` 或 `{"ask":"一句給 agent 的話"}`（巢狀物件）。兩者都給以 argv 為準；都空＝無效列 |
| `note` | 自由文字 |

### schedule 一列

| 欄 | 值 |
|---|---|
| `id` | 同上 |
| `at` | `YYYY-MM-DD HH:MM`，以 `tz` 解讀（不含秒、不含位移） |
| `run`、`note` | 同上 |

## 到期規則（`due.cpp`，純函式）

- **interval**：`last_run` 空 → 到期；否則 `now − last_run ≥ every` → 到期（取 `≥`，`--every 2s` 配 2 秒心跳才能每次都中）。
- **slot**（一列表達一個「時機分區」）：令 `L = to_local(now, tz)`。三件同時成立才到期：
  ① 遮罩允許 `L.weekday`；② `(L.hour, L.minute) ≥ (HH, MM)`；③ `last_run` 空，或 `to_local(last_run, tz)` 的**日期早於** `L` 的日期。
  ③ 就是「一天只觸發一次」的保證：觸發後 `last_run`＝`now`，當天之後的每一次心跳都被 ③ 擋掉，換日後才重新開放。
  沒有「結束時刻」：機器 23:50 才醒，09:30 的 slot 照樣觸發一次（同一天內晚到就晚做；`missed_after` 只管 schedule）。
- **schedule**：`at > now` → `pending`；`now − at ≤ missed_after` → `due`；否則 → `missed`。
- 列無效（`kind`／`every`／`slot`／`at`／`run` 壞掉）：`routine_due` 回 false 並填 `error`，`schedule_state` 回 `pending` 並填 `error`；tick 對這種列記一個 `error` 事件、**不刪不改**，其他列照做。
- `routine_next`（給 `ls`）：已到期 → `nullopt`（印「到期」）；interval → `last_run + every`；slot → 大於 `now`、落在允許日 `HH:MM`、且日期晚於 `last_run` 日期的最早時刻。

## `aos tick` 一次心跳（`run_tick`）

1. `read_config`；`tz` 不合法（`valid_zone` 為 false）→ 回 false，退出碼 1，不寫 log。
2. `read_routines`、`read_schedule`（檔不存在＝空表，不算錯）。`turn`＝`TickOptions::turn`。
3. 依表序處理 routines：`routine_due` 為 true 的列——
   - argv 型：`loop::deliver()` 一條 `wire::Inst{id="hb-<id>-<turn>", argv=run.argv}`（其餘欄位空）→ 事件 `run=<id>→hb-<id>-<turn>`；deliver 失敗 → `error=<id>→<原因>`，且**不更新 `last_run`**。
   - ask 型：`single_agent()` 有值 → `agent::say(folder, name, run.ask)` → `ask=<id>→<name>`；沒有 → `ask=<id>→none`（不呼叫 say）。**兩種都算「已投出」**。
   - 投出後（含 `→none`）`last_run`＝`format_timestamp(now, tz)`。
4. 依表序處理 schedule：
   - `due` → 同上投遞或 say；成功後**刪列**（deliver 失敗 → `error` 事件、留列，下次再試）。
   - `missed` → 不執行原 `run`；有 agent 就 `say()` 一段固定文字（見下）→ `missed=<id>→<name>`，沒有 → `missed=<id>→none`；**兩種都刪列**。
   - `pending` → 略過。
5. 有變動的表才 `write_*`（`extracted` 順便刷新）。兩表都寫完才寫 log；寫表失敗 → 回 false（log 不寫）。
6. 事件非空 → `append_log` 一行；事件為空 → **不寫**。
7. `--dry-run`：1–4 只算不做（不 deliver、不 say、不改表、不寫 log），`report.line` 照組，CLI 印到 stdout 前綴 `dry-run: `。

錯過的 `say()` 文字（單行，`<運行內容>`＝argv 以空白連接，或 ask 原文；`note` 非空時尾端加 `（備註：<note>）`）：
`行程「<id>」錯過了：原定 <at>，現在 <format_at(now)>，已從行程表刪除。要補做還是跳過？內容：<運行內容>`

`say()` 丟例外（agent 目錄在但沒初始化）→ 當 `error=<id>→<what()>`，該列**不更新、不刪**。

**ask 型 routine 的 `last_run` 在投出去的當下就更新**，不等 agent 回。理由：tick 是機械層，沒有任何管道知道
agent 什麼時候「做完」（agent 的回覆只進它自己的 `agents/<name>/log.md`）；若等回覆才更新，每一次心跳都會再
say 一次、把 agent 的收件匣灌爆。投出去＝這一輪的責任已交出，做沒做是 agent 的 log 要回答的事。

## `log.md` 一行

```
2026-08-30T17:00:05+08:00 turn=42 run=lint→hb-lint-42 ask=standup→bob missed=s-tq3k9x→none error=r-bad→every 不合法: 1h30m
```

- 開頭 `format_timestamp(now, tz)`，接 `turn=<turn>`，再接**依處理順序**的事件，全部單一空白分隔，行尾 `\n`。
- 事件＝`<kind>=<id>→<target>`；`kind` ∈ `run`／`ask`／`missed`／`error`；`target`：`run`→投出的指令 id、
  `ask`／`missed`→agent 名或 `none`、`error`→原因（原因裡的換行換成空白，好讓一行仍是一行）。
- **沒事的心跳不寫**：`--every 2s` 的世界一天有四萬多次心跳，全記只會把有用的行淹掉；心跳活著的證據在 loop 的
  `batch/<turn>/out/tick-<turn>.json`，不需要 log 重複。要看某天做了什麼：`grep '^2026-08-30' log.md`。

## 公開標頭：`include/aos/tick.hpp`

型別 `Instant`／`LocalTime`／`Run`／`Routine`／`ScheduleItem`／`Config`／`SlotSpec`／`ScheduleState`／`Event`／`Paths`／
`TickOptions`／`TickReport` 與各層函式的簽名都在標頭內、含註解，這裡不重抄。三條實作以**標頭為唯一契約**：
各層只透過它互相看見，**沒有共用的內部標頭**；每個 `.cpp` 自己的 helper 一律收在匿名 namespace。

## 檔案切分（`src/`，單檔 ≤ 300 行；三條並行，檔案不重疊）

分層單向：`paths ← clock ← ids ← table ← due ← log ← tick ← init ← cli`。右邊可以用左邊，左邊不知道右邊存在。
JSON 一律用 `nlohmann::ordered_json`（私有相依，不出現在標頭）。

| 條 | 檔案 | 職責 | 預估行數 |
|---|---|---|---|
| 1 | `src/paths.cpp` | `paths_of`、`single_agent`（列 `agents_dir` 子目錄） | 50 |
| 1 | `src/clock.cpp` | `parse_duration`、`valid_zone`、`to_local`／`from_local`（`std::chrono::locate_zone`＋`zoned_time`，GCC 16 實測可用）、`parse_timestamp`／`format_timestamp`、`parse_at`／`format_at` | 180 |
| 1 | `src/ids.cpp` | `valid_id`、`make_id`（`<prefix>-<base36(now)>`，撞 `taken` 就 `-2`、`-3`…） | 50 |
| 1 | `src/table.cpp` | `read_routines`／`read_schedule`／`write_routines`／`write_schedule`／`read_config`／`ensure_heartbeat`（`mkdir -p` + 缺的表寫空表）；`run` 欄的物件↔`Run`；表頭四欄；原子改寫（自己寫 `.tmp`＋`rename`，不 include `loop/src/`） | 240 |
| 1 | `tests/test_clock.cpp`、`tests/test_table.cpp` | 期間／時間戳／`at` 的往返與拒收；表的讀寫往返、缺欄、壞 run、重複 id、缺檔 config | 120 / 120 |
| 2 | `src/due.cpp` | `parse_slot`、`routine_due`、`routine_next`、`schedule_state` | 180 |
| 2 | `src/log.cpp` | `format_log_line`（`error` 的 target 換行→空白）、`append_log`（`O_APPEND`，一次 write 一行） | 60 |
| 2 | `src/tick.cpp` | `run_tick`：上面 1–7 步；missed 文字在這裡組 | 200 |
| 2 | `tests/test_due.cpp`、`tests/test_tick.cpp` | interval 的 `≥`／空 last_run；slot 的三條件、換日、遮罩；schedule 三態與 `missed_after` 邊界；`run_tick` 在 TempDir 世界裡：inbox 出現 `hb-<id>-<turn>.json`、`last_run` 更新、schedule 刪列、missed 走 say（建一個 `agents/bob/say/` 目錄驗檔案出現）、0／2 個 agent 記 `none`、dry-run 什麼都不動、無事不寫 log | 150 / 200 |
| 3 | `src/init.cpp` | `heartbeat_init`：`ensure_layout` → `ensure_heartbeat` → 原子寫 `every/tick.json`（`every_ms` 是 wire 不認得的欄，所以用 nlohmann 直接組，不走 `wire::to_json_text`） | 50 |
| 3 | `src/cli_common.cpp` | `extern "C"` 以外的 CLI 共用：可選 folder 位置參數（`is_directory(argv[1])`）、`--ask`／`-- argv`／`--note`／`--id` 解析、`now()` 取時鐘、對齊列印表格。宣告在 `src/cli_common.hpp`（**只給第 3 條的四個 CLI 檔 include**，是本專案唯一的內部標頭） | 30 / 150 |
| 3 | `src/tick_cli.cpp` | `aos_tick_cli_main`：`[folder] [--dry-run]`；turn＝`AOS_TURN` 有值就用，否則 `read_turn`；印 `report.line`（dry-run 加前綴）；有 `error` 事件退出碼 1 | 70 |
| 3 | `src/heartbeat_cli.cpp` | `aos_heartbeat_cli_main`：`init [folder] [--interval 30m]`（預設 `30m`，換算毫秒） | 60 |
| 3 | `src/routine_cli.cpp` | `aos_routine_cli_main`：`add [folder] (--every D \| --slot S) [--id ID] [--note …] (--ask … \| -- argv…)`／`ls [folder]`／`rm [folder] <id>` | 150 |
| 3 | `src/schedule_cli.cpp` | `aos_schedule_cli_main`：`add [folder] --at "YYYY-MM-DD HH:MM" [--id ID] [--note …] (--ask … \| -- argv…)`／`ls`／`rm <id>` | 130 |
| 3 | `CMakeLists.txt`、`tests/test_cli.cpp` | 見下；CLI 測試直接呼叫 `extern "C"` 進入點（同 `core/agent` 的作法 `LINK aos_tick_cli`），驗 add 缺 run 退出碼非 0、add→ls 看得到、rm 後消失、init 寫出的 `every/tick.json` 含 `every_ms` | 40 / 120 |

`ls` 的表（欄位左對齊、兩空白分隔、第一行是欄名；`RUN` 印 `argv: a b c` 或 `ask: …`）：
routine → `ID  KIND  EVERY/SLOT  LAST_RUN  NEXT  RUN  NOTE`（`NEXT`＝`format_at(routine_next)` 或 `到期`；列無效印 `無效`）；
schedule → `ID  AT  STATE  RUN  NOTE`（`STATE`＝`pending`／`due`／`missed`）。

CLI 退出碼：0 成功；1 執行失敗（讀寫表、deliver、id 不存在）；2 用法錯（缺 `--ask`/`-- argv`、`--every` 與 `--slot` 都給或都沒給、期間或時刻解析失敗、id 不合法或已存在）。

## CLI

```text
aos heartbeat init [folder] [--interval 30m]
aos tick [folder] [--dry-run]
aos routine  add [folder] (--every 7d | --slot "09:30 11111..") [--id ID] [--note "…"] (--ask "…" | -- argv…)
aos routine  ls [folder]        aos routine  rm [folder] <id>
aos schedule add [folder] --at "2026-09-01 17:00" [--id ID] [--note "…"] (--ask "…" | -- argv…)
aos schedule ls [folder]        aos schedule rm [folder] <id>
```

`folder` 省略時＝`loop::current_folder()`。`add` 的 `--` 之後全部是 argv。**不解析相對時間**（「今晚 8 點」）。
`every/tick.json` 寫出的內容：`{"id":"tick","argv":["aos","tick"],"every_ms":1800000}`——`every_ms` 目前只是寫出來，
`core/loop` 之後才會認得它；現在 loop 照 `aos run --interval` 的節奏每回合都跑 `aos tick`。

```cmake
aos_add_subproject(tick
    SOURCES src/paths.cpp src/clock.cpp src/ids.cpp src/table.cpp src/due.cpp src/log.cpp src/tick.cpp src/init.cpp
    HEADERS include/aos/tick.hpp
    PUBLIC_DEPS aos::loop
    PRIVATE_DEPS aos::agent
)
add_library(aos_tick_cli OBJECT src/cli_common.cpp src/tick_cli.cpp src/heartbeat_cli.cpp src/routine_cli.cpp src/schedule_cli.cpp)
target_link_libraries(aos_tick_cli PUBLIC aos::tick)
aos_add_subcommand(NAME tick      ENTRY aos_tick_cli_main      LIBRARY aos_tick_cli SUMMARY "跑一次心跳：到期的投進 inbox 或交給 agent")
aos_add_subcommand(NAME heartbeat ENTRY aos_heartbeat_cli_main LIBRARY aos_tick_cli SUMMARY "在資料夾裝上心跳（every/tick.json）")
aos_add_subcommand(NAME routine   ENTRY aos_routine_cli_main   LIBRARY aos_tick_cli SUMMARY "登記／列出／移除固定循環的事務")
aos_add_subcommand(NAME schedule  ENTRY aos_schedule_cli_main  LIBRARY aos_tick_cli SUMMARY "登記／列出／移除一次性行程")
aos_add_test(aos_tick_tests SOURCES tests/test_clock.cpp tests/test_table.cpp tests/test_due.cpp tests/test_tick.cpp tests/test_cli.cpp LINK aos_tick_cli)
```

`core/CMakeLists.txt` 要加一行 `add_subdirectory(tick)`（放 `agent` 之後）——**這行由隊長合併時加**，三條都不動它。
測試的 `TempDir`／`write_file`／`read_file` 照 `core/loop/tests/test_support.hpp` 的樣子在 `tests/test_support.hpp` 抄一份（第 2 條寫，第 1、3 條 include）。

## 驗收（隊長跑）

```sh
aos heartbeat init ./w --interval 2s && aos routine add ./w --every 2s -- sh -c 'date >> hb.txt'
aos run ./w --step 3 --interval 2000            # hb.txt 應有 ≥2 行，log.md 每行一個 run=
aos schedule add ./w --at "2020-01-01 00:00" --ask 補做嗎   # 下一回合：missed=…→none 且列已刪
```

## 已知不管

- 沒有鎖：`aos tick` 與 `aos routine add` 同時改 `routines.json`，後寫的贏（整檔 rename）。
- 不 `fsync`：`rename` 原子，斷電後內容可能是空的；`log.md` 用 `O_APPEND` 單次 write，不保證多行程交錯。
- 沒有崩潰恢復：deliver 成功後、寫表前被殺 → 下一次心跳會再投一次同一件事。
- 投出去就算做了：不追 `batch/<turn>/out/hb-*.json` 的結果，失敗的 argv 不重試；ask 有沒有被 agent 做完也不追。
- 時區只認 IANA 名稱（靠系統 `tzdata`）；`last_run` 的位移固定用 `tz`，換 `tz` 後舊值仍正確（含位移）但顯示會變。
- 夏令時間空缺／重疊：`from_local` 一律取最早的解；Asia/Taipei 沒有夏令時間，其他時區不保證合理。
- 未知欄位改寫時丟掉；`tabledb.py` 加進去的多餘欄會在下一次 tick 改寫時消失。
- 表裡的無效列每一次心跳都記一次 `error` 事件，不會自動移除，要人去修或 `rm`。
- `every/tick.json` 的 `every_ms` 目前沒人讀；心跳節奏＝`aos run --interval`。
- `single_agent` 只看目錄數，不驗那個目錄是不是活的 agent；`say()` 丟例外才會發現。
- id 只在同一張表內查重；routines 與 schedule 可以同名，指令 id 都會是 `hb-<id>-<turn>`，同回合同名就互相覆蓋。
