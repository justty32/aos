# Looking at yourself: self_state

Tool `self_state` is `aos-agent ctl state` aimed at you. It only reads; it changes nothing. It is not put into your prompt by itself: call it when you want to know.

- overview, one line per part: `{}`
- some parts in detail: `{"parts": ["history", "mailbox"]}`
- every part in detail: `{"parts": ["all"]}`
- one JSON object instead of text: add `"json": true`

The eleven parts: `who` (name, definition, workspace, stack; `parent` = the stack of who asked to add you; `notify_box` = where to report (`subagent add` sets it to the parent's `<stack>/mailbox`; null = answer the `reply_to` of the letter that gave you the work); both are what the requester wrote at add time, not proof of who started you; null when not written), `state` (phase, letters in your queue, last answer), `tools`, `llm` (brain settings), `system` (where your system text comes from, its size and first line), `hooks`, `history` (how many messages, how big, the last few), `mailbox` (letters waiting), `subagents` (agents you started with `subagent`, and your quota), `resources` (limits, memory and cpu time in use), `time` (now, how long you have been up).

It gives facts and numbers only, no advice. A part that cannot be read says `not available` and why; the other parts still show.

To change yourself use `self_tools`, `self_llm`, `self_history`, `self_hook`; to stop yourself use `self_ctl` (see `aos/me.json#/self_ctl`).
