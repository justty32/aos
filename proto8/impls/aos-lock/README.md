# aos-lock

`aos-lock - 鎖：mkdir 掛名牌，flock 判庫持有者死活，租約按格算`（NAME，C-54 R1）

**一句話：`aos-lock 子命令 [FLAGS...] 目標`——NORMS [N-15](../../docs/NORMS/05-基礎設施-窗/04-N-15.md)的鎖：`acquire` 用 mkdir 拿 `<資料夾>/.lock/` 或 `<檔>.lock/`、在裡面寫名牌 `holder.json`，`release` 先改名再刪，`show` 印名牌；拿不到時看名牌，庫持有者的 `holder.flock` 已釋放或租約過了就替它收；命令列拿完就退出，要自行 `release` 或給租約。**
一個 lib（`lib/libaos-lock.a`，公開標頭 `include/aos/lock.hpp`，aos-post 的有順序投遞連它）加一支薄命令列（`bin/aos-lock`）。只連 aos-util。全家慣例見 [impls/README.md](../README.md)；設計見 [thinking 10-29 medium-plan § 五](../../thinking/2026-10/29/medium-plan/README.md)。

像會議室門口的牌子：先把牌子掛上門（mkdir，只有一個人掛得上）再寫上名字；用完先把牌子摘下拿走（改名）再丟。庫持有者已經離開（flock 試鎖成功）或寫的時段過了（租約），下一個人可以自己摘掉換上自己的。這是約定，不是門鎖：從 Linux 繞過去 aos 不管（決定 10）。

```sh
aos-lock acquire --note "改 data" data.json && 改 data.json && aos-lock release data.json   # 鎖是 data.json.lock/
aos-lock acquire --wait-ms 5000 some_dir/                                                    # 鎖是 some_dir/.lock/，最多等 5 秒
aos-lock show data.json                                                                      # 印名牌；沒有鎖退 10
```

## 用法

子命令的旗標寫在它的位置參數前後都收（aos-util 的 `parse_cli`；P-44 續）。結束碼照 N-43：0 成功、10 沒東西（拿不到、沒有鎖）、1 錯。

| 子命令 | 做什麼 |
|---|---|
| `acquire [--lease-cycles N] [--note 字] [--wait-ms N] 目標` | 拿鎖：拿到退 0（不印東西）；鎖仍有效退 10。`--wait-ms`＝拿不到每 20 毫秒再試、最多等 N 毫秒（沒給＝只試一次）。`--lease-cycles`、`--note` 寫進名牌；不給租約＝不因時間到期 |
| `release 目標` | 放鎖：先在鎖裡建收屍牌 `.reaping`、關掉本行程的 `holder.flock`，再改名成 `<鎖>.releasing.<獨一無二的名字>` 再刪（/mnt/c 上資料夾裡有檔案開著就改名不了，所以先關（不影響並發語意）；牌子擋著別人收；建不成牌子＝先改名再關）。改名遇 EACCES 短暫重試約 0.5 秒。**先認主**（設計-52）：名牌的 `holder` 跟這次呼叫的身分（`AOS_WS`／`AOS_STACK`／`AOS_CF` 或 cwd）不同＝別人的，stderr 一行 warning、不放、退 10；`--force` 不看；名牌讀不到＝照放。庫的 `release` 另比本行程登記的 `holder.flock` 是不是鎖裡那一個，不是＝只關自己的 fd、回 false。同一個工作區裡兩個人拿同一把鎖仍分不出來。鎖不在退 1 `LockMissing` |
| `show 目標` | 名牌 stdout 印一行；沒有鎖退 10；鎖在但名牌不在或讀不懂退 1 `HolderBad` |

