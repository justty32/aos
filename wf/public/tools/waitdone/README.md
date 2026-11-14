# waitdone: wait until agent-fsm agents have answered

`subagent listen` / `ask` from an MCP client can be cut at 60 s (fixed in repo 252669c47, but the live tree may still be old, and the MCP client has its own tool timeout). For a long task, `subagent say` instead, then run this script in the background (Claude Code: Bash with `run_in_background`); you get notified when it exits.

It is done when each agent's `history.jsonl` ends with an assistant message that has no `tool_calls` (= the agent answered and stopped), and the history has more than 2 lines. Read-only: it only reads the stacks.

## Use
    python3 ~/repo/aos/wf/public/tools/waitdone/waitdone.py [--new] [--timeout 1700] [--every 15] [--procs DIR] NAME...
- Prints `all done` and exits 0, or `timeout, not done: NAME...` and exits 1.
- `--procs`: folder holding the stacks (default `$AOS_HOME/ws/.stack/procs`, else `~/aos-home/ws/.stack/procs`).
- `--new`: only count an answer written after the script started. Use it when the agent already answered an earlier task (else its old answer counts as done at once). Start it right after `say`.
- Then take the answer from the `content` of the last line of `<procs>/NAME/history.jsonl` (or `aos-agent history`), save it to a file and read that.

## Install / remove
Nothing to install; run it with python3. Delete the folder to remove.

## Known limits
- Only for agents whose history is one OpenAI message per line (agent-fsm). Not for eca agents.
- "Assistant without tool calls" also matches an agent that stopped early (e.g. only said "I will do it"); read the answer.
- An agent that is stopped or cooling down never finishes: you get the timeout.

## Author
ok-llmk2 (original `wf/temp/ok-llmk2/waitdone.py`, used for sol x3 and astra x1, 2026-11-14); flags and default path added by repo-aos curation, 2026-11-14 (tested on fake stacks only).
