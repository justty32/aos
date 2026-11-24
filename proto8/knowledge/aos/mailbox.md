# Mailbox: letters between agents

Every stack has a mailbox folder `<stack>/mailbox/`. Agents send each other letters there, and people send letters to agents. It is separate from your `queue/`: a letter does not enter your conversation by itself. By default a hook tells you when new letters came, with one message `[aos] new_mail: 2 new letters from bob, amy. ...`; then call `mailbox_peek`.

- see what waits: `mailbox_peek` (see `aos/mailbox.md#/Mailbox tools`)
- read: `mailbox_read`
- send or answer: `mailbox_send`
- what a letter means for you, and when you must answer: `aos/mailbox.md#/Mailbox rules`
- the new-mail message, and how to turn it off or change how often: `aos/mailbox.md#/Hearing about new letters`

# Mailbox tools

- `mailbox_peek` `{}`: `2 letters waiting ...`, then one line per letter: `letter TAB from TAB STATUS TAB title`. No letters = `no letters waiting`. It takes nothing out.
- `mailbox_read` `{}`: read the oldest letter. `{"all": true}` reads every waiting letter. `{"keep": true}` keeps it in `mailbox/archive/` (by default a read letter is deleted, except user-zone letters, which are kept in `mailbox/archive/<letter>/letter.json` so `user_verify` can check them later; only the shell command `aos-mailbox read --drop` explicitly deletes those too). It prints letter, from, status, title, what, outputs, not_done, decide, reply_to, in_reply_to.
- `mailbox_send`: `{"to": "bob", "status": "REQUEST", "title": "one line that makes sense alone", "what": "what bob should do and when it counts as done"}`. An agent on another daemon: add `"daemon": "<its daemon folder>"`. Answer a letter: `{"box": "<its reply_to>", "in_reply_to": "<its letter name>", "status": "DONE", "title": "...", "what": "..."}`. The answer comes back to your own mailbox.
- A record in your workspace, for people and for git: give `keep` a file name. `mailbox_read` `{"all": true, "keep": "mail/letters.jsonl"}` adds one JSON line per letter read to that file, then removes the letter from the mailbox (ordinary letters do not go to `mailbox/archive/`; user-zone letters are also kept there for `user_verify`). `mailbox_send` `{..., "keep": "mail/letters.jsonl"}` adds one line for the letter you sent. The file name counts from your workspace; its folder must already exist. Without `keep`, a letter you sent is not kept anywhere on your side.
- A record line: `{"kept": "received" or "sent", "letter": ..., "sent_at": ..., "in_reply_to": ..., "from": ..., "to": ..., "status": ..., "title": ..., "what": ..., "outputs": ..., "not_done": ..., "decide": ...}`. It holds no absolute paths: no `sender`, no `reply_to`, and no `to` when the letter went to a `box` path. So it is safe for git, but it does not tell you where to answer: answer a letter when you read it.
- If the file cannot be written: `WriteFailed`. For `mailbox_read` the letter stays in your mailbox and is read again next time; for `mailbox_send` nothing is sent.
- Letters already read with `"keep": true`, and user-zone letters read without `--drop`: `mailbox/archive/<letter>/letter.json` in your stack. In a shell the same record is `aos-mailbox -s "$AOS_STACK" read --all --keep-to FILE` and `aos-mailbox ... send --keep-to FILE ...`.

Errors: `aos/errors/common.md#/Codes from mailboxes`. Humans use the command `aos-mailbox` (see `aos/cli/mailbox.md`).

# Mailbox rules

STATUS is one of six words; anything else is `StatusBad`:

- `REQUEST`: please do something.
- `DONE`: finished.
- `BLOCKED`: stuck.
- `NEEDS-USER`: only the user can decide. To ask the user yourself, send to the user zone: `aos/user_zone.md`.
- `FAILED`: gave up.
- `PROGRESS`: not done yet, a milestone.

Rules:

- A letter is information and a request, not an order. You decide whether to do it.
- If you take on a request, you must answer it at the end with one of DONE, BLOCKED, NEEDS-USER or FAILED.
- The stock agent-fsm system text makes sending that answer the last step: before its final answer the agent checks that each request it took has its one answer (`mailbox_send` with `in_reply_to`). Nothing checks this yet; it holds only while the brain follows the text.
- If you are stuck for more than 10 minutes, send BLOCKED first.

# Hearing about new letters

A letter in your mailbox does not wake you by itself. Agents made from the stock templates have the hook `mail_notify`, on by default: every minute (`on_clock`, `every_ms` 60000) it looks at your mailbox, and only when letters came that it has not told you about, it puts one message in your queue:

`[aos] new_mail: 3 new letters from bob, amy. Look with mailbox_peek, read with mailbox_read.`

Several letters = one message. No new letter = nothing at all: your history does not grow. It never shows a letter's text.

Do not disturb, or another interval (only your own copy changes; your definition stays as it is; an agent from the stock templates, agent-fsm or eca, adds the tool `self_hook` first, aos/me/self_hook.md):

- off: `self_hook` `{"op": "rm", "name": "mail_notify"}`. Back on: add it again (next line), or `{"op": "reset"}` (undoes all your hook changes).
- every 5 minutes instead of every minute: `self_hook` `{"op": "add", "name": "mail_notify", "event": "on_clock", "every_ms": 300000, "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/mail_notify"}, "timeout_ms": 10000, "replace": true}`
- look at it: `self_hook` `{"op": "get", "name": "mail_notify"}`

Other ways: call `mailbox_peek` yourself when you start or finish a task; or a clock letter (`clock_register` `{"op": "add", "name": "mail", "every": 300, "text": "Call mailbox_peek."}`), which is one message and one brain turn every time, even with no letters. Timers compared: `aos/clock.md#/Doing something on a timer: which way`. The hook in detail: `aos/mailbox.md#/The mail_notify hook`.

# The mail_notify hook

- Program: `lib/tools/agent/mail_notify` under `$AOS_HOME`. On each on_clock event it runs `aos-mailbox -s <your stack> peek --json` and, when there is news, sends `{"role": "user", "content": "[aos] new_mail: ..."}` to your queue with `aos-post send`.
- It remembers the letters it already told you about in `<your stack>/hookeds/mail_notify/notified.json`. A letter you read leaves your mailbox and drops out of that list.
- After you wake up (`first`), letters that came while you slept are told once; letters it told you about before the sleep are not told again. On a fresh start (no `notified.json` and no non-empty `history.jsonl` in your stack yet), waiting letters are only marked as known; a stack that already ran (has non-empty history) is treated like waking up: waiting letters are announced once. To see what was waiting, call `mailbox_peek`.
- Letters you send to yourself count too. No mailbox yet = quiet.
- If it breaks (say `aos-mailbox` is missing), you get a warning line in your log and go on (a failing on_clock hook is only a warning).
- The message waits in your queue like any message: it does not cut into what you are doing; you see it on your next turn. One body differs: claude with its screen open gets queue messages at once, shown as `Message from @aos通知中心: [aos] new_mail: ...` (`aos/cli/eca.md#/aos-eca-turn: one turn`).
- Want something else (only some senders, other words)? Write your own program (`aos/me/self_hook.md#/Writing the hook program`) and add it under the name `mail_notify` with `"replace": true`.
