# py — cmd 共用的 Python 模組

← [proto8](../README.md)｜用它的：[cmd](../cmd/README.md)、[templates](../templates/README.md)、[kernel](../kernel/README.md)、[lib](../lib/README.md)

不是指令、不進 PATH；用的程式從自己的真位置往上找這個夾（`cmd/<名>/bin/` 往上三層），或從 PATH 上 `aos-tools` 的真位置推。

`aos_ws` 與 `lib/tool_io.py` 的兩鐘函式跟 `aos-util` 同義：`AOS_TICK` 沒設或空就沒有時鐘；指到缺檔時，每行程每路徑印一次英文 warning，仍當 0、不建檔；空檔照舊當 0。

| 模組 | 是什麼 | 誰 import 它 |
|---|---|---|
| `aos_flags.py` | 命令列旗標解析 `parse` 與三扇門小函式（`die`、`warn`、`run`…），全 aos 共用短名表 `SHORT`（`parse(…, short=…)`）、不可逆動作前的確認 `confirm`；切 token 包 `lib/tool_io.py` 的 `tokenize_flags`（從自己的真位置找 `../lib/tool_io.py`，單獨複製這支出去不能用），說明在 [cmd/docs/02](../cmd/docs/02-aos-tick與已定值.md) | cmd 的每支 Python 指令、templates/agent-fsm 的格、kernel/llm-kernel 的 fake_slow |
| `aos_ws.py` | 放一則訊息、等答案、讀 stack 的共用小零件；叫 aos-post 的包裝只有這一份（`run_post`） | aos-agent、aos-eca-turn、daemon_ctl |
| `daemon_ctl/` | 找 daemon、讀 daemon 表、寄信等回信的共用套件（aos-daemon-ctl 的本體，`import daemon_ctl`；`__init__.py` 對外名字、`base.py` Fail 與常數、`entry.py` 判型組信（`add_letter` 等）、`table.py` 找 daemon（`find_daemon`）、讀表、上一層看法、`ctl.py` phase 檢查與 pause／resume 寫 ctl 窗、`post.py` 寄信、共用回信信箱、ask／ping；usage 與 `AOS_KERNEL` 提醒行歸各支自己印、套件不印；除了 daemon 自己沒人碰 pid／`/proc`，11-06 [no-pid](../thinking/2026-11/05/no-pid/README.md) P3），說明在 [cmd/docs/03](../cmd/docs/03-aos-daemon-ctl.md) | aos-daemon-ctl、aos-agent、aos-eca-screen |
| `cli_session.py` | 把 claude／codex 的一段對話接成工具（非互動續對話、tmux 畫面、接 aos-mcp）；問一輪的本體是 `ask`，工具形入口 `call_main` 只剩 `aos-eca-turn --one` 在用（要有效的 `$AOS_WS`，沒有＝`WsMissing`） | aos-eca-turn、aos-eca-screen、lib/agent 的 `agent_tool.py`（claude、codex 的 `ask_cli` 叫 `ask`） |
