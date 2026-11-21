# The goal of one agent

Use aos-agent goal to give one agent a goal it is reminded of when it stops by itself (its last answer calls no tool and its queue is empty). It writes only that agent's `<stack>/goal.json`. A parent agent sets the goal of its child the same way.

```sh
aos-agent goal -t bob                         # = get: status, text, reminded N of LIMIT, reason, set_by, updated; or "no goal"
aos-agent goal -t bob get --json              # the goal.json object, or null
aos-agent goal -t bob set Fix the failing test in src/.
aos-agent goal -t bob set --limit 3 -  < goal.txt
aos-agent goal -t bob pause waiting for the review
aos-agent goal -t bob resume                  # the count starts again at 0 (also after the limit paused it)
aos-agent goal -t bob done the test passes    # --abandoned = given up
aos-agent goal -t bob clear -y
```

- `set`: flags go before TEXT; from the first word on everything is the goal text (`set Read --help first.` keeps `--help`).
- `set -n N` = `--limit N`: 1 to 1000, default 10 (here `-n` is not `--name`). The text is at most 1000 characters. `done -a` = `--abandoned`. `-` as the text reads stdin.
- The reminder is one message `[aos] goal: TEXT (reminder N of LIMIT. ...)` in the agent's history. Letters come first. An agent that has not answered anything yet (empty history) gets the goal as its first message.
- A tool call after a reminder (other than goal itself) is progress: the count goes back to 0. After LIMIT reminders in a row without progress (default 10) the goal is paused, with one last message saying so.
- Works for agent-fsm agents and for eca (claude, codex, pi); for an eca, a tool call is seen in the CLI's own transcript.
- `GoalMissing`: no goal. `GoalEnded`: done or abandoned cannot be paused or resumed (set a new one). `GoalBad`: the file is broken (set or clear rewrites it).
- The agent's own tool and the reminder rules: `aos/tools/goal.md`.
