# cmd — 人在終端打的指令（Python）

← [proto8](../README.md)｜慣例：[CONVENTION](../docs/CONVENTION.md)｜共用模組：[py](../py/README.md)｜C++ 實作：[impls](../impls/README.md)

一支指令一夾，夾名＝指令名，執行檔在 `<名>/bin/<名>`（跟 impls 同形；aos-eca 兩支同夾）。命令列共用模組（`aos_flags`、`aos_ws`、`daemon_ctl`）在 [proto8/py](../py/README.md)；CLI 對話與介面宣告的共用模組（`cli_session`、`agent_files`）在 [lib/agent](../lib/docs/03-索引-agent等.md)。共用模組依序從自己的資料夾、自己 `realpath(__file__)` 往上找到的 repo `py/`／`lib/`、標準 `sys.path` 找；不再從 PATH 上 `aos-tools` 的真位置推。

| 指令夾 | 是什麼 |
|---|---|
| [aos-agent](aos-agent/README.md) | 給人用的 agent 介面：add、say／listen／chat、畫面、tools 覆蓋層、搬家範本 |
| [aos-daemon-ctl](aos-daemon-ctl/README.md) | 掛上 proc、起停、暫停；prune 自檢與清理舊列；poke 叫 daemon 立刻看檔 |
| [aos-feedback](aos-feedback/README.md) | 收集指令／函數意見；從 AI 評分與工具帳計算舒適度 |
| [aos-tools](aos-tools/README.md) | 一個 agent 資料夾一份工具註冊檔（tools.json） |
| [aos-clock](aos-clock/README.md) | 把時鐘檔的回合數往前走一格 |
| [aos-eca](aos-eca/README.md) | 外部 coding agent（claude／codex）：`aos-eca-turn` 答一輪、`aos-eca-screen` 開畫面 |
| [aos-mcp](aos-mcp/README.md) | 把 aos-tools 登記的工具當 MCP tools 給外部 agent 叫 |
| [aos-sandbox](aos-sandbox/README.md) | 照一份設定把 prog 關進沙箱再跑 |
| [aos-grow](aos-grow/README.md) | 把一個函數往上長一級或縮回一級（原型） |

> **C++（[proto8/impls](../impls/README.md)）是唯一實作**（使用者 10-23：「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 和時鐘，使用者選「fsm 也改用 C++、tick 先留 Python」）：
> `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 的說明在各自的 README：[aos-exec](../impls/aos-exec/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-fsm](../impls/aos-fsm/README.md)、[aos-daemon](../impls/aos-daemon/README.md)；inst 是 C lib [inst](../impls/aos-inst/README.md)。
> 這裡的 Python 支都用 `aos_flags.py` 的旗標解析 `parse`；完整說明在各支的檔頭 docstring。

aos 的程式都不動 PATH（ideas § 24）：自己跑時把 `proto8/impls/<名>/bin/` 與 `proto8/cmd/<名>/bin/` 放進 PATH。
要一次放好：impls 建完後跑 `proto8/install.sh`（11-05），把 `impls/*/bin/*` 與 `cmd/*/bin/*` 全部 symlink 進 `~/.local/bin`（給參數換目的地、`--dry-run` 只印、`--uninstall` 拿掉指進這份 repo 的連結；PATH 上同名的別支排在前面會印提醒行 `install.sh: warning: …`（stderr）；目的地是檔案＝`DestBad`）；同時在 Python user site 寫 `aos-proto8.pth`，精確兩行是本 repo `proto8/py` 與 `proto8/lib` 的絕對路徑，讓複製出 repo 的程式也能從標準 `sys.path` import；`--dry-run` 只印、不寫 `.pth`，`--uninstall` 只刪內容完全屬於本 repo 的那份，不動別份 repo 的設定；user site 不可用時只印一行 warning，其餘照裝，這時可明給 `PYTHONPATH` 這兩個路徑。Python 支也可從自己的 `realpath(__file__)` 往上找 repo；已有同名的別的東西（含內容不同的 `.pth`）不蓋、印 `skip`，最後 stderr 補 `install.sh: error: LinkFailed N names already taken by something else`、退 1；repo 換位置要重跑。

三扇門（11-05 [stdio-unify](../thinking/2026-11/05/stdio-unify/README.md)）：這裡每支的錯誤行是 `程式: error: 代號 原因`（退 1）、提醒行是 `程式: warning: 句子`；`--help`＝英文說明到 stdout、退 0；不給參數／子命令＝`ArgumentsBad`；Ctrl-C 退 130、不吐 traceback；stdout 被對面先關（`| head -1`）退 141、不吐 traceback（用 `aos_flags.run` 包 main 的支；aos-sandbox 沒包，它除了 --dry-run 那行就直接 exec）（共用小函式在 `aos_flags.py`，見 [docs/02](docs/02-aos-clock與已定值.md)）。

## 分檔目錄

> aos-tools、aos-clock、aos-daemon-ctl、aos-eca 的說明超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按標題（再按條號／頂層清單項）拆開，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-逐支說明](docs/01-逐支說明.md) | 逐支說明：開頭、aos-tools - 一個 agent 資料夾一份工具註冊、aos-round 不在了、aos-eca-turn - 外部 coding agent |
| [02-aos-clock與已定值](docs/02-aos-clock與已定值.md) | 逐支說明（續）：aos-clock - 把時鐘檔的回合數往前走一格、aos_flags.py：命令列旗標解析 parse(；已定值 |
| [03-aos-daemon-ctl](docs/03-aos-daemon-ctl.md) | aos-daemon-ctl：開頭、哪個 daemon（11-05 起沒設找 ./.stack）、add／rm＝投信、做完的同名再 add＝重新起、自動識別、-- 參數...、--ws WS、--stack S、不碰 /.stack、stop／start、sleep／wake（11-05）、用錯 phase＝PhaseBad、pause／resume、表上的路徑存相對印絕對（11-05）、任何 proc 共用起停睡醒（11-07 B）、寄信子命令的 --reply-to（11-05）、沒給 --reply-to 看 3 秒、ping、poke 門鈴（11-09）、共用回信信箱（11-06） |
| [04-aos-daemon-ctl續](docs/04-aos-daemon-ctl續.md) | aos-daemon-ctl（續）：where --stack 名字、ls、上一層的看法、錯、prune 自檢與清理舊列 |
| [05-aos-llm與eca入口](docs/05-aos-llm與eca入口.md) | aos-llm（Python 改定義那支 11-04 刪了，名字給 C++ 的基礎工具）、aos-eca-screen（eca 的 screen 子介面身體，11-04）；aos-eca-llm 11-04 晚刪了 |

<a id="逐支說明"></a>
<a id="已定值"></a>
<a id="aos-daemon-ctl"></a>
