這份教你用 `aos-mailbox` 寄一封信給活著的 eca-claude agent、再把它的回信收回來（試驗 07，11-18 在公司 WSL 用 haiku 實跑過）。
← [目錄](README.md)

# 試驗 07：用 aos-mailbox 寄信給 agent，並收信

使用者原話：「7.使用aos-mailbox寄信給agent，並收信」

## 結論

- **`aos-mailbox` 是「我的信箱」**：四個子指令 `where`（印出我的信箱、沒有就建）、`peek`（看有哪些信、不拿走）、`read`（讀最舊一封、讀完收掉）、`send`（寄信）。
- **寄給 agent 只要三樣**：對象名字 `--to ann`、它在哪個 daemon `-d .stack`、信的 `--status`＋`--title`＋內文。回信位置不用填：自動寫成「寄件人 stack 底下的 `mailbox/`」。
- **人的信箱預設在 `~/.aos/stack/mailbox/`**（`-s` 可換）。不用先建：`send`、`where` 都會自動建。
- **agent 的信箱和 `aos-agent say` 投的 `queue/` 是兩個不同的夾**：`say` 投進 `queue/`，下一輪就直接是 agent 要回的話；信投進 `mailbox/`，agent 不會自己去看，要靠範本的 `mail_notify` hook 每分鐘巡一次，有新信才往 `queue/` 塞一句提醒。實測從寄出到 agent 動手約 50 秒。
- **回信不會自動送到你眼前**：要自己 `peek`／`read`（輪詢）。回信的 `in_reply_to` 就是你寄出那封的信名，靠它對上。
- 實測 haiku 收到 REQUEST 信，就算信裡沒叫它回信，也會自己用 `mailbox_send` 回 DONE；收到 PROGRESS 信（「不用回」）就只讀、不回。

## 一步一步

先做：`cd ~/aos-home && source env.sh`，樹已經 `aos-tree-start root` 起好、`ann` 已經掛上（照 [start-eca](../../../../templates/start-eca/README.md)）。

**1. 看自己的信箱在哪（順便建好）**

```sh
aos-mailbox where
```

會看到：一行絕對路徑，例如 `/home/你/.aos/stack/mailbox`。裡面有 `tmp/ new/ cur/` 三個夾。

**2. 寄一封 REQUEST 給 ann**

```sh
aos-mailbox send --to ann -d .stack --status REQUEST --title "Please tell me how many files are in agents/ann" "Count the files directly inside agents/ann and reply to me with mailbox_send, status DONE, the number in the title."
```

會看到：一行信名，例如 `01794988398219385329.1806987.2748454`。**記下來**，等一下靠它對回信。
信落在 `.stack/procs/ann/mailbox/new/<信名>/letter.json`，裡面 `reply_to` 指回你的信箱、`body.from` 是你的登入名（要換用 `--from 名字`）。

- `--status` 只收 `REQUEST DONE BLOCKED NEEDS-USER FAILED PROGRESS`。
- 內文要寫在所有旗標後面；從內文開始全部算文字。內文太長用 `-`，從 stdin 讀。
- 卡點：**不在樹的根目錄又沒給 `-d`**＝`StateMissing /tmp/.stack/procs_state.json not found (daemon not started yet, or procs_state is off)`。daemon 其實好好的，是你站錯資料夾。

**3. 等 agent 看到信（約 1 分鐘）**

```sh
aos-agent -d .stack listen -t ann --last 1
```

會看到：（約 50 秒後）

```
> [aos] new_mail: 1 new letter from guanyu. Look with mailbox_peek, read with mailbox_read.
I counted the files and sent the answer back to guanyu. ...
```

這一句提醒是 `mail_notify` 塞進 `queue/` 的。提醒只寫封數和寄件人、不帶內文。agent 用 `mailbox_read` 讀信，普通信讀完就從它的信箱刪掉。

**4. 看有沒有回信（不拿走）**

```sh
aos-mailbox peek
```

會看到：一行一封，用 Tab 分開：`信名  寄件人  狀態  標題`：

```
01794988463548193462.1816400.2754987	ann	DONE	11 files directly inside agents/ann
```

沒信就什麼都不印、退 0。要寫腳本等回信，就是反覆 `peek` 直到有輸出（沒有「等到有信」的子指令）。

**5. 讀回信**

```sh
aos-mailbox read
```

會看到：一行一個欄位：

```
letter: 01794988463548193462.1816400.2754987
from: ann
status: DONE
title: 11 files directly inside agents/ann
what: Counted the regular files directly inside agents/ann (subfolder screen/ excluded): 11. ...
outputs: none
reply_to: /home/…/.stack/procs/ann/mailbox
in_reply_to: 01794988398219385329.1806987.2748454
```

