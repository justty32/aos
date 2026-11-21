# `knowledge/aos/mailbox.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/mailbox.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 信箱：agent 之間的信

每個 stack 都有一個信箱資料夾 `<stack>/mailbox/`。agent 在那裡互相寄信，人也在那裡寄信給 agent。它跟你的 `queue/` 是分開的：信不會自己跑進你的對話。預設有一個 hook 會在新信來時告訴你，用一則訊息 `[aos] new_mail: 2 new letters from bob, amy. ...`；然後呼叫 `mailbox_peek`。

- 看有什麼在等：`mailbox_peek`（見 `aos/mailbox.json#/tools`）
- 讀：`mailbox_read`
- 寄信或回覆：`mailbox_send`
- 一封信對你代表什麼，以及什麼時候你一定要回覆：`aos/mailbox.json#/rules`
- 新信訊息，以及怎麼關掉它或改它多久提醒一次：`aos/mailbox.json#/check`

---

**`#/tools`**

# 信箱工具

- `mailbox_peek` `{}`：`2 letters waiting ...`，然後每封信一行：`letter TAB from TAB STATUS TAB title`。沒有信＝`no letters waiting`。它什麼都不拿走。
- `mailbox_read` `{}`：讀最舊的那封信。`{"all": true}` 讀所有在等的信。`{"keep": true}` 把它留在 `mailbox/archive/`（預設讀過的信會被刪掉，但使用者區的信例外，它們會留在 `mailbox/archive/<letter>/letter.json`，讓 `user_verify` 之後能檢查；只有 shell 指令 `aos-mailbox read --drop` 會明確地連那些也刪掉）。它印出 letter、from、status、title、what、outputs、not_done、decide、reply_to、in_reply_to。
- `mailbox_send`：`{"to": "bob", "status": "REQUEST", "title": "one line that makes sense alone", "what": "what bob should do and when it counts as done"}`。另一個 daemon 上的 agent：加上 `"daemon": "<its daemon folder>"`。回覆一封信：`{"box": "<its reply_to>", "in_reply_to": "<its letter name>", "status": "DONE", "title": "...", "what": "..."}`。回覆會回到你自己的信箱。
- 在你的工作區留一份紀錄，給人看、也給 git：給 `keep` 一個檔名。`mailbox_read` `{"all": true, "keep": "mail/letters.jsonl"}` 會把讀到的每封信各加一行 JSON 到那個檔案，然後把信從信箱移掉（一般的信不會進 `mailbox/archive/`；使用者區的信也會留在那裡給 `user_verify`）。`mailbox_send` `{..., "keep": "mail/letters.jsonl"}` 會為你寄出的信加一行。檔名從你的工作區算起；它的資料夾必須已經存在。沒有 `keep` 的話，你寄出的信在你這邊什麼地方都不會留。
- 一行紀錄：`{"kept": "received" or "sent", "letter": ..., "sent_at": ..., "in_reply_to": ..., "from": ..., "to": ..., "status": ..., "title": ..., "what": ..., "outputs": ..., "not_done": ..., "decide": ...}`。裡面沒有絕對路徑：沒有 `sender`、沒有 `reply_to`，信是寄到 `box` 路徑時也沒有 `to`。所以放進 git 是安全的，但它不會告訴你要回到哪裡：讀信的時候就回覆。
- 檔案寫不進去時：`WriteFailed`。對 `mailbox_read` 來說，信會留在你的信箱，下次再讀一次；對 `mailbox_send` 來說，什麼都不會寄出。
- 用 `"keep": true` 讀過的信，以及沒加 `--drop` 讀過的使用者區的信：在你 stack 裡的 `mailbox/archive/<letter>/letter.json`。在 shell 裡，同樣的紀錄是 `aos-mailbox -s "$AOS_STACK" read --all --keep-to FILE` 和 `aos-mailbox ... send --keep-to FILE ...`。

錯誤：`aos/errors/common.json#/mail`。人用的是指令 `aos-mailbox`（見 `aos/cli/mailbox.json`）。

---

**`#/rules`**

# 信箱規則

STATUS 是六個字之一；其他的都是 `StatusBad`：

