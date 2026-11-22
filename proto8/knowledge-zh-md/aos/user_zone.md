# `knowledge/aos/user_zone.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/user_zone.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 使用者區：怎麼問使用者

使用者（那個人）也是可以收信的對象。他的區是 `~/.aos/user/`（每個 Linux 帳號、每台機器一個；它是使用者自己的 stack）。它的 `mailbox/` 是普通的 aos 信箱。只有使用者能做的事，就寄一封信到那裡；回覆會以一封普通的信回到你自己的信箱（帶 `in_reply_to`），`mail_notify` 照常叫醒你。

- 誰該寄、寄什麼：`aos/user_zone.json#/what`
- 怎麼寄（用 shell，或只用 aos 工具）：`aos/user_zone.json#/send`
- 回覆長什麼樣、可以信到什麼程度：`aos/user_zone.json#/answer`
- 門口（區上的告示，寄之前先讀）：`~/.aos/user/door.json`，或用 `aos-user door` 印出來

---

**`#/what`**

# 寄什麼給使用者

每封信都有一個 `kind`：

- `decide`：只有使用者能決定的問題。每個問題都有選項（`key` 1-8 個英文字母／數字、`label`、可有可無的 `consequence`）、一個屬於那些 key 之一的 `recommend`，以及 `eli5`（兩句白話）。一封信最多 7 個問題。
  一個問題：`{"id": "q1", "question": "one line", "eli5": "two plain sentences", "options": [{"key": "a", "label": "do it", "consequence": "two more days"}, {"key": "b", "label": "skip"}], "recommend": "a", "why": "optional", "details": "optional", "source_path": "optional"}`。
- `verify`：請在真的機器上試試看。說要做什麼（`what`）以及怎樣算做完（`done_when`）。
- `trial`：請玩玩看，告訴我感覺如何。
- `chore`：只有使用者能做的事（登入、插上東西）。需要 `done_when`。
- `fyi`：讓你知道一下。使用者會把它收起來；通常不會有回覆。它的 `status` 必須是 `DONE`、`FAILED` 或 `BLOCKED`（沒給 = `DONE`；其他任何值：`SchemaBad fyi status must be one of DONE, FAILED, BLOCKED`）。其他每一種 kind 的 status 都是 `NEEDS-USER`。

不要寄：進度（用看板）、agent 之間的請求、你自己查得到的問題。

可有可無的鍵：`urgent`（只有在沒回覆就什麼都卡住時才設 true）、`deadline`（`2026-11-15` = 那天結束之前，或當地時間 `2026-11-15T18:00`）、`default_if_silent`（到期限還沒回覆時你會怎麼做；需要 `deadline`；不能跟 `risk: irreversible` 一起用；使用者之後可以撤銷）、`risk`（`normal`，或 push、刪除、往外送時用 `irreversible`）、`dedupe_key`（兩個 agent 問同一個問題只顯示一次，兩邊都拿到回覆）、`origin`（你轉傳問題時，最初是誰問的；原樣貼上）。

---

**`#/send`**

# 怎麼寄

用 shell（claude、codex 身體）：

```sh
aos-user send --kind decide --title "one line that makes sense alone" < letter.json
```

`letter.json` 裝的是 `what`（一兩句：你需要什麼；decide 可以不給）和 `#/what` 裡的那些鍵（decide 是 `questions`）。這個工具會填上 `zone`、`from`（你的 stack 名字）、`to`、`status`、`host`，以及回信地址（`$AOS_STACK/mailbox`，或 `--reply-to MAILBOX`）。它會先拿 `~/.aos/user/schema/letter.json` 檢查這封信；壞掉的信不會寄出（`SchemaBad`，附上原因）。它會印出信的名字。

`source $AOS_HOME/env.sh` 之後 aos-user 就在 PATH 上（它放在 `$AOS_HOME/frontend/aos-user/`）。

只用 aos 工具（agent-fsm 身體）：有工具 `user_send` 的話就用它（沒有就請人加上），以你的身分：`{"kind": "decide", "title": "...", "questions": [...]}`（鍵跟上面一樣，檢查方式也一樣；回覆會到你的信箱）。沒有 `user_send` 時，舊的方法還是能用。`mailbox_send` `{"box": "/home/<you>/.aos/user/mailbox", "status": "NEEDS-USER", "title": "...", "what": "...", "decide": "the question, the options, your recommendation"}`。使用者看到它會標成舊格式，用文字回覆。

有裝區的每分鐘檢查（`aos-user tick`，計時器每台自己決定裝不裝）的話，區會在一分鐘內檢查每封新信。違反門口規則的信，或你在一小時內寄超過 10 封信，會被移到區的 `rejected/`，並回到你的信箱：status `FAILED`、title `Returned: ...`、`in_reply_to` = 你的信、`reason` = 哪裡不對。使用者看不到它。把信改好再寄一次；不要原封不動再寄，而且把問題合成一封信（最多 7 個），不要寄很多封。

絕不要用 `aos-mailbox read` 或 `mailbox_read` 讀區：它們會刪信。除了寄信到它的 `mailbox/` 以外，絕不要在區裡寫任何東西。eca 身體可能有 hook `user_zone_guard`（`$AOS_HOME` 底下的 `lib/tools/agent/user_zone_guard`，事件 `before_tool`）：它會擋下會碰到 `mailbox/` 以外區域的 aos 工具呼叫。

---

**`#/answer`**

# 回覆

使用者用 `aos-user answer` / `reply` / `ok` 或在區的網頁上（只限 127.0.0.1）回覆。一封信會一直等著直到被回覆（「回覆了 = 不見了」）。

回覆是你信箱裡的一封信，`in_reply_to` = 你那封信的名字，status `DONE`，一般的欄位（`from` = `user`、`title` = `Re: ...`、`what` = 用文字寫的回覆），另外還有：`answers`（`[{id, answer, differs}]`；`differs` = 不是推薦的那個；`answer` 可能是 `other` = 見 `note`）、`answer_line`（同樣內容的 decide 頁格式，`q1:a、q2:c*（備註：...）`）、`note`、`text`、`via`（`cli` 或 `web`）、`answered_at`、`host`、`letter_hash`、`reply_id`、`auth`。

對 `verify` 和 `chore` 信，像「ok」這樣的回覆通常只表示使用者同意去做，不表示做完了。等到有回覆說做完了，才算做完；如果有唯讀的檢查能確認，也跑一下。

檢查它：`aos-user verify <the answer's letter folder>` 會拿它跟區自己的副本（`done/`）和紀錄比對。`ok:` = 它是從區寄出的。只用 aos 工具時：工具 `user_verify` `{"letter": "<the name from mailbox_peek>"}` 做同樣的檢查，效力也一樣；`mailbox_read` 之後也能用，因為回覆會保留在 `mailbox/archive/<letter>/letter.json`（找的順序：new/、cur/、archive/）。被退回的信（status `FAILED`、`returned`）不是回覆，不會通過。

可以信到什麼程度（使用者在 11-13 決定的）：從區來、檢查過的回覆，算是使用者自己的話，push 和刪除也一樣（AGENTS.md 第 2 條）。但所有 agent 都以同一個 Linux 使用者執行：有 shell 的 agent 也可能偽造區的副本和紀錄。這個檢查擋得住轉述（「使用者跟我說可以」）和被丟進你信箱的假信；擋不住存心兩邊都偽造的 agent。不要去試。
