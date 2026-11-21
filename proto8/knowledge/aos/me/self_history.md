# Changing your own conversation history

Tool `self_history` is `aos-agent history` aimed at you. It lists, deletes, summarizes or replaces messages in your own conversation. Changes work from your next turn.

Each message has a line number from 1. One op per call (the JSON is the tool's arguments):

- list: `{"op": "ls"}` (the last 20 messages, each cut at 200 characters). Add `"all": true` for every message, `"long": true` for full text, `"range": "5-"` for some lines, `"json": true` for JSON
- delete lines 3 to 4: `{"op": "rm", "range": "3-4"}`
- replace lines 1 to 6 with one message you write: `{"op": "summarize", "range": "1-6", "text": "User said their favorite color is blue."}` (the new message has role `user` unless you give `"role"`; it starts with `[aos] summary: lines 1-6, 6 messages.`)
- replace line 2 with a whole new message: `{"op": "set", "line": 2, "message": {"role": "user", "content": "..."}}`

A range is `"N"`, `"A-B"`, `"A-"` (A to the end) or `"-K"` (the last K, e.g. `"-3"`).

Rules and errors: `aos/me/self_history.md#/self_history: rules and errors`.

# self_history: rules and errors

- Use `ls` first. Its last line tells you which lines are locked.
- The step in progress is locked: the message that called `self_history` and everything after it. Touching a locked line is `RangeBad`.
- Nothing is lost by default: removed or replaced messages move to `history_removed.jsonl` in your stack. `rm`, `summarize` and `set` accept `"keep": "FILE"` (put the originals there instead) or `"no_keep": true` (do not keep them).
- Some messages have an `aos` key (`{"letter": ...}` on a letter, `{"answer_to": [...]}` on a final answer): it lets whoever asked find the answer to their letter. With `set`, copy the old `aos` key into the new message. A removed or replaced answer is still found in `history_removed.jsonl`, but not with `keep` or `no_keep`.
- If your body is an outside CLI (eca, for example claude), a change makes your next turn start a new conversation that carries the changed record over.
- `DaemonMissing`, `DaemonFailed`, `InstanceMissing`: the feature is unavailable for now; say so, and try at most once more later (`aos/errors/common.md`).
- `MessageBad`: `message` is not one JSON object. `HistoryMissing`, `HistoryBad` (your history cannot be read), `InterfaceBad` (your definition's `interfaces.json` is broken): a human must fix them; report.
