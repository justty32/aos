這份教你用最底層的 `aos-post` 建信箱、丟信、取信，以及直接往活著的 eca-claude agent 的 queue 丟一封、看它回答（試驗 04，11-18 在公司 WSL 用 haiku 實跑過）。

← [目錄](README.md)

使用者原話：「4.使用aos-post往信箱丟信。」

## 結論

- `aos-post` 是 aos 最底層的收發室（C++）。一個「信箱」就是有 `tmp/ new/ cur/` 三個子夾的資料夾，一封信就是 `new/` 裡的一個小夾，裡面放 `letter.json`。
- 丟信只要一行：`echo '<JSON>' | aos-post send <信箱>`。它會印出信件名稱。內容一定要是 JSON，格式它不管。
- 往 agent 丟：信箱是 `~/aos-home/.stack/procs/ann/queue`，內容寫成 `{"role":"user","content":"…"}`，agent 就會答。回答寫在它的 `history.jsonl`，用 `aos-agent listen --letter <信件名稱>` 拿。
- **`aos-agent say` 底下就是它**：`say` 等於「沒有 queue 就先 `aos-post init`」，再把文字包成 `{"role":"user","content":…}`（對 eca 另外加寄件人 `name`），最後 `aos-post send --ordered`。另外它還會檢查對象在不在表上、沒在跑時提醒你。
- 內容格式不對（JSON 但不是一則訊息）：aos-post 照收，agent 那邊丟掉，`listen` 會報 `LetterDropped`。

## 第一部分：自己建一個信箱玩

下面在任何一個空資料夾打都可以（先 `source env.sh`）。

**1. 建信箱**

```sh
aos-post init box && ls box
```

會看到 `cur  new  tmp`。

**2. 丟一封**

```sh
echo '{"hello": "world"}' | aos-post send box
```

會印信件名稱，例如 `01794989202043795212.1876035.2828837`。這串是「UTC 奈秒 20 位．寄信行程的 pid．那個行程起來的時刻」（`post.hpp` 檔頭的說明），所以照名字排序就是寄出的先後。

**3. 信落在哪**

```sh
find box -type f
```

會看到 `box/new/01794989202043795212.1876035.2828837/letter.json`。打開長這樣：

```json
{
  "sender": "/home/你/現在的資料夾",
  "sent_at": "2026-11-18T08:06:27.228+00:00",
  "body": {"hello": "world"}
}
```

`sender` 填的是 `$AOS_STACK`，沒設就填你現在所在的資料夾。我用 `AOS_STACK=/x/y aos-post send box` 試過，那封的 `sender` 就變成 `/x/y`。

**4. 有序號、指定回信信箱、自己取名**

```sh
aos-post init replybox && echo '{"n": 2}' | aos-post send --ordered --reply-to $PWD/replybox box my-name
```

會印 `000000000001.my-name`。

- `--ordered` 會在前面加 12 位序號。序號記在信箱的 `order.json`，寄的時候要拿 `order.lock/` 這把鎖，見 [05](05-aos-lock鎖信箱.md)。
- 信封多一格 `"reply_to": "../replybox"`，用的是相對路徑，從信箱算起。
- `--reply-to` 指的夾要先存在，不然會看到 `aos-post: error: MailboxMissing mailbox not found: …/replybox`。
- 自己取的名字撞名：再寄一次 `send box same` 會看到 `LetterExists new/ already has a letter with this name: …/box/new/same`。

**5. 取信、看信、收掉**

```sh
L=$(aos-post take box) && aos-post see box $L && aos-post done box $L
```

- `take`：把最前面那封從 `new/` 移到 `cur/`，印出它的名字。
- `see`：把信封印成一行 JSON。
- `done`：把它收掉，`cur/` 就空了。
- 排序是有序號的在前、照序號；沒序號的在後、照名字。
- 沒信可取時，`take` 什麼都不印、退出碼 10。`take-all` 一次取全部。`regret` 收回一封還沒被取的。

## 第二部分：往活著的 agent 丟一封

前提：照 [README 的「共同準備」](README.md#共同準備)起好樹、`ann` 是 running。在 `~/aos-home` 打。

```sh
L=$(echo '{"role":"user","content":"Reply with exactly: posted-ok"}' | aos-post send --ordered .stack/procs/ann/queue) && echo $L && aos-agent -t ann listen --letter $L --timeout-s 120
```

會看到兩行：

```
000000000004.01794989214046205592.1876219.2830037
posted-ok
```

`tail -2 .stack/procs/ann/history.jsonl` 看得到兩行：user 那行帶著 `"aos": {"letter": "<你那封的名字>"}`，assistant 那行帶著 `"answer_to": [<同一個名字>]`。`listen --letter` 就是靠這個對上是哪一封的回答。

不加 `--ordered` 也收得到，回 `unordered-ok`。差別只在排隊順序：沒序號的排在有序號的後面。

## 跟 `aos-agent say` 比

| | `aos-post send` | `aos-agent say` |
|---|---|---|
| 對誰 | 任何信箱夾（路徑） | 表上的名字（`-t ann`），自己查出它的 stack |
| 內容 | 你給的 JSON，原樣放進 `body` | 你打的字，包成 `{"role":"user","content":…}`；對 eca 再加 `"name"`（寄件人） |
| 信箱沒建 | `MailboxMissing … run aos-post init first` | 自己先 `aos-post init` |
| 序號 | 要自己加 `--ordered` | 一律 `--ordered` |
| 對象沒在跑或暫停 | 不知道、不提醒 | stderr 印一行提醒，例如 `nothing is running ann now` |

`say` 的程式在 `py/aos/apps/agent/say.py`，真正寄信的那段在 `py/aos/ws.py` 的 `put`。另一支 `aos-mailbox` 寄的是另一個夾（agent 的 `mailbox/`，不是 `queue/`），見 [07](07-aos-mailbox寄信收信.md)。

## 錯誤訊息（原樣）

| 你做了什麼 | 看到 |
|---|---|
| 信箱夾不存在 | `aos-post: error: MailboxMissing mailbox not found: nobox` |
| 只是普通資料夾、沒 init | `aos-post: error: MailboxMissing mailbox not set up (missing …/plain/tmp); run aos-post init first` |
| stdin 不是 JSON | `aos-post: error: InputBad stdin is not JSON` |
| 是 JSON 但不是物件，例如 `[1,2]` | **照收**，印出信件名稱 |
| 往 agent 的 queue 丟 `{"hello":1}` | aos-post 照收；`listen --letter` 報 `aos-agent: error: LetterDropped … will not be answered: ann dropped it (bad: it was not a valid message); say it again for a new answer` |

## 發現的問題

1. 往 agent 的 queue 丟格式不對的信，aos-post 不會擋，要等 agent 丟掉之後，`listen` 才知道。這是分層的設計（aos-post 不管內容），但人直接用 aos-post 時容易踩到。
2. `--reply-to` 的信箱要先存在，可是 `aos-post send --help` 沒寫這件事。
