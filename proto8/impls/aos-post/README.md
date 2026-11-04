# aos-post

`aos-post - 投遞：把一封信寄進信箱、處理者一封封認領`（NAME，C-54 R1）

**一句話：`aos-post 子命令 [旗標...] 信箱 [信件名稱]`——NORMS [N-16](../../docs/NORMS/05-基礎設施-窗.md)的標準投遞：寄信人 `send` 把一封信放進信箱的 `new/`，處理者 `take`／`take-all` 一封封拿進 `cur/`、`see` 讀信、`done` 收掉（要回信就照信裡的 `reply_to` 投一封回去），還沒被拿走的寄信人可以 `regret` 撤回。**
aos-post 是 aos 體系跨行程交流（IPC）的語法糖、基底工具：跟 aos proc 的關聯不深，proc 自己拿它組出想要的效果（[thinking 11-03 aos-post](../../thinking/2026-11/03/aos-post.md)）。
一個 lib（`lib/libaos-post.a`，公開標頭 `include/aos/post.hpp`，aos-daemon 的信箱模式、aos-llm-kernel、aos-llm-send 連它）加一支薄命令列（`bin/aos-post`）。連 aos-util、aos-lock（有順序的投遞）。全家慣例見 [impls/README.md](../README.md)；最早的設計見 [thinking 10-29 medium-plan § 二](../../thinking/2026-10/29/medium-plan/README.md)。

像公司的收發室：寄件人在後面的桌上（`tmp/`）把信封好，封好才放進待收籃（`new/`）；收件人把信從籃子拿到自己桌上（`cur/`）就算簽收，簽收了寄件人就抽不回來；辦完撕掉，或歸檔（`archive/`）。掛號信（有序）永遠先收，平信（無序）排在後面。

```sh
aos-post init box                                   # 建 box/tmp new cur
echo '{"procs_added": {"bob": "../agent-bob"}}' | aos-post send box      # 印信件名稱
aos-post take-all box                               # 一行一個信件名稱（照處理順序）；沒有退 10
aos-post see box                                    # 讀 cur/ 照處理順序第一封；好信印 letter.json、壞信退 1
aos-post done box                                   # 收掉那一封（--keep 進 archive/）
```

## 用法

旗標寫在位置參數前面（aos-util 的 `parse_cli`，同全家）。結束碼照 N-43：0 成功、10 沒東西、1 錯。

| 子命令 | 做什麼 |
|---|---|
| `init 信箱` | 建信箱與 `tmp/`、`new/`、`cur/`（上層沒有一起建；已經有＝沒事）。`archive/` 不建 |
| `send [--ordered] [--reply-to 信箱] [--in-reply-to 信件名稱] 信箱 [信件名稱] < body.json` | 寄一封，stdout 印 `new/` 裡的名字。不給信件名稱＝自動生成；`--ordered`＝名字前加 12 位序號。stdin 一份 JSON＝`body`（任何 JSON 值；空的＝`{}`） |
| `take 信箱` | `new/` 照處理順序，認領第一個 rename 得進 `cur/` 的，印它的名字；沒有退 10。`cur/` 沒有就建 |
| `take-all 信箱` | 認領 `new/` 裡全部，一行一個（照處理順序）；沒有退 10。`cur/` 沒有就建 |
| `see 信箱 [信件名稱]` | 讀 `cur/<名>/letter.json`：好信 stdout 印一行（整份）；壞信退 1、`LetterBad 原因`。不給名字＝`cur/` 裡照處理順序第一封；`cur/` 空退 10 |
| `done [--keep] [--reply] 信箱 [信件名稱] [< body.json]` | 處理完：預設 rename 回 `tmp/` 再刪；`--keep`＝rename 進 `archive/`（沒有就建）。壞信一律丟掉（不管 `--keep`、不回信）。`--reply`＝stdin 一份 JSON 當 body，照那封的 `reply_to` 投一封回信（`in_reply_to`＝原信的名字），stdout 印回信的名字；那封沒寫 `reply_to`＝不回、不印。不給名字＝`cur/` 裡照處理順序第一封；`cur/` 空退 10 |
| `regret 信箱 信件名稱` | 撤回：rename `new/<名>` 回 `tmp/` 再刪；已被認領（或本來就沒有）退 1 `RegretFailed`。名字必給（「撤最新的」會撤到別人的） |

