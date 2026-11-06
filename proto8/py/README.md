# py — cmd 共用的 Python 模組

← [proto8](../README.md)｜用它的：[cmd](../cmd/README.md)、[templates](../templates/README.md)、[kernel](../kernel/README.md)

不是指令、不進 PATH。共用模組依序從自己的資料夾、自己的 `realpath(__file__)` 往上找到的 repo `py/`／`lib/`、標準 `sys.path` 找；最後可由 `install.sh` 寫的 user site `aos-proto8.pth` 或 `PYTHONPATH` 提供，不再從 PATH 上 `aos-tools` 的真位置推。

依賴單向：`py` 可以 import `lib`，`lib` 不 import `py`。CLI 對話與介面宣告的共用模組在 [lib/agent](../lib/docs/03-索引-agent等.md)：`cli_session.py`、`agent_files.py`（11-06 晚 K-5）。

`aos_ws` 與 `lib/tool_io.py` 的兩鐘函式跟 `aos-util` 同義：`AOS_TICK` 沒設或空就沒有時鐘；指到缺檔時，每行程每路徑印一次英文 warning，仍當 0、不建檔；空檔照舊當 0。

| 模組 | 是什麼 | 誰 import 它 |
|---|---|---|
| `aos_flags.py` | 命令列旗標解析 `parse` 與三扇門小函式（`die`、`warn`、`run`…），全 aos 共用短名表 `SHORT`（`parse(…, short=…)`）、不可逆動作前的確認 `confirm`；切 token 包 `lib/tool_io.py` 的 `tokenize_flags`（照上面的順序找共用模組），說明在 [cmd/docs/02](../cmd/docs/02-aos-tick與已定值.md) | cmd 的每支 Python 指令、templates/agent-fsm 的格、kernel/llm-kernel 的 fake_slow |
| `aos_ws.py` | 放一則訊息、等答案、讀 stack 的共用小零件；叫 aos-post 的包裝只有這一份（`run_post`） | aos-agent、aos-eca-turn、daemon_ctl |
| `daemon_ctl/` | 找 daemon、讀 daemon 表、寄信等回信的共用套件（aos-daemon-ctl 的本體，`import daemon_ctl`；`__init__.py` 對外名字、`base.py` Fail 與常數、`entry.py` 判型組信（`add_letter` 等）、`table.py` 找 daemon（`find_daemon`）、讀表、上一層看法、`ctl.py` phase 檢查與 pause／resume 寫 ctl 窗、`post.py` 寄信、共用回信信箱、ask／ping；usage 與 `AOS_KERNEL` 提醒行歸各支自己印、套件不印；除了 daemon 自己沒人碰 pid／`/proc`，11-06 [no-pid](../thinking/2026-11/05/no-pid/README.md) P3），說明在 [cmd/docs/03](../cmd/docs/03-aos-daemon-ctl.md) | aos-daemon-ctl、aos-agent、aos-eca-screen |
