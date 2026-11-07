Run an aos agent with loop and FSM cells.

複製本範本後，修改 `llm.json`、`system.txt` 與 `tools.json`，即可建立另一隻 agent；入口、四格運作與完整用法見 [agent-fsm 說明](../docs/02-agent-fsm.md)。

`interfaces.json` 宣告身體、工具、腦設定與記憶設定的位置；知識庫由 `tools/memory/_memory.json` 的 `base` 指定。`_metainfo.json` 宣告估時 `cost.time_ms` 與 `llm` 資源，未設定逾時。
