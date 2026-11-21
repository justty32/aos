# External coding agents (eca)

The two commands behind an eca agent (claude, codex or pi run by aos, as in `templates/eca-claude` and `templates/eca-pi`). People use `aos-agent` for both; run them by hand only to test.

Guarding the CLI's own tools (Bash ...) with the CLI's own hooks: `aos/cli/eca.md#/Guarding the CLI's own tools (claude)`.

The pi body (kind pi, one answer per message, no screen): `aos/cli/eca.md#/The pi body (kind pi)`.

# aos-eca-turn: one turn

```sh
AOS_STACK=/abs/st AOS_WS=/abs/ws aos-eca-turn /abs/def      # loop form
echo '{"prompt": "hello there"}' | AOS_STACK=/abs/st aos-eca-turn --one /abs/def
# FAKE: hello there        (tool form: prints the answer)
```

The body of an eca agent's loop: it hands every letter in `$AOS_STACK/queue` to the CLI as one prompt, waits for the answer and appends both to `history.jsonl`. DEF_DIR is an absolute folder (`AgentBad`) with `cli.json` (`CfgMissing`); flags go before or after it. `--on-empty stop` (default) exits 10 on an empty queue, `idle` 0. `--on-busy yield` (default) leaves the batch while someone is attached, `answer` waits. `--prompt FILE` (relative to DEF_DIR; `PromptMissing`) is the opening message when history and queue are empty. `--one` rejects `--on-empty`, `--prompt` (`ArgumentsBad`). With claude and an open screen, each letter arrives as a signed cross-session message on the CLI's own message socket (the screen shows `Message from @NAME`; the model is told its user did not type it). NAME is the sender from `aos-agent say` or `chat`; letters without one (new-letter notices, clock and goal letters, the opening record) are signed `aos通知中心`. The sender name is not in `history.jsonl`; the letter name is: each letter's row has `"aos": {"letter": NAME}`, and the answer has `"aos": {"answer_to": [NAME, ...]}` (every letter of the turn, also those that arrived while it answered). `$AOS_STACK/letters.json` lists the letters handed over and not answered yet (`pending`) and the ones dropped (`dropped`: a bad letter, one a `before_queue` hook blocked, or `failed`). They go in at once, even while someone is attached or a turn is running, and so do letters arriving while it answers. On this path `--on-busy` only decides what a held lock does. With the screen closed, a claude body whose `cli.json` has `"live_mail": true` keeps the CLI's stdin open (`--input-format stream-json --replay-user-messages`): letters that arrive while it answers are written in, one per line, and the model reads them at its next tool step (a long foreground command still delays them; the CLI is also given a short system line asking it to run long commands in the background, with `--system-prompt-snapshot off` so a resumed conversation sees it; it is a request, not a guarantee). stdin is closed once a result is in, every line was taken, no background task runs and no new letter waits. The answer is every result of the turn plus what the model said after taking a letter and before its next tool, joined with a blank line into one history entry. At most `live_mail_cap.letters` letters (default 5) are added, none after `live_mail_cap.seconds` (default 300); the rest wait for the next turn. The turn right after a cooldown adds none. A bad `live_mail_cap` is `CfgBad`. Off by default. If the socket is unknown or unreachable, or no receipt comes within 30 s, aos types into the screen as before (a warning on stderr; after a missing receipt, for that screen until its next session start: reopen, /clear, /compact, /resume). Older screens, codex, the non-interactive path, slash commands and `--one` are typed or run as before. `"a2a": false` in `cli.json` turns it off. A failure after the prompt was handed over (`CliFailed`, `ReplyMissing`) starts a cooldown (`cooldown.json`, shown by `aos-agent ctl ls -l`). For claude's print form, a result line marking a temporary API error (429, 408, 409, 5xx, overloaded, connection failed, or the CLI's own api_retry giving up) exits 0 instead of stopping the loop: unanswered letters stay pending in `retry.json`. After cooldown, one `[aos] retry: ...` prompt continues the same conversation without repeating their text or claiming new letters; its answer counts as theirs and clears the retry record. If the conversation was not saved, a new one carries the history and retry prompt. The 10th temporary failure in a row counts as permanent (letters dropped, retry record removed, exit 1). A temporary slash failure drops that slash letter as failed, exits 0 and leaves any earlier retry record untouched. Other failures drop the letters as `failed` (`aos-agent ask` then says `LetterDropped`) and stop as before; codex always keeps the old behavior. Non-text claude results are `CliFailed`. Claude's `brain_failed` event carries `name`, `reason`, `code`, `retry`, `attempt`, `dropped`, `wait_s` for temporary errors, and `status` / `cause` when available; codex keeps only `name` and `reason` besides the hook engine's fields. The shared brain_notify hook uses a boolean `retry` on `CliFailed` / `ReplyMissing` to describe continuation or a permanent stop; without that boolean (codex), it quietly does nothing. `reasoning_effort` in llm.json (how hard the model thinks) becomes claude's `--effort` (`low`, `medium`, `high`, `xhigh`, `max`; anything else is `CfgBad`; on codex any `reasoning_effort` is `CfgBad`); it is read every turn, while an open screen keeps the level it was opened with until it is closed and opened again. A changed history starts a new conversation that carries the record over (at most `reseed_bytes` of cli.json, default 48000). A letter that is exactly `/clear`, `/compact`, `/status`, `/usage` or `/exit` (sent with `aos-agent say` or `chat`) is done by aos and answered with one `[aos] slash: ...` message (claude's own words for `/compact`, `/usage`): `/clear` moves `history.jsonl` to `history_removed.jsonl` and starts a new conversation; codex's `/compact` starts a new thread carrying aos's record; `/exit` closes the screen. After claude's `/compact` history is its summary. `/compact INSTRUCTIONS` is `/compact` too (claude gets the instructions for its summary; codex ignores them). A `/compact` letter is always a batch of its own: letters before it are answered first, it and the ones after it wait in `cur/` for the next turns. The eca-claude template's `context_wrap` hook (on_clock, `lib/tools/agent/context_wrap`) watches the context: at `config.percent` (default 35) of the window it sends one wrap-up message, then, once that is answered and the queue is empty, a letter that is only `/compact`; it does not repeat until a later turn reads under the limit. Claude Code compacts by itself (for `/compact` or when full); the template's `compact_hook` turns its PreCompact / PostCompact hooks into the aos hook points `before_compact` (change the summary instructions, give `restore` text that is added right after the compaction, or exit 10 to block it) and `after_compact` (only tells, with the `summary`): `aos/me/self_hook.md#/Hook events`. A blocked `/compact` letter is answered with the CLI's own refusal line; history stays. With the screen open, `/clear` and `/compact` are typed into it (not while it answers, and not while claude's input box has text: see `#/screen`). A letter starting with `/goal` (`/goal TEXT`, `/goal clear`, `/goal`) is the CLI's own goal, separate from aos's `goal.json`: typed into an open screen, else handed to claude as it is (codex exec has no `/goal`; aos says so). When codex's screen asks `Replace goal?`, aos picks `1. Replace current goal`; it presses nothing for any other question. `TrustMissing`: see `aos/cli/errors.md#/Codes you will meet`. Other codes: StackMissing, HistoryBad, PostFailed, WriteFailed, HookFailed, HooksBad, ToolsBad, CfgBad, ToolsMissing, CliMissing.

# aos-eca-screen: the screen

```sh
aos-eca-screen --eca /abs/def open --detach   # screen opened (...)
aos-eca-screen --eca /abs/def watch           # follows live.jsonl until one answer ends
aos-eca-screen --eca /abs/def close           # closed
aos-eca-screen --eca /abs/def peek /usage     # the /usage answer, printed at once
```

People use `aos-agent open / close / watch / peek -t NAME` (`aos/cli/talk_settings.md#/chat and screens`). It reads `AOS_STACK` (unset = `StackMissing`) and `AOS_WS`; ECA_DIR holds cli.json. `--eca` goes before or after the action; `--detach` (no short name) goes after open. No cli.json in the folder (open, watch, peek) or no `--eca` = `ArgumentsBad`; close with a bad cli.json still closes, with a warning; unknown action = `CommandUnknown`. open attaches unless detached; Ctrl-] (or Ctrl-\) leaves the screen running. close keeps the conversation and refuses while answering (`SessionBad`). watch ends after one answer, or when its daemon row stops running or disappears (unreadable daemon or table: it keeps waiting); Ctrl-C leaves it with exit 0.

