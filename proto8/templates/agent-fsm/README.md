Run an aos agent with loop and FSM cells.

用 `cp -r $AOS_HOME/templates/agent-fsm <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`），再修改 `llm.json`、`system.txt` 與 `tools.json`，即可建立另一隻 agent；入口、四格運作與完整用法見 [agent-fsm 說明](../docs/02-agent-fsm.md)。

wait 格等腦回信不設期限：寄出後每滿 10 分鐘在 stderr 印一行 `agent-fsm: warning: no reply from the brain for N minutes to letter <名>: <原因>; still waiting`、照樣等（原因＝信在 kernel 的哪一格：`requests/new/` 還在排隊沒開始、`cur/` kernel 正在跑〔附那封的 `stderr.txt` 路徑〕、或 `AOS_LLM_KERNEL` 沒設／不是資料夾；kernel 沒在跑由同一拍 `aos-llm recv` 那行說，11-10 晚 two-machines B10）（提醒到第幾次記在 stack 的 `think/wait_warned.txt`）。

`interfaces.json` 宣告身體、工具與腦設定的位置；知識庫由 `tools.json` 裡 `memory` 那格的 `env.AOS_MEMORY` 指定。`_metainfo.json` 宣告估時 `cost.time_ms` 與 `llm` 資源，未設定逾時。
