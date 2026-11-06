# Removal and confirmation

Check the chosen daemon, agent and stack before destructive commands; scripts do not get a confirmation prompt.

`aos-agent ctl rm bob` requires the name explicitly. It never takes the name from `$AOS_AGENT`. It closes the screen, detaches bob and deletes bob's stack. This destroys history and overlays. A stack covering the workspace, definition, daemon, cwd, home or another listed stack is kept.

`aos-agent tools --target bob reset` deletes this agent's tools overlay. `aos-agent llm --target bob reset` deletes its changed brain settings. Both return to the definition; the custom changes have no other copy unless you saved one.

These three commands ask `[y/N]` on stderr only when stdin is a terminal. Only `y` or `yes` continues. Other input, an empty line or EOF gives `aos-agent: warning: nothing done`, exit 0. Ctrl-C at the question exits 130. A reset with no overlay does not ask.

Add `-y`/`--yes` to the destructive action to skip the question:

```sh
aos-agent ctl rm --yes bob
aos-agent tools --target bob reset --yes
aos-agent llm --target bob reset --yes
```

A pipe, an agent call, a script with non-terminal stdin, or `</dev/null` does not ask and proceeds. Exit 0 can mean the user declined; read the warning.

`aos-daemon-ctl rm bob` only detaches and keeps the stack. It does not ask and does not accept `-y`. `aos-tools rm NAME` removes registrations, keeps tool files and does not ask. `--override` replaces a registration; check its name first.