Slash commands typed on the screen go to the CLI itself. aos follows it: when the CLI moves to another conversation (claude `/clear` or `/resume`), the next answer goes on in that one; `/clear` also empties the agent's `history.jsonl` (codex: when the answer comes from a thread that has only this turn; a thread with older turns is a `/resume` and history stays). claude's `/compact` keeps the conversation and replaces history with claude's summary (one `[aos] summary: ...` message); codex's `/compact` gives no summary text, so history becomes the user and assistant messages codex kept (from its compacted `replacement_history`, without tool definitions, tool calls and `<environment_context>` blocks; if nothing can be read, history stays). Old messages move to `history_removed.jsonl`. `/exit` ends the screen; the next message is answered without one.

`peek /status` or `peek /usage` (`aos-agent peek -t NAME /usage`) prints the same answer as the letter, but at once, also while the agent is in a turn: no letter, nothing in history, no lock on the cell, nothing typed into the screen (`/usage` is a separate `claude -p --no-session-persistence`; codex has no usage report outside its screen and says so). Other commands: `ArgumentsBad`. The panorama page uses it for its usage and status buttons; `/context` still goes through the queue (it must not be typed into a screen that is answering).

A slash letter from the queue while the screen is open (for example the lone `/compact` that `context_wrap` sends): if the screen is answering (`busy.txt` in the cell), or (claude) its input box has text someone typed or cannot be read (another dialog is up), it is not typed: the letter stays in `cur/` and is tried again on the next round, with a warning in the agent's log; aos never clears the input box (that would eat the person's words). A key pressed in the instant between that look and the typing can still be joined to the command (known limit). Otherwise aos types it into the screen (tmux `send-keys -l`, Enter half a second later), then waits up to 120 s for the CLI's hook to replace history (claude: SessionStart compact or clear) and answers the letter; if history did not change by then, the answer says so and the command is not typed again. The same input-box check holds for `/goal` and `/context` on claude's screen; codex's screen is not checked.

