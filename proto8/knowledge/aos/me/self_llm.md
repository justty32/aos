# Changing your own brain settings

Tool `self_llm` is `aos-agent llm` aimed at you. It changes only your own brain settings; your definition and other agents stay as they are. Changes work from your next brain call.

`model` picks your brain (a brain pack name of the llm kernel). The other keys only tune how it answers and do not change which brain you are: `temperature`, `top_p`, `max_tokens`, `seed`, `presence_penalty`, `frequency_penalty`, `stop`. `reasoning_effort` (agent-fsm) sets how hard the brain thinks (`low`, `medium`, `high`, `xhigh`, `max`; only names your pack accepts, see `aos-llm ls --json`). Which keys your body reads depends on what kind of agent you are: an eca agent reads `model` and `reasoning_effort`. For eca the effort goes to its CLI (claude: `low`, `medium`, `high`, `xhigh`, `max`; pi also `off`, `minimal`); a level the CLI does not take stops you (`CfgBad`) until it is changed or removed.

One op per call (the JSON is the tool's arguments):

- see: `{"op": "ls"}` (one KEY=VALUE per line: the definition's settings with your changes on top); `{"op": "ls", "long": true}` also says which keys you changed (`agent`) and which come from your definition
- change: `{"op": "set", "settings": {"model": "smart-high", "temperature": "0.2"}}` (values are strings; a key your body does not read is kept anyway, with a warning line; the key `system` is refused with ArgumentsBad and nothing is stored: your system text is changed with `self_system`)
- undo some changes: `{"op": "rm", "keys": ["temperature"]}` (back to your definition's value; a key you did not change is `KeyMissing`)
- undo all your changes: `{"op": "reset"}`

Rules:

- Use `ls` first, and change one thing at a time.
- Nothing stops you from choosing a brain that does not work. If you do, you stop answering until a human runs `aos-agent llm --target <you> reset`. Only switch to a model you were told exists.
- A brain pack may fix some tuning keys (for example its `temperature`); then do not set that key: an agent-fsm body sends your value with every brain request, and the llm kernel refuses the request with `RequestBad ... is fixed by endpoint <pack>`; remove the key with `rm`.
- Unknown argument names, or an argument the op does not take, are `ArgumentsBad`. `LlmBad`: your brain settings file (yours or your definition's) is broken; a human must fix it.
- `DaemonMissing`, `DaemonFailed`, `InstanceMissing`: same as for `self_tools` (the feature is unavailable for now; say so).
