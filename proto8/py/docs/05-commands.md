# 05-commands — 人在終端打的指令（Python；原 proto8/cmd，11-18 S5 收進 py/aos/apps/）

← [proto8](../../README.md)｜慣例：[CONVENTION](../../docs/CONVENTION.md)｜共用模組：[lib 頂層](04-共用模組.md)｜C++ 實作：[cpp](../../cpp/README.md)

一支指令一夾，本體在 `py/aos/apps/<名>/`（夾名＝指令名去掉 `aos-`、`-` 換 `_`，例 `aos-clock-register`→`clock_register`；aos-eca 兩支同夾），測試在 `py/tests/apps/<名>/`。入口不手寫：`py/entries.json` 一行一支（指令名→模組），`install.py` 照它在 `bin/` 生幾行的 Python 入口（把同一個家的 `lib/` 放上 `sys.path`，再把那個模組當 `__main__` 跑），跟 C++ 的執行檔同一夾；改了 `py/` 要重跑 `install.py` 才生效。命令列共用模組（`aos.flags`、`aos.ws`、`aos.daemon_ctl`）在 aos 套件，原始碼 `proto8/py/aos/`，`install.py` 裝到 `proto8/lib/aos/`（說明在 [py/docs/04](04-共用模組.md)）；CLI 對話的共用模組（`cli_*.py`〔說明在 `cli_session.py`〕）在 `aos.agentlib`、介面宣告讀法 `aos.declared_files` 在 aos 頂層（[索引](03-索引-agent等.md)）。家外的程式找 lib 只經 `$AOS_HOME/lib`，沒設 `AOS_HOME` 就報 `HomeMissing`。

| 指令夾 | 是什麼 |
|---|---|
| [aos-agent](../aos/apps/agent/README.md) | 給人用的 agent 介面：add、say／listen／chat、畫面、tools 覆蓋層、搬家範本 |
| [aos-daemon-ctl](../aos/apps/daemon_ctl/README.md) | 掛上 proc、起停、暫停；prune 自檢與清理舊列；poke 叫 daemon 立刻看檔 |
| [aos-feedback](../aos/apps/feedback/README.md) | 收集指令／函數意見；從 AI 評分與工具帳計算舒適度 |
| [aos-gdb](../aos/apps/gdb/README.md) | 開一個放好入口 `aos.py`（`agent`、`daemon_ctl`、`std`、`defs`）的 Python REPL，給了名字再放 `a = agent.attach(名)`：`a.xxx`＝`aos-agent xxx`（通用代理，一個呼叫＝一條指令）、`a.look` 讀 stack 的檔；斷點全在 `a.bp`（`a.bp.add.<種類>(…)` 回 id，以 id 增刪改查、看為什麼停；控制 `resume`／`step`／`pause` 不收參數、都等到停下才回；觸發器＝hook，工具要跑之前扣住、其他事件那一格做完暫停；觀察者＝另一支 proc 輪詢、成立就 ctl pause；都留字條，本體 `aos.gdb`）；`--hooks FILE`／`--def-hooks` 載入 hook 宣告當參考（REPL 裡 `hooks` 列點與欄位、宣告的點也能下、對不上只提醒、`a.bp.event()` 照宣告排，本體 `aos.gdb.decl`） |
| [aos-tools](../aos/apps/tools/README.md) | 一個 agent 資料夾一份工具註冊檔（tools.json） |
| [aos-clock](../aos/apps/clock/README.md) | 把時鐘檔的回合數往前走一格 |
| [aos-clock-register](../aos/apps/clock_register/README.md) | 時鐘登記表（add／rm／ls）：每 N 個 cycle 往一個 aos-post 箱子寄一句（定時叫醒 agent） |
| [aos-mailbox](../aos/apps/mailbox/README.md) | 我的信箱（`<stack>/mailbox/`，aos-post 箱子）：照 inbox 協議寄信給 agent（名字＋daemon 或信箱路徑）、peek、read；人把自己當一隻 agent 用自己的 stack |
| [aos-sweeper](../aos/apps/sweeper/README.md) | 清道夫：一台 daemon 的 stderr 封存、封存保留期、收表外子 loop（掛成 `_sweeper` 列；手動 `aos-daemon-ctl sweep`） |
| [aos-eca](../aos/apps/eca/README.md) | 外部 coding agent（claude／codex）：`aos-eca-turn` 答一輪、`aos-eca-screen` 開畫面 |
| [aos-mcp](../aos/apps/mcp/README.md) | 把 aos-tools 登記的工具當 MCP tools 給外部 agent 叫 |
| [aos-mcp-launch](../aos/apps/mcp_launch/README.md) | 起一台外部 stdio MCP server：讀 server 檔與它的 `env_file`，exec 成那支 server（eca 原生掛那條用） |
| [aos-mcp-import](../aos/apps/mcp_import/README.md) | 連一次外部 MCP server，把它的工具凍結進同一份 server 檔，疊進 tools.json 就是一包工具；`sync` 重問、印差異、`--yes` 才寫 |
| [aos-sandbox](../aos/apps/sandbox/README.md) | 照一份設定把 prog 關進沙箱再跑 |
| [aos-grow](../aos/apps/grow/README.md) | 把一個函數往上長一級或縮回一級（原型） |
| [aos-json-view](../aos/apps/json_view/README.md) | 只讀：把 json（或 `#/指標` 那段）印成人好讀的樣子：`鍵: 值`、短的擠一行、`\n` 真的換行、字串陣列接成段落、`--depth N` 摺深層 |
| [aos-hook](../aos/apps/hook/README.md) | 讓任何子程式（C++、shell…）提供 hook 點：只有 `fire` 一個子指令——照名字跑掛在那個事件上的 handler（清單 `--list` 或 `--def` 的 interfaces.json `hookeds`；資料走 stdin JSON），一行 JSON 交回各自的退出碼與 stdout、退 0；`--stop-on-nonzero`＝第一個非 0 就停、用它的碼退出。攔不攔、改不改由發事件的程式自己決定；跑 hook 的是共用引擎 `aos.hook_run` |

