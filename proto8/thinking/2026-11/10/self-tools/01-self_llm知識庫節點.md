# 01 self_llm 的知識庫節點（交 json-memory 隊照新格式加；11-10 晚改成 ls／set／rm／reset、鍵 model）

← [README](README.md)

knowledge/aos 現在歸 json-memory 隊；這頁是要加進 `me` 底下的節點內容（建議節點名 `me/self_llm`，跟 `me/self_tools` 並排），由它照新 JSON 格式放進去。`me` 那頁講「你能改什麼」的清單也請加一條「你的腦設定：工具 `self_llm`」。

```markdown
# Changing your own brain settings

Tool `self_llm` is `aos-agent llm` aimed at you. It changes only your own brain settings; your definition and other agents stay as they are. Changes work from your next brain call.

`model` picks your brain (a brain pack name of the llm kernel). The other keys only tune how it answers and do not change which brain you are: `temperature`, `top_p`, `max_tokens`, `seed`, `presence_penalty`, `frequency_penalty`, `stop`. Which keys your body reads depends on what kind of agent you are (an eca agent reads only `model`).

One op per call (the JSON is the tool's arguments):

- see: `{"op": "ls"}` (one KEY=VALUE per line: the definition's settings with your changes on top); `{"op": "ls", "long": true}` also says which keys you changed (`agent`) and which come from your definition
- change: `{"op": "set", "settings": {"model": "smart-high", "temperature": "0.2"}}` (values are strings; a key your body does not read is kept anyway, with a warning line)
- undo some changes: `{"op": "rm", "keys": ["temperature"]}` (back to your definition's value; a key you did not change is `KeyMissing`)
- undo all your changes: `{"op": "reset"}`

Rules:

- Use `ls` first, and change one thing at a time.
- Nothing stops you from choosing a brain that does not work. If you do, you stop answering until a human runs `aos-agent llm --target <you> reset`. Only switch to a model you were told exists.
- A brain pack may fix some tuning keys (for example its `temperature`); then your value for that key has no effect.
- Unknown argument names, or an argument the op does not take, are `ArgumentsBad`.
- `DaemonMissing`, `DaemonFailed`, `InstanceMissing`: same as for `self_tools` (the feature is unavailable for now; say so).
```
