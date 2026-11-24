# Messages, screens and agent settings

Send messages and change one agent's overlays without modifying its definition. Changes are saved in the agent's stack; the definition is not changed.

# say and listen

```sh
aos-agent say -t bob "what time is it"     # prints the letter name
aos-agent listen -t bob --timeout-s 60     # waits for the answer, prints its text
aos-agent listen -t bob --letter NAME      # waits for the answer to that letter
aos-agent listen -t bob --last 3           # blocks: == #N, > question, answer
aos-agent listen -t bob --follow           # new exchanges as they come
```

say: words are joined with spaces; no words or `-` reads stdin; terminal stdin with no words = `ArgumentsBad`. Paused or sleeping agents still queue messages. `--from WHO` (say and chat) names the sender; without it the sender is the agent whose stack holds `$AOS_STACK`, else your login name. When the sender is another agent, or `--from` is given, the text starts with `[say from NAME] ` (say, ask and chat; also subagent `say` / `ask` and an agent typing `aos-agent say` in its shell), for agent-fsm and eca alike. Text without it was typed by a person in a terminal. An eca agent (definition with `cli.json`) also gets the name in the letter; a claude body with its screen open shows it and treats the message as not typed by its user (open the screen and type to speak as its user). A name must be one line of at most 64 characters without `" < > &`, or `ArgumentsBad`. listen without a timeout can wait forever; `--timeout-s S` (`0` = no limit) or `--timeout-cycles N` gives up with `AnswerMissing`. `--follow` (`-f`) works with or without `--last`. Do not combine a timeout with `--last` or `--follow`. Ctrl-C in follow exits 0; while waiting it exits 130. `aos-agent ask -t bob "what time is it"` is say then listen in one step (like the subagent tool's op ask): stdout is only the answer, no time limit by default (`--timeout-s S`, `0` = no limit, or `--timeout-cycles N`), `AnswerMissing` when it gives up. ask waits for the answer to its own letter, so others talking to the same agent at the same time get their own answers; one answer to several letters is printed to each asker. Ctrl-C while ask waits exits 130; the letter was sent, and stderr names it: `aos-agent listen -t bob --letter NAME` reads the answer later.

`listen --letter NAME` waits for the answer to that letter (the name say printed). Without `--letter`: the newest letter still in the queue, else the last letter the agent took and has not answered, else the latest answer. `LetterDropped` (ask, chat, listen): the agent dropped that letter (not a valid message, blocked by a `before_queue` hook, or an eca agent's CLI failed after taking it) and will not answer it; say it again. An agent whose body does not record letter names yet (no `aos` key in its history) is matched the old way, the latest answer, with a warning on stderr.

# chat and screens

`printf 'hello\n' | aos-agent chat -t bob` sends one line at a time and waits for each answer (matched to its own letter, like ask) (the `> ` prompt goes to stderr). Empty lines are ignored; Ctrl-C leaves.

`aos-agent open -t bob` attaches to its screen (`--detach`: open only); `close` closes it and keeps the conversation; `watch` follows the screen until one answer ends. They require a declared screen interface (`ScreenMissing`); without a screen, use listen. The lower-level command: `aos/cli/eca.md#/aos-eca-screen: the screen`.

# One agent's tools

```sh
aos-agent tools -t bob                 # = ls
aos-agent tools -t bob add --name now2 $AOS_HOME/lib/tools/base/peek_now_time
aos-agent tools -t bob rm shell
aos-agent tools -t bob reset -y
```

Choose one action: `ls [-l | --json]`, `get NAME_OR_PATH`, `add [--name N] [--replace] [--no-cache] [--envs K=V]... [--env-file FILE] (PATH | --path-json JSON)`, `rm NAME_OR_PATH`, `reset`. `--no-cache`: inspect an executable tool's definition each time; `--path-json` stores a directive instead of a path. Changes go to this agent's own `tools.json` in its stack, which holds only the differences from the definition's (`"$override"`; a removed tool is `null`). The first change prints a warning that the file was created. add/rm print the same result lines as aos-tools (`removed shell (...: set to null over ...)`). Hub variables: `aos/cli/tool_env.md`.

# One agent's brain settings

```sh
aos-agent llm -t bob set model=fake temperature=0.3
aos-agent llm -t bob ls -l      # model=fake<TAB>agent: which keys this agent changed
aos-agent llm -t bob rm temperature
```

No action means ls. `model` picks the brain pack; `reasoning_effort` says how hard the brain thinks (agent-fsm sends it to the llm kernel, aos/brain.md; eca turns it into its CLI's flag, claude `--effort`, pi `--thinking`; the levels it takes depend on the body); `temperature`, `top_p`, `max_tokens`, `seed`, `presence_penalty`, `frequency_penalty`, `stop` tune it. Only changed keys are stored (`llm.json` in the stack); other keys follow the definition. Values are strings. A key the body does not read (`llm_keys` in the definition's `interfaces.json`) is stored anyway, with a warning. reset removes all changes. `llm set system=...` is refused (ArgumentsBad, nothing stored): use `system`.

Asking the brain service directly is `aos-llm` (`aos/cli/parts/llm.md`).

# One agent's system text

```sh
echo "Be short." | aos-agent system -t bob set   # or: set FILE
aos-agent system -t bob get -l                   # where it comes from, then the text
aos-agent system -t bob reset -y
```

No action means get. set reads FILE, or stdin when FILE is `-` or not given; the text goes whole into `<stack>/system.txt` and replaces the definition's (an agent-fsm sends it as its system message; an eca appends it to the CLI's own). When it takes effect: agent-fsm, its next brain call; eca claude, its next turn; eca codex, its next new conversation (set and reset print a warning); an open eca screen, after it is reopened. Why: `aos/body.md#/System text, history`. The definition must declare `{"aos-agent": {"system": "system.txt"}}`, otherwise `SystemMissing`. reset deletes the copy.
