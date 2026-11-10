Run an aos agent with loop and FSM cells.

用範本旁的 `../copy-out --template agent-fsm <目的資料夾>` 複製本範本（指回 repo 的路徑預設寫成 `{"$env": "AOS_HOME", …}`，每台設一次 `AOS_HOME`；`--proto8 relative|absolute` 選別的寫法；只 `cp -r` 出了 repo 會 `ToolsBad`），再修改 `llm.json`、`system.txt` 與 `tools.json`，即可建立另一隻 agent；入口、四格運作與完整用法見 [agent-fsm 說明](../docs/02-agent-fsm.md)。

wait 格等腦回信不設期限：寄出後每滿 10 分鐘在 stderr 印一行 `agent-fsm: warning: no reply from the brain …`、照樣等（提醒到第幾次記在 stack 的 `think/wait_warned.txt`）。

`interfaces.json` 宣告身體、工具、腦設定與記憶設定的位置；知識庫由 `tools/memory/_memory.json` 的 `base` 指定。`_metainfo.json` 宣告估時 `cost.time_ms` 與 `llm` 資源，未設定逾時。