> **C++（[proto8/cpp](../../cpp/README.md)）是唯一實作**（使用者 10-23：「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 和時鐘，使用者選「fsm 也改用 C++、tick 先留 Python」）：
> `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 的說明在各自的 README：[aos-exec](../../cpp/aos-exec/README.md)、[aos-loop](../../cpp/aos-loop/README.md)、[aos-fsm](../../cpp/aos-fsm/README.md)、[aos-daemon](../../cpp/aos-daemon/README.md)；inst 是 C lib [inst](../../cpp/aos-inst/README.md)。
> 這裡的 Python 支都用 `aos.flags`（`py/aos/flags.py`）的旗標解析 `parse`；完整說明在各支的檔頭 docstring。

aos 的程式都不動 PATH（ideas § 24）：自己跑時把 `proto8/bin/`（C++ 執行檔與 Python 入口，在 proto8 跑 `python3 install.py` 才有）放進 PATH。
要一次放好：一台設一次 `AOS_HOME`＝那個 proto8，每個視窗先 `source $AOS_HOME/env.sh`（或樹裡那份薄的 `env.sh`；`AOS_HOME` 沒設就報 `EnvBad`、不替你設；清掉 `AOS_HOME` 以外的 `AOS_*`、把 `$AOS_HOME/bin`（第一）與 `frontend/bin`（選配的網頁外掛 aos-frontend，在 [proto8/frontend](../../frontend/API.md)）放到 PATH 最前，不往 `~/.local/bin` 放東西；`aos-exec` 不在時提示先跑 `python3 $AOS_HOME/install.py`）。舊的 `cmd/install.sh`（symlink 進 `~/.local/bin`）11-18 S5 收掉（題 X-4 A），由 `install.py` 取代。不在 Python user site 寫 `aos-proto8.pth`（使用者 11-15 裁「6.拿掉。」），複製出 repo 的程式要 import 共用模組，就設 `AOS_HOME`（共用模組只經 `$AOS_HOME/lib` 找）。

三扇門（[stdio-unify](../../thinking/2026-11/05/stdio-unify/README.md)）：這裡每支的錯誤行是 `程式: error: 代號 原因`（退 1）、提醒行是 `程式: warning: 句子`；`--help`＝英文說明到 stdout、退 0；不給參數／子命令＝`ArgumentsBad`；Ctrl-C 退 130、不吐 traceback；stdout 被對面先關（`| head -1`）退 141、不吐 traceback（用 `aos_flags.run` 包 main 的支；aos-sandbox 沒包，它除了 --dry-run 那行就直接 exec）（共用小函式在 `aos.flags`，見 [docs/02](05-commands/02-aos-clock與已定值.md)）。

## 分檔目錄

> aos-tools、aos-clock、aos-daemon-ctl、aos-eca 的說明超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題（再按條號／頂層清單項）拆開，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-逐支說明](05-commands/01-逐支說明.md) | 逐支說明：開頭、aos-tools - 一個 agent 資料夾一份工具註冊、aos-eca-turn - 外部 coding agent、aos-mcp-import - 外部 MCP 工具凍結成包 |
| [02-aos-clock與已定值](05-commands/02-aos-clock與已定值.md) | 逐支說明（續）：aos-clock - 把時鐘檔的回合數往前走一格、aos-sweeper - 清道夫、aos_flags.py：命令列旗標解析 parse(；已定值 |
| [03-aos-daemon-ctl](05-commands/03-aos-daemon-ctl.md) | aos-daemon-ctl：開頭、哪個 daemon（沒設找 ./.stack）、add／rm＝投信、做完的同名再 add＝重新起、自動識別、-- 參數...、--ws WS、--stack S、不碰 /.stack、stop／start、sleep／wake、用錯 phase＝PhaseBad、pause／resume、表上的路徑存相對印絕對、任何 proc 共用起停睡醒、寄信子命令的 --reply-to、沒給 --reply-to 看 3 秒、ping、poke 門鈴、共用回信信箱 |
| [04-aos-daemon-ctl續](05-commands/04-aos-daemon-ctl續.md) | aos-daemon-ctl（續）：where --stack 名字、ls、上一層的看法、錯、prune 自檢與清理舊列 |
| [05-aos-llm與eca入口](05-commands/05-aos-llm與eca入口.md) | aos-llm（C++ 的基礎工具）、aos-eca-screen（eca 的 screen 子介面身體） |

<a id="逐支說明"></a>
<a id="已定值"></a>
<a id="aos-daemon-ctl"></a>