`in_reply_to` 等於第 2 步記下的信名，就是那封的回覆。讀完這封就刪了（`--keep` 改成留在 `mailbox/archive/`；`--all` 一次讀完；`-j` 印 JSON）。再 `read` 一次沒信＝什麼都不印、退 10。

**6. 要再回它一句**（照 `reply_to` 寄回去）

```sh
aos-mailbox send --box <上面的 reply_to> --in-reply-to <它的信名> --status DONE --title "thanks" "Got it."
```

## aos-post、aos-mailbox、aos-agent say／listen／ask 三者關係

讀程式確認：`aos-mailbox` 跟 `say` 兩邊底下都是叫 `aos-post` 命令列。丟信的細節另見 [04-aos-post丟信](04-aos-post丟信.md)。

| | aos-post（C++） | aos-mailbox（Python） | aos-agent say／listen／ask（Python） |
|---|---|---|---|
| 是什麼 | 最底層的收發室：任何 `tmp/ new/ cur/` 夾都能 `init`、`send`、`take`、`see`、`done`、`regret` | 包 aos-post：`init`、`send`、`take`、`see`、`done` 都叫它；`peek` 自己直接讀 `new/*/letter.json` | `say`＝`aos-post send --ordered` 進 `<stack>/queue/` |
| 投到哪 | 你給的任何信箱 | `<對方 stack>/mailbox/`（照 daemon 表上的名字找 stack，沒有信箱就替它建） | `<對方 stack>/queue/` |
| 信長怎樣 | 信封（`sender`、`sent_at`、`reply_to`、`in_reply_to`）＋任意 body | body 固定成 inbox 協議：`from to status title what outputs not_done decide`；寄件人＝我的 stack、`reply_to`＝我的信箱 | body＝`{"role":"user","content":…}`，對 eca 再加寄件人 `name` |
| agent 怎麼看到 | 不管 | 不會自己看到；靠 `mail_notify` hook 每分鐘巡、往 queue 塞提醒，agent 再用 `mailbox_peek`／`mailbox_read`（就是 aos-mailbox 的包裝） | 下一輪直接是它要回的話 |
| 回答在哪 | 不管 | 對方另寄一封信回你的 `mailbox/`，`in_reply_to` 對上 | 寫進對方 `history.jsonl`；`listen` 讀它，`ask`＝`say`＋`listen --letter 信名`（配到你那封） |

一句話：**要「問一句、等一句」用 `ask`；要留下一封有狀態、可以晚點回、雙方都能非同步看的信，用 `aos-mailbox`。**

## 寄錯、對方沒在跑會怎樣（實測原樣）

| 情況 | 指令結果 |
|---|---|
| 名字不在 daemon 表上（打錯字、還沒 `ctl add`） | `aos-mailbox: error: InstanceMissing nobody is not on the daemon table (only running, stuck, stopping, stopped, sleeping rows count; removed ones are gone, see aos-daemon-ctl ls)`，退 1、沒寄 |
| 狀態寫錯 | `aos-mailbox: error: StatusBad status must be one of REQUEST, DONE, BLOCKED, NEEDS-USER, FAILED, PROGRESS (got 'OK')` |
| `--box` 給的夾不存在 | `aos-mailbox: error: MailboxMissing mailbox not found: /tmp/nope` |
| 對方 `ctl stop` 停著 | **寄成功、退 0、不提醒**；信在它信箱裡等。`ctl start` 之後約 10 秒，`mail_notify` 補提醒一次，照樣回信 |
| 同樣情況用 `say` | 也寄成功，但會提醒：`aos-agent: warning: queued in …/queue/new/; nothing is running ann now; it is stopped on the daemon table (ann is stopped); start it: aos-agent ctl start --target ann` |

## 發現的問題（不修程式）

1. **寄給停著的 agent，`aos-mailbox send` 不提醒**；`say` 同樣情況會提醒「nothing is running」。人會以為對方馬上會看到。
2. **`StateMissing` 的原因句會誤導**：站錯資料夾、沒給 `-d` 時說 `daemon not started yet`，其實 daemon 好好的。
3. **回信沒有「等到有信」的子指令**：只能自己反覆 `peek`。`aos-agent listen` 有 `--timeout-s`，`aos-mailbox` 沒有對應。
4. **`--from` 預設只看 `$USER`**；`say` 的 `--from` 會先看 `$AOS_STACK` 落在哪一隻 agent。兩邊預設的寄件人規則不一樣。
5. 回信的 `to:` 印成你信箱的絕對路徑，不是名字：agent 用 `--box` 回信，`to` 就記成路徑。
6. agent 先寄出回信、才結束那一輪。剛 `peek` 到回信就馬上 `listen --last 1`，看到的可能還是上一輪。