How full the context is while the screen is open: the interactive claude does not write `live.jsonl`, so `context_wrap` reads claude's own transcript (`<cell>/transcripts/claude-<session>.jsonl`, or `~/.claude/projects/*/<session>.jsonl`): the usage of the last finished turn; right after a compaction there is no reading until the next answer. The transcript has no context window size: it comes from `config.window` of the hook, else from an earlier `claude -p` turn in `live.jsonl`; with neither, the hook stays quiet, so an agent that has only ever talked on its screen needs `config.window` (`aos/me/self_hook.md#/Hook options and answers`).

# External MCP servers (claude and codex)

One server file per server; list them in `cli.json` as `"mcp_servers": ["mcp/site.json"]` (relative to cli.json, directives allowed). The CLI connects itself; a listed server is fully approved; `only` / `except` pick tools. Tool names are `mcp__<name>__<tool>`.

```json
{"description": "<one line>",
 "mcp_server": {"name": "site", "transport": "http", "url": "https://<host>:<port>/mcp",
                "bearer_token_env": "SITE_TOKEN", "env_file": "/home/<me>/.config/<agent>/site.env", "ca_file": "/home/<me>/.config/<agent>/ca-bundle.pem"}}
```

stdio: `"transport": "stdio", "command", "args", "env", "env_file"`; it is started through `aos-mcp-launch <server file>`, which reads env_file into the server process only. The server starts in the server file's folder: relative `command` and `args` paths are from there (for a workspace path write `{"$env": "AOS_WS", "$path": "data"}`). It also gets the environment of whoever started it (with claude: the whole shell's, API keys included).

