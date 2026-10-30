# aos-post

`aos-post - 投遞：把一封信寄進信箱、處理者一封封認領`（NAME，C-54 R1）

**一句話：`aos-post 子命令 [旗標...] 信箱 [信號]`——NORMS [N-16](../../docs/NORMS/05-基礎設施-窗.md)（10-29 改口＋補）的標準投遞：寄信人 `send` 把一封信放進信箱的 `new/`，處理者 `claim`／`claim-all` 一封封拿進 `cur/`、`check` 讀信、`finish` 收掉（要回信就照信裡的 `reply_to` 投一封回去），還沒被拿走的寄信人可以 `withdraw` 撤回。**
一個 lib（`lib/libaos-post.a`，公開標頭 `include/aos/post.hpp`，aos-daemon 的信箱模式要連）加一支薄命令列（`bin/aos-post`）。連 aos-util、aos-lock（有順序的投遞）。全家慣例見 [impls/README.md](../README.md)；設計見 [thinking 10-29 medium-plan § 二](../../thinking/2026-10-29-medium-plan.md)。

像公司的收發室：寄件人在後面的桌上（`tmp/`）把信封好，封好才放進待收籃（`new/`）；收件人把信從籃子拿到自己桌上（`cur/`）就算簽收，簽收了寄件人就抽不回來；辦完撕掉，或歸檔（`done/`）。

```sh
aos-post init box                                   # 建 box/tmp new cur
echo '{"loops_added": {"bob": "../agent-bob"}}' | aos-post send box      # 印信號
aos-post claim-all box                              # 一行一個信號（照名字排序）；沒有退 10
aos-post check box 信號                             # 好信印 letter.json；壞信退 1
aos-post finish box 信號                            # 收掉（--keep 進 done/）
```

## 用法

旗標寫在位置參數前面（aos-util 的 `parse_cli`，同全家）。結束碼照 N-43：0 成功、10 沒東西、1 錯。

| 子命令 | 做什麼 |
|---|---|
| `init 信箱` | 建信箱與 `tmp/`、`new/`、`cur/`（上層沒有一起建；已經有＝沒事）。`done/` 不建（選用，`finish --keep` 時才建） |
| `send [--ordered] [--reply-to 信箱] [--in-reply-to 信號] 信箱 < body.json` | 寄一封，stdout 印信號（`--ordered`＝`new/` 裡的名字，帶序號）。stdin 一份 JSON＝`body`（任何 JSON 值；空的＝`{}`） |
| `claim 信箱` | `new/` 照名字排序，認領第一個 rename 得進 `cur/` 的，印它的信號；沒有退 10 |
| `claim-all 信箱` | 認領 `new/` 裡全部，一行一個（照名字排序）；沒有退 10 |
| `check 信箱 信號` | 讀 `cur/<信號>/letter.json`：好信 stdout 印一行（整份）；壞信退 1、`LetterBad 原因` |
| `finish [--keep] [--reply] 信箱 信號 [< body.json]` | 處理完：預設 rename 回 `tmp/` 再刪；`--keep`＝rename 進 `done/`。壞信一律丟掉（不管 `--keep`、不回信）。`--reply`＝stdin 一份 JSON 當 body，照那封的 `reply_to` 投一封回信（`in_reply_to`＝原信號），stdout 印回信的信號；那封沒寫 `reply_to`＝不回、不印 |
| `withdraw 信箱 信號` | 撤回：rename `new/<信號>` 回 `tmp/` 再刪；已被認領（或本來就沒有）退 1 `WithdrawFailed` |

