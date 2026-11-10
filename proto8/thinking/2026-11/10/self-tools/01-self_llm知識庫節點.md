# 01 self_llm 的知識庫節點（交 json-memory 隊照新格式加）

← [README](README.md)

knowledge/aos 現在歸 json-memory 隊；這頁是要加進 `me` 底下的節點內容（建議節點名 `me/self_llm`，跟 `me/self_tools` 並排），由它照新 JSON 格式放進去。`me` 那頁講「你能改什麼」的清單也請加一條「你的腦設定：工具 `self_llm`」。

```markdown
# Changing your own brain settings

Tool `self_llm` is `aos-agent llm` aimed at you. It changes only your own brain settings; your definition and other agents stay as they are. Changes work from your next turn.

One op per call (the JSON is the tool's arguments):

- see: `{"op": "show"}` (one KEY=VALUE per line: the definition's settings with your changes on top)
- change: `{"op": "set", "settings": {"endpoint": "smart-high"}}` (values are strings; which keys mean something depends on your body; `endpoint` picks the brain pack)
- undo all your changes: `{"op": "reset"}`

Rules:

- Use `show` first, and change one thing at a time.
- Nothing stops you from choosing a brain that does not work. If you do, you stop answering until a human runs `aos-agent llm --target <you> reset`. Only switch to an endpoint you were told exists.
- Unknown argument names, or an argument the op does not take, are `ArgumentsBad`.
- `DaemonMissing`, `DaemonFailed`, `InstanceMissing`: same as for `self_tools` (the feature is unavailable for now; say so).
```
