← [本輪報告](README.md)｜[notes 索引](../README.md)

# 開機合一、家不合一＋kernel 帳本換 sqlite：計畫（2026-09-24，P 隊）

使用者已拍板（[daemon-split-review 裁決](../2026-09-24-daemon-split-review/README.md)、WAIT_USER 的 one-program I 隊五題）。這頁寫開工前的打算，做完的真相看 [README.md](README.md)。

## 一句話

**daemon 除了當 cpu 的爸爸，也負責「定時開一格 `aos-kernel tick`」。** kernel cpu、tick 鏈、開機交接拿掉。kernel 帳本從 `K/state.json` 換成 `K/ledger.sqlite`。一條 `aos up` 開機、一條 `aos down` 停機。

## 改哪些檔

| 檔 | 改什麼 |
|---|---|
| 新 `lib/aos_kernel_store.py` | sqlite 帳本：開檔、建表、整份讀、只寫有變的列（一筆交易）、查一筆行程、舊 `state.json` 匯入 |
| `lib/aos_kernel_engine.py` | tick 不再放下一格、不再睡 `tick_ms`、不再 ack kernel cpu 的回音；一開始拿 `K/.tick.lock`；序號＝帳本 `last_seq`＋1；停好時請 daemon 別再開 tick |
| `lib/aos_kernel_ledger.py` | 存檔改走 store；拿掉 `tick_request`、`ack_ticks` |
| `lib/aos_kernel_boot.py` | boot 改成：驗 → 拿 tick 鎖 → （舊帳本）匯入、把舊 kernel 池縮到 0 → 寫帳本 → 建家 → 向 daemon 登記「請定時開 tick」 |
| `lib/aos_kernel_info.py` | 不再自動補 kernel 池；`tick_timeout_ms` 新鍵；開 tick 的 daemon＝頂層 `daemon`（沒寫就看舊的 `pools.kernel.daemon`） |
| `lib/aos_kernel_health.py`、`_rows.py`、`_ls.py`、`_check.py`、`_cpu.py`、`_cli.py` | 拿掉 kernel 池與 kcpu；「tick 停住」改看帳本 `last_tick_at`；新增 `aos-kernel proc NAME --json`；`ls --json` 升第 3 版 |
| 新 `lib/aos_daemon_ticks.py` | daemon 的「開 tick」：登記表 `D/kernels/<id>.json`、何時開、同時一格、逾時、連敗退避、停機時怎麼收 |
| `lib/aos_daemon_loop.py`、`_rpc.py`、`aos_daemon.py`、`_cli.py` | 收屍時認得 tick；新 method `tick`（登記／撤登記）；`ls` 多印 kernel 那幾行 |
| 新 `cli/aos`＋`lib/aos_up.py` | `aos up`、`aos down` |
| `lib/aos_agent*.py` | 不再直接開 `K/state.json`：改呼叫 store 的查一筆行程；`start` 的相容檢查改看 sqlite 帳本的 `features` |
| `lib/aos_team_post.py` | **兩行**（讀 `K/state.json` 的 procs 改成呼叫 store）——別隊地盤，報告寫明 |
| 測試、規範、教程、索引 | 見報告 |

## 帳本表結構（`K/ledger.sqlite`，WAL 模式）

| 表 | 一列是什麼 | 欄 |
|---|---|---|
| `meta` | 一個小鍵 | `key`、`value`（JSON）：`version`（3）、`chain`、`cli`、`ticker`（開 tick 的 daemon 家）、`last_seq`、`last_tick_at`、`phase`、`halting`、`features`、`recent`、`stale`、`ready`、`delayed`、四個出貨箱 |
| `procs` | 一個行程 | `name`（主鍵）、`status`、`pool`、`body`（整筆 JSON，跟舊 `procs.<名>` 同形） |
| `pools` | 一個池 | `name`、`body`（跟舊 `pools.<P>` 同形） |
| `busy` | 一顆忙的 cpu | `cpu`（`P/<i>`）、`ord`（巡檢輪轉的順序）、`proc`、`body`（`{req, proc, discard}`） |

- `on`（行程 → 在哪顆）不再存：從 `busy` 反推（`busy.proc` 有索引）。
- tick 照舊整份讀進記憶體、照舊一格最多存三次（出貨完、決定完、出貨完）；**每次存＝一筆交易，只寫有變的列**。崩在交易中間＝整筆沒發生。
- 讀的人（`ls`、`proc`、agent）用同一支 lib 開連線只讀；WAL 讓讀不擋寫。

## tick 怎麼被開

daemon 每圈（`poll_ms`，預設 20 ms）看每個登記的 kernel 家：
1. 有一格在跑 → 看逾時（`tick_timeout_ms`，預設 60 秒）；到了就整組 KILL，算一次失敗。
2. 沒在跑 → 下面任一成立就開一格（當孩子、不等它）：時間到（上一格開始後 `tick_ms`）；`K/requests/` 出現「上一格開始時還沒有」的檔（只 stat 資料夾的修改時間，變了才列目錄比名字，不讀內容）。`wake` 就是往 `K/requests/` 丟檔，所以也算。
3. 一格退出：0＝好；75＝鎖被佔（別人在跑），不算失敗，`tick_ms` 後再試；其他＝失敗，stderr 記一行，退避 `tick_ms×2^(連敗−1)`、最多 60 秒，**不自己停**。

## 鎖

`K/.tick.lock` 的獨占 flock，tick 一開始非阻塞地拿，拿不到退 75。行程死了（含 kill -9）鎖自己消失。boot 寫帳本時也拿這把（阻塞、最多 `--wait-ms`）。tick 自己也設鬧鐘（`tick_timeout_ms`），daemon 被殺後留下的孤兒 tick 卡住也會自己死。

## 崩潰窗口（要寫測試的）

| 崩在 | 下一格怎麼接 |
|---|---|
| tick 寫帳本的交易中間（kill -9） | sqlite 回滾：整筆沒發生，下一格重讀同樣的原單重判 |
| tick 放了派工單、還沒存出貨完 | 同舊版：「先記後放」，下一格靠 `recent` 補放、EEXIST 當已放 |
| tick 卡住 | daemon 逾時 KILL 整組，算失敗、退避；鎖跟著消失 |
| daemon 被 kill -9、tick 正在跑 | tick 變孤兒，自己跑完退出；新 daemon 開的 tick 拿不到鎖就退 75、下一次再試；cpu 照舊由新 daemon 殺掉重拉 |
| `aos down` 時 tick 正在跑 | kernel halt 要 tick 繼續跑才停得好；停好那格請 daemon 撤登記；daemon 停機時還在跑的 tick 等 `stop_wait_ms＋kill_wait_ms`，再不退就 KILL |
| boot 寫好帳本、還沒登記 | daemon 不開 tick；`ls` 報「沒人開 tick」，再 boot（或 `aos up`） |

## 要改的前提

- daemon「不認識 kernel」→ 改成「只認得 kernel 的家在哪、多久開一格；不讀 kernel 家的檔案內容」。
- kernel「在 kernel cpu 上一格接一格」→ 改成「daemon 定時或有新單時開一格，同時只准一格」。
- kernel 的家「照 cpu 範式、帳本是 state.json」→ 只對帳本放寬：帳本是 sqlite；requests／responses／pools 仍是檔案。