- **信箱**＝一個資料夾（不是＝`MailboxMissing`），位置由擁有者定（N-16）。各子命令只驗自己用到的格，少了＝`MailboxMissing`、不替人建（`init`、下面兩處例外）：
  - `send`：`tmp/`、`new/` 是資料夾，**而且對自己可寫**（`access(2)` 驗 `W_OK|X_OK`，照字面驗、不試寫；不過＝`MailboxBad`）。不看 `cur/`。
  - `take`／`take-all`：`new/`；`cur/` 沒有就建（建不了＝`MkdirFailed`）。
  - `see`：`cur/`。`done`：`cur/`、`tmp/`；`--keep` 時 `archive/` 沒有就建。`regret`：`new/`、`tmp/`。
- **信件名稱**兩種形狀：**有序**＝`<12 位序號>.<尾名>`（名字匹配 `^[0-9]{12}\.`），**無序**＝其他。尾名＝`send` 自己給的；不給＝`<UTC 奈秒 20 位>.<pid>.<started_at_ticks>`（aos-util 的 `unique_id`，時間開頭；`sent_at` 取自同一刻）。
  - **處理順序**（`take`、`take-all`、`see`／`done` 不給名字時、aos-daemon 排 `cur/` 殘骸都是這一套，庫裡的 `sort_letters`）：有序全部在前、照名字排（12 位同寬＝照序號）；無序全部在後、照名字排（預設名時間開頭＝寄出先後；自己給的照字面排，不讀 `sent_at`）。無序的被有序的一直插隊也接受。
  - **缺號不等**：不讀 `order.json`、不算期望的下一號、不逐號探——列出 `new/`、排好、從頭 rename，第一個成功的就是（下一號在幾百號之後也一樣快）。
  - **自己給的名字**（`send 信箱 名字`）：不空、不含 `/`、不以 `.` 開頭，而且**不得像有序名**（不然會被當成插隊的有序信）；不合＝`ArgumentsBad`。`--ordered` 加自己給的＝`<序號>.<自己給的>`。`tmp/` 或 `new/` 已有同名的＝`LetterExists`（`tmp/` 的半截自己刪）；預設名撞名換一個再試。`cur/`、`archive/` 已有同名的 `send` 不擋；`take` 搬不進 `cur/`（同名的還在處理）就跳過、那封留在 `new/`。
  - 命令列其他地方給的名字（`see`／`done`／`regret`／`--in-reply-to`）只驗前三條（有序名在那裡合法），不合＝`ArgumentsBad`。
- **`letter.json`**：`{"sender", "sent_at", "reply_to"?, "in_reply_to"?, "body"}`（沒有 `kind`；讀到也只是不認得的 key、忽略）。
  - `sender`（寄件人身分＝路徑）＝aos-util 的 `aos::identity()`：`$AOS_WS` ＞ `$AOS_STACK` ＞ `$AOS_CF` ＞ cwd，空字串算沒設、轉絕對路徑；cwd 拿不到＝`Internal`。人也一樣。
  - `sent_at`＝ISO 8601 UTC 到毫秒（`2026-11-03T01:58:45.123+00:00`，寫法同 aos-util 的 `utc_now_ms`）。
  - `reply_to`＝`--reply-to` 給的信箱，轉絕對後照 `send` 的信箱驗法驗（是資料夾、`tmp/`、`new/` 是資料夾而且可寫）；不過＝`MailboxMissing`／`MailboxBad`，信不寄。
  - `in_reply_to`＝原信的名字（只驗是單純的名字，不驗那封在不在——它多半已經被收掉了）。
- **壞信**（`see` 退 1、`done` 丟掉）：`letter.json` 讀不了或不是 JSON 物件、`sender`／`sent_at` 不是字串、沒有 `body`、`reply_to`／`in_reply_to` 有但不是字串。名字有序無序都不算壞。`body` 的形狀由收信的程式自己驗。不通知寄信人（決定 27）；記 `mailbox_warning` 是處理者的事（拿 `see` 的原因）。
- **回信寄不出去**（`reply_to` 那個信箱沒了、不可寫）：退 1，原信**留在 `cur/`**，可以再 `done` 一次。
- **有順序的投遞**（`send --ordered`，N-16、[medium-plan § 三](../../thinking/2026-10/29/medium-plan/README.md)）：信箱多兩樣——`order.lock/`（[aos-lock](../aos-lock/README.md) 的鎖，持有者＝這個 aos-post 行程）與 `order.json`（`{"counter_letters": N}`，沒有＝0）。步驟：信照常先在 `tmp/<尾名>` 寫好 → 拿 `order.lock/`（拿不到每 20 毫秒再試、**一直等**；持有者死了照 aos-lock 收屍）→ 讀 N → `order.json` 寫 N+1（暫存改名）→ rename 成 `new/<N+1 零填 12 位>.<尾名>` → 放鎖。鎖握到 rename 完，所以到 `new/` 的順序＝取號順序。`order.json` 讀不懂＝`OrderBad`（放鎖、信丟掉）。
  - **會缺號、不會重號**：寄信人死在「寫完 N+1、還沒 rename」之間，那個號就缺了（信留在 `tmp/`）；處理者照上面的處理順序直接拿下一號。
  - 同一個信箱有序、無序都收；`send` 不管信箱是不是「有序信箱」。