- `env_file` now uses the same dotenv subset as aos-tools env files: `${X}` expansion, inline `#` comments and strict matching quotes; `A=x # note` reads as `x`, then `B=${A}y` reads as `xy`.
- The token file is read when the CLI starts; codex gets the value only in its own environment, not its shell's (shell_environment_policy.exclude is added); claude gets it through headersHelper, never in its environment.
- `ca_file` sets SSL_CERT_FILE / CODEX_CA_CERTIFICATE (codex) or NODE_EXTRA_CA_CERTS (claude).
- A broken server file, or an stdio server whose command is not found or cannot be run (checked before every CLI start), is skipped with a `cli_session: warning: external MCP server ... skipped` line; the others still attach. claude turns without a screen print `warning: external MCP server NAME was not connected when claude started (status ...)` when the CLI reports it; later breaks are not reported.
- Never pass a secret with `aos-agent ctl add --envs`: it is stored in plain text in procs/<name>/exec.json.
- Or freeze the same server file into aos tools with aos-mcp-import (`aos/cli/mcp_import.md`); aos hooks then see the calls. Pick one way per server.

# Guarding the CLI's own tools (claude)

aos hooks (`before_tool`, `after_tool`) see only aos tools. To check Bash, Write or Edit, use Claude Code's own hooks.

aos starts claude in your workspace without isolating it: the workspace `.claude/settings.json` is read as usual, and its hooks run next to the ones aos adds. The stock template runs with `--permission-mode dontAsk` and Bash allowed: no person confirms a command.

The stock template has no such hook. To gate Bash, add a `PreToolUse` hook with matcher `Bash` to the workspace `.claude/settings.json`:

```json
{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /abs/path/gate.py"}]}]}}
```

The program gets the call as JSON on stdin (the command line is `tool_input.command`) and decides by printing:

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "why"}}
```

What the answer does:

- nothing printed: the command runs, nobody is asked.
- `deny`: the command does not run; you get the reason.
- `ask`: with the screen open, a confirmation box appears on the screen and waits for a person. Without a screen (aos runs `claude -p`) it counts as deny. So "ask the user first" needs the screen open; when refused, report it and ask for the screen; do not rephrase the command to get past the gate.
- A permission rule in the same file (`permissions.ask`, `permissions.deny`) only refuses in this mode, screen or not; `permissions.ask` shows no box.

Not covered: a command a person types on the screen with `!` (no hook is called); codex.

Rules for one agent only: put the same settings in its definition, in `cli.json` under the key `settings` (an object like `.claude/settings.json`, or the path of a JSON file next to `cli.json`). aos merges it into the `--settings` it adds itself: both sides' hooks run. In a hook command, `$AOS_CLI_DEF` is the definition folder: `"command": "python3 \"$AOS_CLI_DEF/gate.py\""`. A definition is edited by its owner (a person), not by you (`aos/rules.md`). claude only; on any other kind (codex, pi) `settings` is `CfgBad`.

Do not put `--settings` in `cli.json` flags: `CfgBad` (the agent stops before taking a message); use the `settings` key.

A turn without a screen starts a new CLI, so it reads the file again. Whether an open screen picks up a change was not verified: close and open it.

# Delayed screen closure

The eca template has screen_linger_start (after_start, first) and screen_linger_stop (after_stop), 4000 ms timeout; the handler only warns on an error and exits 0, so a failure does not stop the loop. Stop schedules closure on the screen's tmux server; start/wake cancels it. cli.json screen_close_after_s is a non-negative integer in seconds: default 600, 0 closes immediately through reap. Changed settings apply on the next stop only.

Orders live at <stack>/<kind>/screen_close.json. Reap checks the token, tmux server identity and the local loop's pid/ticks/boot_id; it never reads a daemon table. A new loop or screen is not closed; an unverifiable live pid keeps the order and warns. A busy cell lock retries every 30 s, up to ten times. Attached viewers are disconnected too. Set both hooks to null to disable closure. `aos-agent ctl stop` does not close the screen itself, so these hooks are the only closer after a stop; `ctl rm` and `ctl set-def` still close it at once.

No sweeper fallback: SIGKILL/OOM without after_stop, or opening a screen while the agent is already stopped, schedules no closure. Moving the tree can invalidate a scheduled absolute command. tmux 3.2 or newer is required.

# The pi body (kind pi)

`"kind": "pi"` in `cli.json` runs the pi coding agent (`templates/eca-pi`). `pi` must be on PATH, and so must the `node` it runs on (pi's launcher starts with `#!/usr/bin/env node`; exit 127 means one of them is missing). The shell that opens the screen needs both too.

