# aos-lock

`aos-lock - 鎖：mkdir 一個 .lock/ 資料夾，掛上名牌，持有者死了別人能收`（NAME，C-54 R1）

**一句話：`aos-lock 子命令 [旗標...] 目標`——NORMS [N-15](../../docs/NORMS/05-基礎設施-窗.md)（10-29 補）的鎖：`acquire` 用 mkdir 拿 `<資料夾>/.lock/` 或 `<檔>.lock/`、在裡面寫名牌 `holder.json`，`release` 先改名再刪，`show` 印名牌；拿不到時看名牌，持有者死了（pid＋`started_at_ticks`＋`boot_id` 對不上）或租約過了就替它收。**
一個 lib（`lib/libaos-lock.a`，公開標頭 `include/aos/lock.hpp`，aos-post 的有順序投遞連它）加一支薄命令列（`bin/aos-lock`）。只連 aos-util。全家慣例見 [impls/README.md](../README.md)；設計見 [thinking 10-29 medium-plan § 五](../../thinking/2026-10-29-medium-plan.md)。

像會議室門口的牌子：先把牌子掛上門（mkdir，只有一個人掛得上）再寫上名字；用完先把牌子摘下拿走（改名）再丟。牌子上的人早就下班了（行程不在）或寫的時段過了（租約），下一個人可以自己摘掉換上自己的。這是約定，不是門鎖：從 Linux 繞過去 aos 不管（決定 10）。

```sh
aos-lock acquire --note "改 data" data.json && 改 data.json && aos-lock release data.json   # 鎖是 data.json.lock/
aos-lock acquire --wait-ms 5000 some_dir/                                                    # 鎖是 some_dir/.lock/，最多等 5 秒
aos-lock show data.json                                                                      # 印名牌；沒有鎖退 10
```

## 用法

旗標寫在位置參數前面（aos-util 的 `parse_cli`）。結束碼照 N-43：0 成功、10 沒東西（拿不到、沒有鎖）、1 錯。

| 子命令 | 做什麼 |
|---|---|
| `acquire [--lease-ms N] [--note 字] [--wait-ms N] [--pid N] 目標` | 拿鎖：拿到退 0（不印東西）；被活人拿著退 10。`--wait-ms`＝拿不到每 20 毫秒再試、最多等 N 毫秒（沒給＝只試一次）。`--lease-ms`、`--note` 寫進名牌 |
| `release 目標` | 放鎖：改名成 `<鎖>.releasing.<信號>` 再刪。不看是誰的鎖（約定）。鎖不在退 1 `LockMissing` |
| `show 目標` | 名牌 stdout 印一行；沒有鎖退 10；鎖在但名牌不在或讀不懂退 1 `HolderBad` |

- **目標 → 鎖**：結尾是 `/` 或是現有的資料夾＝`<目標>/.lock/`；其他（檔、還不存在的名字）＝`<目標>.lock/`。相對路徑從 cwd 算。鎖的上一層不在＝`MkdirFailed`（不替人建）。不檢查上下層（鎖了資料夾不等於鎖了裡面的檔）。
- **名牌 `holder.json`**：`{"holder", "pid", "started_at_ticks", "boot_id", "acquired_at", "lease_ms"?, "note"?}`。`holder`＝`$AOS_WS`（轉絕對），沒設或空＝`$HOME`，都沒有＝`/`（同 aos-post 的 `sender`）。**`pid` 預設是叫 aos-lock 的那個行程**（getppid）——aos-lock 拿完就退，寫它自己等於一拿到就算死了；要寫別的行程用 `--pid`（那個行程要在，不在＝`ArgumentsBad`）。`started_at_ticks`、`boot_id` 讀 `/proc`（讀不到＝null）；`acquired_at`＝ISO 8601 UTC 到毫秒。先寫 `.holder.json.tmp` 再改名。
- **收屍**（mkdir 失敗時）：讀名牌，下面任一條成立就照放鎖的步驟替它收、再 mkdir（改名只有一個人會成功，兩人同時收也沒事）——
  ① `boot_id` 跟現在的不同；② `pid`＋`started_at_ticks` 對不上（行程不在、pid 被重用；`started_at_ticks` 是 null＝只看 pid 在不在）；③ 行程是殭屍（結束了、父行程還沒收屍）；④ 有 `lease_ms` 且 `acquired_at`＋`lease_ms` 已過（持有者活著也收）；⑤ 名牌不在或讀不懂、且鎖資料夾 10 秒沒動過（持有者 mkdir 完還沒寫好名牌就死了；10 秒不開 key）。
  好幾個人同時判到同一把死鎖時，直接改名會搬走別人剛拿到的新鎖（10-29 實測，20 個人同時收撞到過），所以收之前先在鎖裡 `mkdir .reaping`（收屍牌，只有一個人建得成；牌子 10 秒沒動＝收的人也死了，拔掉再來），再讀一次名牌：跟判的那份不同（牌子掛進了別人的新鎖）＝拔掉牌子、不收；名牌本來就不在的還要是同一個資料夾（inode）。