- **目標 → 鎖**：結尾是 `/` 或是現有的資料夾＝`<目標>/.lock/`；其他（檔、還不存在的名字）＝`<目標>.lock/`。相對路徑從 cwd 算。鎖的上一層不在＝`MkdirFailed`（不替人建）。不檢查上下層（鎖了資料夾不等於鎖了裡面的檔）。
- **名牌 `holder.json`**：`{"holder", "acquired_at", "acquired_at_cycles"?, "lease_cycles"?, "flock"?, "note"?}`。`holder`＝aos-util 的 `aos::identity()`：`$AOS_WS` ＞ `$AOS_STACK` ＞ `$AOS_CF` ＞ cwd，空字串算沒設、轉絕對路徑（同 aos-post 的 `sender`）。`acquired_at`＝ISO 8601 UTC 到毫秒，永遠寫；有 `AOS_CLOCK` 時才寫非負整數 `acquired_at_cycles`；給租約才寫非負整數 `lease_cycles`（0＝立即到期）。透過已開啟的鎖目錄 fd 先寫 `.holder.json.tmp`，確認寫入與關檔成功再 `renameat` 成名牌，縮排 2、無尾端換行；目錄開啟後即使被改名，也不會誤寫別人新建的鎖。
- **持有者死活**：庫拿鎖時建立 `holder.flock`、取獨佔 flock，fd 保留到 `release` 或行程結束；名牌寫 `"flock": true`。別人只對有此標記的鎖試 `LOCK_EX | LOCK_NB`，拿得到＝庫持有者已經離開，能收；拿不到＝仍持有。行程被 SIGKILL 或重開機，kernel 都會放掉 flock，不必讀 `/proc`。命令列 `acquire` 拿完即退出，名牌不寫 `flock`，不做死亡回收：**命令列拿鎖要記得 `release`，或指定 `--lease-cycles`**。
- **租約按格算**（[N-65](../../docs/NORMS/02-設計理念-時空.md)）：讀的人自己有時鐘、名牌也有 `acquired_at_cycles`，以 `now_cycle >= acquired_at_cycles + lease_cycles` 判到期；時鐘檔停著，正數格數租約等再久也不到期（0 格仍立即到期）。`AOS_CLOCK` 指向的鐘檔不存在時，印 warning 並當作格數 0，仍算有時鐘；若一直不存在或一直停在 0，從 0 起算的正數格數租約永遠不到期，不會退牆鐘。其他情況以牆鐘 `acquired_at + lease_cycles × clock_interval_ms()` 判到期。`AOS_CLOCK_INTERVAL` 沒設＝1000 毫秒；例如設 500、租約 2 cycles，沒有時鐘時約 1 秒。租約到期可以收活持有者的鎖。
- **收屍**（mkdir 失敗時）：flock 表示持有者已離開、租約到期、或名牌不在／讀不懂且鎖資料夾 10 秒沒動，任一成立即可收。收之前先在鎖裡 `mkdir .reaping`（收屍牌，只有一個人建得成；牌子 10 秒沒動＝收的人也死了，拔掉再來），再讀一次名牌：跟判的那份不同＝拔掉牌子、不收；也要是同一個資料夾（inode）。建立收屍牌會更新 mtime，因此重新檢查沿用判定時的年齡，避免殘缺名牌永遠收不掉。之後把鎖資料夾改名再刪、重新 mkdir。
- **牆上時鐘**：名牌不在／讀不懂與收屍牌的 10 秒，一律看檔案 mtime，不數格；mtime 在未來 10 秒以上同樣當過期。有時鐘的租約只看格數；退牆鐘的租約遇到校時，往前跳會提早到期、往回跳會延後。
- **殘骸**：`<鎖>.releasing.*` 是別人放到一半的，名字不同、不擋人，aos-lock 不碰。/mnt/c 上偶爾會留一個（刪的那一刻別人開著裡面的檔）。aos-sweeper 會清 daemon 各 stack 底下 10 分鐘以上的（open-14）。

## 元素

```
 main ──▶ 子命令表 ──▶ parse_cli ──▶ lock_dir_of ──▶ acquire（try_acquire：mkdir → 寫名牌｜look → reapable → reap）｜release｜look
```

逐檔「哪個檔負責什麼」從檔頭一句話生成，在 code map 的 [逐檔表 impls.json](../../../wf/knowledge/code-map/proto8/impls.json)（`#/tree/aos-lock`）；改說明去改檔頭。

## 錯誤代號

stderr 一行 **`aos-lock: error: 代號 原因`**、退 1。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`、`FlagUnknown`（共用） | 子命令沒給、目標不是剛好一個、`--lease-cycles`／`--wait-ms` 不是非負整數、不認得的旗標 |
| `CommandUnknown`（全家共用，aos-util） | 不認得的子命令 |
| `ClockBad`（aos-util） | `AOS_CLOCK` 鐘檔讀不了（不存在時只 warning 並當 0）或內容壞、牆鐘換算時的 `AOS_CLOCK_INTERVAL` 壞 |
| `LockMissing` | `release`：鎖不在 |
| `HolderBad` | `show`：鎖在，名牌不在或讀不懂 |
| `MkdirFailed`、`WriteFailed`、`Internal`（共用） | 鎖資料夾建不了（上一層不在、沒權限）；名牌或 flock 檔開不了／鎖不了、名牌寫不了、改名不了；照理不會發生的 |

## 建置與測試

```sh
cmake -B build && cmake --build build
```

依賴：aos-util（`add_subdirectory` 一起編）。

## 已知限制

- 使用 Linux flock；跨 PID namespace 也能認同一把檔案鎖，兩邊必須看得到同一個檔案系統中的同一個鎖檔，檔案系統必須支援 flock。複製鎖資料夾不會複製活的 flock。
- 收屍牌擋得住「判完被別人收掉又拿走」；仍有幾個角落：mkdir 後、開鎖目錄前停頓超過 10 秒，原鎖可能被收走，恢復時打開的是替代鎖；名牌本來就不在、新鎖剛好拿到同一個 inode 號又還沒寫名牌；租約到期的持有者自己放鎖、緊接著有人 mkdir、收的人才改名。這是約定（決定 10），不必擋得住。
- 租約到期會收活人的鎖：原持有者之後 `release` 不會放掉新持有者的鎖（認主，見上）——但兩者身分一樣（同一個工作區）時仍會放掉。要用租約的人自己守時。
- flock 用來判庫持有者死活；等鎖仍每 20 毫秒輪詢，`--wait-ms` 用 steady_clock，凍住時鐘不會凍住等鎖時間。
- fd 以絕對鎖路徑登記；`release` 會關掉本行程登記的 fd，即使鎖已被別人移走。fork 子行程會先關掉繼承的 fd，exec 也不繼承。
- 租約比較避免加法／乘法溢位；數學期限超出可表示的格數／毫秒時，不會繞回而提早過期。
- 沒有時鐘或名牌沒有格數時，租約退牆鐘，校時風險照上面說明；不同樹的格數不可直接相比，共用鎖應使用同一個時鐘。