- `tmp/` 處理者永遠不看；`new/`、`cur/` 裡 `.` 開頭的名字不算信（N-05）。不是資料夾的東西出現在 `new/` 也認領得到，`see` 算壞信、`done` 丟掉。`archive/` aos-post 永遠不讀。

## 元素

| 檔 | 做什麼 |
|---|---|
| `include/aos/post.hpp` | 公開介面（函式清單與說明在檔頭）：`Mailbox`、`SendOpts`、`Seen`；自己的代號 |
| `src/mailbox/mailbox.cpp` | 信箱路徑、`init`、`open`；信件名稱的規則 `check_name`、`is_ordered`、`sort_letters`；共用小工具（宣告在 `src/common/common.hpp`：`need_dir`、`make_dir`、`names_in`、`move`、`drop`） |
| `src/send/send.cpp` | `send`：入口檢查（可寫、`reply_to`、名字）、預設名與 `sent_at`（同一刻）、自己給的名字與 `LetterExists`；`--ordered` 的 `post_ordered` |
| `src/take/take.cpp` | `take`、`take_all`（`cur/` 沒有就建）、`first_in_cur`、`see`（驗信封）、`reply`、`done`（`archive/`）、`regret` |
| `src/main.cpp` | 命令列：子命令表、旗標、`see`／`done` 不給名字時取第一封、印結果、錯誤一行 |

## 錯誤代號

stderr 一行 **`aos-post: 代號 原因`**、退 1。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`、`FlagUnknown`（共用） | 子命令沒給、位置參數個數不對、信件名稱不是單純的名字、`send` 自己給的名字像有序名、旗標缺值、開關帶值、不認得的旗標 |
| `CommandUnknown`（全家共用，aos-util） | 不認得的子命令（舊名 `claim`、`check`、`finish`、`withdraw` 也是） |
| `InputBad`、`InputExtra`（共用） | `send`、`done --reply` 的 stdin 解不出 JSON、有好幾份 |
| `MailboxMissing`（全家共用，aos-util） | 信箱不是資料夾、子命令用到的格不是資料夾；`--reply-to`／回信時 `reply_to` 指的不是信箱 |
| `MailboxBad` | `send`（含回信）：信箱的 `tmp/` 或 `new/` 對自己不可寫 |
| `LetterMissing`（同 aos-llm-send） | `see`、`done`：信不在 `cur/` |
| `LetterBad` | `see`：壞信 |
| `LetterExists` | `send` 自己給的名字：`tmp/` 或 `new/` 已有同名的 |
| `RegretFailed` | `regret`：信不在 `new/` |
| `OrderBad` | `send --ordered`：`order.json` 在但不是 `{"counter_letters": 非負整數}` |
| `MkdirFailed`、`WriteFailed`、`Internal`（共用） | 建不了資料夾；寫不了、改名不了（`done --keep` 時 `archive/` 已有同名的也是）；照理不會發生的（cwd 被刪） |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

依賴：aos-lock、aos-util（`add_subdirectory` 一起編）。`ctest` 跑 `test_cli`（`tests/test_cli.py`，unittest；各段涵蓋什麼寫在檔頭）：含 20 個寄信人並發 200 封不漏不重、`tmp/` 的半截信永遠不被認領、`--ordered` 50 個寄信人序號從 1 連續、持有者死了收屍繼續（缺號不重號）、亂 kill -9 寄信人不重號也不卡鎖；自己給名字、有序無序同箱的順序、缺號直接拿下一號、`see`／`done` 不給名字、`take` 建 `cur/`、可寫檢查、`reply_to` 的驗法、`sender` 四級順序、`kind` 有也忽略。

## 已知限制

- 只支援 Linux（`/proc` 的 `started_at_ticks`）。各格要在同一個檔案系統（rename 才原子）。
- 一個信箱預設一個處理者（N-16）：兩個處理者搶，rename 認領不會重複，但 `cur/` 的殘骸分不出是誰的。
- 寄到一半死掉的殘骸留在 `tmp/`，aos-post 不清（收屍歸寄信人的上一層，決定 23）。
- 序號滿 12 位之後不管（N-18：最小實作預設不出現）。