- `REQUEST`：請做某件事。
- `DONE`：做完了。
- `BLOCKED`：卡住了。
- `NEEDS-USER`：只有使用者能決定。要自己問使用者，就寄到使用者區：`aos/user_zone.json`。
- `FAILED`：放棄了。
- `PROGRESS`：還沒做完，一個里程碑。

規則：

- 一封信是資訊和請求，不是命令。要不要做由你決定。
- 如果你接下一個請求，最後一定要用 DONE、BLOCKED、NEEDS-USER 或 FAILED 其中之一回覆它。
- 如果你卡住超過 10 分鐘，先寄 BLOCKED。

---

**`#/check`**

# 得知有新信

信箱裡有信，並不會自己把你叫醒。用現成範本做出來的 agent 有 hook `mail_notify`，預設開著：每分鐘（`on_clock`、`every_ms` 60000）它看一次你的信箱，只有在來了它還沒告訴過你的信時，才在你的佇列放一則訊息：

`[aos] new_mail: 3 new letters from bob, amy. Look with mailbox_peek, read with mailbox_read.`

好幾封信＝一則訊息。沒有新信＝什麼都沒有：你的對話歷史不會變長。它從不顯示信的內文。

勿擾，或換別的間隔（只改你自己的那份複本；你的定義保持原樣；現成的 agent-fsm 要先加上工具 `self_hook`，aos/me/self_hook.json）：

- 關掉：`self_hook` `{"op": "rm", "name": "mail_notify"}`。再打開：再加一次（下一行），或 `{"op": "reset"}`（撤銷你所有的 hook 修改）。
- 改成每 5 分鐘而不是每分鐘：`self_hook` `{"op": "add", "name": "mail_notify", "event": "on_clock", "every_ms": 300000, "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/mail_notify"}, "timeout_ms": 10000, "replace": true}`
- 看看它：`self_hook` `{"op": "get", "name": "mail_notify"}`

其他做法：在你開始或做完一件工作時自己呼叫 `mailbox_peek`；或用時鐘信（`clock_register` `{"op": "add", "name": "mail", "every": 300, "text": "Call mailbox_peek."}`），它每次都是一則訊息加一輪腦，就算沒有信也一樣。計時器的比較：`aos/clock.json#/choose`。這個 hook 的細節：`aos/mailbox.json#/check_hook`。

---

**`#/check_hook`**

# mail_notify 這個 hook

- 程式：`$AOS_HOME` 底下的 `lib/tools/agent/mail_notify`。每次 on_clock 事件，它跑 `aos-mailbox -s <your stack> peek --json`，有新消息時，就用 `aos-post send` 把 `{"role": "user", "content": "[aos] new_mail: ..."}` 送進你的佇列。
- 它把已經告訴過你的信記在 `<your stack>/hookeds/mail_notify/notified.json`。你讀過的信會離開你的信箱，也會從那份清單掉出去。
- 你醒來之後（`first`），你睡著時來的信會告訴你一次；睡著之前已經告訴過你的信不會再說。全新啟動時（你的 stack 裡還沒有 `notified.json`，也沒有非空的 `history.jsonl`），在等的信只會被標成已知；已經跑過的 stack（有非空的對話歷史）會被當成醒來處理：在等的信會宣告一次。要看有什麼在等，呼叫 `mailbox_peek`。
- 你寄給自己的信也算。還沒有信箱＝安靜。
- 如果它壞了（例如找不到 `aos-mailbox`），你的記錄檔會多一行警告，然後照常繼續（on_clock hook 失敗只是警告）。
- 這則訊息跟任何訊息一樣在你的佇列裡等：它不會打斷你正在做的事；你在下一輪會看到它。有一種身體不一樣：畫面開著的 claude 會立刻收到佇列訊息，顯示成 `Message from @aos通知中心: [aos] new_mail: ...`（`aos/cli/eca.json#/turn`）。
- 想要別的（只看某些寄件人、換別的字）？寫你自己的程式（`aos/me/self_hook.json#/handler`），用 `mail_notify` 這個名字、加上 `"replace": true` 加進去。
