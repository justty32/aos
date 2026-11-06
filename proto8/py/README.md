# py — cmd 共用的 Python 模組

← [proto8](../README.md)｜用它的：[cmd](../cmd/README.md)、[templates](../templates/README.md)、[kernel](../kernel/README.md)、[lib](../lib/README.md)

不是指令、不進 PATH；用的程式從自己的真位置往上找這個夾（`cmd/<名>/bin/` 往上三層），或從 PATH 上 `aos-tools` 的真位置推。

| 模組 | 是什麼 | 誰 import 它 |
|---|---|---|
| `aos_flags.py` | 命令列旗標解析 `parse` 與三扇門小函式（`die`、`warn`、`run`…），說明在 [cmd/docs/02](../cmd/docs/02-aos-tick與已定值.md) | cmd 的每支 Python 指令、templates/agent-fsm 的格、kernel/llm-kernel 的 fake_slow |
| `aos_ws.py` | 放一則訊息、等答案、讀 stack 的共用小零件 | aos-agent、aos-eca-turn |
| `cli_session.py` | 把 claude／codex 的一段對話接成工具（非互動續對話、tmux 畫面、接 aos-mcp） | aos-eca-turn、aos-eca-screen、lib/agent 的 claude、codex |