- **殘骸**：`<鎖>.releasing.*` 是別人放到一半的，名字不同、不擋人，aos-lock 不碰。

## 元素

```
 main ──▶ 子命令表 ──▶ parse_cli ──▶ lock_dir_of ──▶ acquire（try_acquire：mkdir → 寫名牌｜look → reapable → reap）｜release｜look
```

| 檔 | 做什麼 |
|---|---|
| `include/aos/lock.hpp` | 公開介面：`Holder`、`Seen`、`STALE_MS`；`lock_dir_of`、`identity`、`holder_of`、`to_json`、`look`、`reapable`、`try_acquire`、`acquire`、`release`；自己的代號 |
| `src/holder/holder.cpp` | 名牌：`identity`、`holder_of`、`to_json`、`look`、`reapable`（判死活、殭屍、租約）；common 的 `now_ms`、`parse_at`、`unique_id` |
| `src/lock/lock.cpp` | 鎖：`lock_dir_of`、寫名牌（暫存改名、不建資料夾）、`try_acquire`、`reap`（收屍牌 `.reaping` → 再讀名牌確認 → 改名再刪）、`acquire`（steady_clock 計時）、`release` |
| `src/common/common.hpp` | 內部標頭：`using`、時間與名字小工具的宣告 |
| `src/main.cpp` | 命令列：子命令表、旗標、持有者預設 getppid；出錯印「aos-lock: 代號 原因」 |

## 錯誤代號

stderr 一行 **`aos-lock: 代號 原因`**、退 1。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`、`FlagUnknown`（共用） | 子命令沒給、目標不是剛好一個、`--lease-ms`／`--wait-ms`／`--pid` 不是非負整數、`--pid` 的行程不在、不認得的旗標 |
| `CommandUnknown`（同 aos-json） | 不認得的子命令 |
| `LockMissing` | `release`：鎖不在 |
| `HolderBad` | `show`：鎖在，名牌不在或讀不懂 |
| `MkdirFailed`、`WriteFailed`、`Internal`（共用） | 鎖資料夾建不了（上一層不在、沒權限）；名牌寫不了、改名不了；照理不會發生的 |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

依賴：aos-util（`add_subdirectory` 一起編）。`ctest` 跑 `test_cli`（`tests/test_cli.py`，unittest）：命令列的錯、目標換鎖、名牌各欄（`pid`＝叫它的行程、`--pid`）、十個行程搶同一把只有一個拿到、kill -9 持有者後收屍、`boot_id` 不同的舊名牌、pid 被重用、租約到期、名牌沒寫好就死（10 秒）、`started_at_ticks` 是 null、30 個人同時收同一把死鎖只有一個拿到（收屍牌；機率性的守門，拿掉收屍牌時 10 次約紅 2 次）、`--wait-ms` 逾時與等到、release 不留殘骸、`.releasing.*` 殘骸不擋人。

## 已知限制

- 只支援 Linux（`/proc`）。持有者在別的 PID namespace（沙箱）裡時，外面看到的 pid 對不上，會被當成死了收掉——鎖要跨 namespace 用時，兩邊要看得到同一套 pid。
- 收屍牌擋得住「判完被別人收掉又拿走」；擋不住的剩兩個角落：名牌本來就不在、新鎖剛好拿到同一個 inode 號又還沒寫名牌；租約到期的持有者自己放鎖、緊接著有人 mkdir、收的人才改名。這是約定（決定 10），不必擋得住。
- 租約到期會收活人的鎖：原持有者之後 `release` 會放掉新持有者的鎖（release 不看是誰的）。要用租約的人自己守時。
- flock 加速（N-15 ④）沒做：等鎖是每 20 毫秒輪詢。
