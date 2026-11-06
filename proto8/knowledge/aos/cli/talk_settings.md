# Messages, screens and agent settings

Send messages and change one agent's overlays without modifying its definition.

```sh
aos-agent say --target bob "hello"
aos-agent listen --target bob --timeout-s 60
aos-agent listen --target bob --last 3 --follow
aos-agent tools --target bob add read ../lib/base/read
aos-agent llm --target bob set endpoint=smart-high
```

say prints a letter name. Words are joined with spaces. No words, or `-`, reads stdin; terminal stdin with no words is an error. Paused/sleeping agents still queue messages. listen waits for the latest question by default and prints only answer text. Without a timeout it can wait forever. `--last N` prints question/answer blocks. `--follow` (`-f`) follows new exchanges, with or without `--last`; alone it follows only new answers. Do not combine `--timeout-s` with `--last` or `--follow`. Ctrl-C in follow exits 0; while waiting it exits 130.

chat sends one line at a time and waits for each answer. Ctrl-C leaves. open/close/watch require a declared screen interface. `open --detach` opens without attaching. Without a screen, use listen.

`aos-agent tools --target bob ls|get NAME|add NAME PATH|rm NAME|reset` manages the toolbox (choose one action). No action means ls. Changes are saved as this agent's overlay; the definition is not changed. add/rm can print the same result lines as aos-tools. reset deletes the overlay; see [safety](safety.md).

`aos-agent llm --target bob show|set KEY=VALUE...|reset` manages changed brain keys. No action means show. Only changed keys are stored; other keys follow the definition. Values are strings. reset removes changes.

Brain service calls are separate: `aos-llm ls` lists endpoint packs; pipe a request letter into `aos-llm ask`. It needs `AOS_LLM_KERNEL`.