- **信箱**：拿得到＝信箱與 `tmp/`、`new/`、`cur/` 都是資料夾，少一個＝`MailboxMissing`（`init` 以外的子命令都不替人建）。位置由擁有者定（N-16）。
- **信號**：`<UTC 奈秒 20 位>.<pid>.<started_at_ticks>`（同 aos-llm-kernel 的產生法；`sent_at` 取自同一刻）。命令列給的信號要是單純的名字（不空、不含 `/`、不以 `.` 開頭），不是＝`ArgumentsBad`。
- **`letter.json`**：`{"kind": "letter", "sender", "sent_at", "reply_to"?, "in_reply_to"?, "body"}`。`sender`＝`$AOS_WS`（轉絕對），沒設或空＝`$HOME`（轉絕對；`HOME` 也沒有＝`/`），人也一樣。`sent_at`＝ISO 8601 UTC 到毫秒（同全家的 `recorded_at`，`…+00:00`）。`reply_to`＝`--reply-to` 給的路徑轉絕對（不驗在不在）。
- **壞信**（`check` 退 1、`finish` 丟掉）：`letter.json` 讀不了或不是 JSON 物件、`kind` 不是 `"letter"`、`sender`／`sent_at` 不是字串、沒有 `body`、`reply_to`／`in_reply_to` 不是字串。`body` 的形狀由收信的程式自己驗。不通知寄信人（決定 27）；記 `letter_warning` 是處理者的事（拿 `check` 的原因）。
- **回信寄不出去**（`reply_to` 不是信箱等）：退 1，原信**留在 `cur/`**，可以再 `finish` 一次。
- **有順序的投遞**（`send --ordered`，N-16、[medium-plan § 三](../../thinking/2026-10-29-medium-plan.md)）：信箱多兩樣——`order.lock/`（[aos-lock](../aos-lock/README.md) 的鎖，持有者＝這個 aos-post 行程）與 `order.json`（`{"counter_letters": N}`，沒有＝0）。步驟：信照常先在 `tmp/<信號>` 寫好 → 拿 `order.lock/`（拿不到每 20 毫秒再試、**一直等**；持有者死了照 aos-lock 收屍）→ 讀 N → `order.json` 寫 N+1（暫存改名）→ rename 成 `new/<N+1 零填 12 位>.<信號>` → 放鎖。鎖握到 rename 完，所以到 `new/` 的順序＝取號順序，處理者照名字排序（`claim`／`claim-all` 本來就是）就是有順序的。`order.json` 讀不懂＝`OrderBad`（放鎖、信丟掉）。
  - **會缺號、不會重號**：寄信人死在「寫完 N+1、還沒 rename」之間，那個號就缺了（信留在 `tmp/`）。plan 原本是先 rename 再寫 N+1，死在中間時下一個人會拿到同一個號，所以兩步對調。
  - 一個有序信箱只收 `--ordered` 的信：混著寄，沒序號的信號（20 位數字開頭）跟帶序號的（12 位）照名字排會亂。
- `tmp/` 處理者永遠不看；`new/`、`cur/` 裡 `.` 開頭的名字不算信（N-05）。不是資料夾的東西出現在 `new/` 也認領得到，`check` 算壞信、`finish` 丟掉。

## 元素

| 檔 | 做什麼 |
|---|---|
| `include/aos/post.hpp` | 公開介面（函式清單與說明在檔頭）；自己的代號 |
| `src/mailbox/mailbox.cpp` | 信箱路徑、`init`、`open`、`check_id`；共用小工具（宣告在 `src/common/common.hpp`） |
| `src/send/send.cpp` | `sender`、信號與 `sent_at`（同一刻）、`send`；`--ordered` 的 `post_ordered` |
| `src/take/take.cpp` | `claim`、`claim_all`、`check`（驗信封）、`reply`、`finish`、`withdraw` |
| `src/main.cpp` | 命令列：子命令表、旗標、印結果、錯誤一行 |

## 錯誤代號

stderr 一行 **`aos-post: 代號 原因`**、退 1。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`、`FlagUnknown`（共用） | 子命令沒給、位置參數個數不對、信號不是單純的名字、旗標缺值、開關帶值、不認得的旗標 |
| `CommandUnknown`（同 aos-json） | 不認得的子命令 |
| `InputBad`、`InputExtra`（共用） | `send`、`finish --reply` 的 stdin 解不出 JSON、有好幾份 |
| `MailboxMissing`（同 aos-gate） | 信箱或 `tmp/`、`new/`、`cur/` 不是資料夾；`finish --reply` 時 `reply_to` 指的不是信箱 |
| `LetterMissing`（同 aos-gate） | `check`、`finish`：信不在 `cur/` |
| `LetterBad` | `check`：壞信 |
| `WithdrawFailed` | `withdraw`：信不在 `new/` |
| `OrderBad` | `send --ordered`：`order.json` 在但不是 `{"counter_letters": 非負整數}` |
| `MkdirFailed`、`WriteFailed`、`Internal`（共用） | 建不了資料夾；寫不了、改名不了；照理不會發生的 |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

依賴：aos-lock、aos-util（`add_subdirectory` 一起編）。`ctest` 跑 `test_cli`（`tests/test_cli.py`，unittest；各段涵蓋什麼寫在檔頭）：含 20 個寄信人並發 200 封不漏不重、`tmp/` 的半截信永遠不被認領、`--ordered` 50 個寄信人序號從 1 連續、持有者死了收屍繼續（缺號不重號）、亂 kill -9 寄信人不重號也不卡鎖。

## 已知限制

- 只支援 Linux（`/proc` 的 `started_at_ticks`）。四格要在同一個檔案系統（rename 才原子）。
- 一個信箱預設一個處理者（N-16）：兩個處理者搶，rename 認領不會重複，但 `cur/` 的殘骸分不出是誰的。
- 寄到一半死掉的殘骸留在 `tmp/`，aos-post 不清（收屍歸寄信人的上一層，決定 23）。