- Each batch is one `pi --mode rpc --no-approve --session-dir <cell>/pi-sessions --session-id <id>` run: aos sends the prompt as one `prompt` command and the run ends at `agent_settled`. aos makes the id on the first turn (`session.txt`); the same id continues the conversation. The conversation file is `<cell>/pi-sessions/<time>_<id>.jsonl` (cell = `$AOS_STACK/pi`). Events go to `<cell>/live.jsonl`.
- Letters that come while it answers are sent one `steer` each; pi reads them before its next model call, all before `agent_settled`. The answer is every segment joined with a blank line (one reply to the prompt and each letter, or one reply that covers them). `"live_mail": false` in cli.json turns this off (the letters wait for the next turn); `live_mail_cap` is as for claude.
- pi exits 0 even when the model call failed: an answer that ended with `stopReason` `error` or `aborted` is `CliFailed` with pi's errorMessage. Failures are not split into temporary and permanent (as codex); pi retries by itself first.
- Screen: `aos-agent open` starts the interactive `pi` in tmux on the same conversation (`--tui-mode regular`) with aos's screen extension (`<cell>/pi-aos-screen.mjs`, which loads `lib/aos/agentlib/pi_aos_screen.mjs`). It reports each settled turn to aos (`<cell>/turns.jsonl`), follows `/new` and compaction, and while the screen is open aos's letters go through `<cell>/pi_inbox/` into the conversation (a `steer` when a turn is running). `aos-agent close` ends it; after `ctl stop` the screen closes after `screen_close_after_s` (default 600).
- What a person types on the screen and pi's replies to it are in `turns.jsonl` and pi's conversation file, not in aos's history. Letters sent through the inbox carry no sender line.
- aos tools: before each run aos writes `<cell>/pi-aos-mcp.mjs`, a one-line pi extension that registers the aos MCP server, and passes it with `-e`. Tools are declared directly: `mcp__aos__NAME`. `mcp_servers` (external MCP) is `CfgBad` for pi.
- `system` is appended with `--append-system-prompt FILE`, read again every run. `model` in llm.json becomes `--model PROVIDER/ID`; none = pi's own default (`pi --list-models`; the default must be a provider you are logged in to). `reasoning_effort` in llm.json becomes `--thinking` (`off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`; anything else is `CfgBad`). pi records the level in its conversation: after `aos-agent llm rm reasoning_effort` the same conversation keeps the last level; a new one (`/clear`) starts at pi's default.
- aos adds `--mode`, `--session-dir`, `--session-id`, `--no-approve`; writing those, `-p`, `--print`, `--session`, `--no-session`, `--fork`, `-c`, `--continue`, `-r`, `--resume`, `--approve`, `-a` or `-na` in flags is `CfgBad`.
- Permissions: pi asks nothing and has no sandbox. Its read, bash, edit and write run as this Linux user. `--no-approve` only keeps the workspace's `.pi/` settings, MCP file and extensions out; `AGENTS.md` / `CLAUDE.md` are still read.
- Slash: `/compact [INSTRUCTIONS]` without a screen starts one `pi --mode rpc` on the same conversation and sends it `compact`; history becomes pi's summary (pi refuses a conversation that is too short; history then stays). With the screen open it is typed there; when pi does not compact, aos waits 120 s and answers that history did not change. `/clear` starts a new conversation (typed as `/new` on an open screen). `/goal` and `/usage` are answered as not available; `/status` works.
- context_wrap: not in the template; pi's events carry token counts but no context window: give the hook `config.window`.
