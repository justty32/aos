# templates — agent 範本與同步裁判比對器。

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop…，C++）、[cmd](../cmd/README.md)（aos-eca-turn、aos-tools…）、[aos-agent](../cmd/aos-agent/README.md)｜掛在 daemon 上的管理元件：[kernel](../kernel/README.md)｜慣例：[CONVENTION](../docs/CONVENTION.md)

<a id="agent-danagent-dan-q11-02-晚刪了"></a>
<a id="agent-eveagent-當工具10-24"></a>
<a id="agent-meg記憶庫10-24"></a>
<a id="talkagent-之間寄信10-24"></a>
<a id="agent-gus小念頭10-24"></a>
複製出去用的 agent 範本，都用 `aos-agent ctl add` 掛（不給預設、要明寫資料夾）：`eca-claude`（外部 coding agent）、[`agent-fsm`](#agent-fsm)（aos 自己的 loop／fsm agent；問腦＝寄信給 [llm-kernel](../kernel/docs/01-llm-kernel.md)）。兩個範本對外同形（`_entry`＝aos-loop、queue／history／ctl／state、同一份 `tools.json`、`--prompt` 開場白），對照表在 [thinking 11-04 loop-fsm-agent 02](../thinking/2026-11/04/loop-fsm-agent/02-跟-eca-對照.md)。

**開一隻新 agent 就 `cp -r`**（templates-cp，使用者 11-10「copy-out能刪就刪」）：`cp -r $AOS_HOME/templates/範本名 目的資料夾`（kernel 範本是 `$AOS_HOME/kernel/名`）。範本裡指到範本外、落在 proto8 的路徑（`tools.json` 的工具、reviewer 借 agent-fsm 的格、kernel 範本的 `exec`）一律寫成 `{"$env": "AOS_HOME", "$path": "/…"}`，範本裡沒有捷徑，所以抄到哪都能跑；只要這台有 `AOS_HOME`＝放 lib、templates、knowledge 的那個資料夾的絕對路徑，可以是 proto8 本身或它的抄本（使用者 11-13「em-Q1:B」）。給法三選一：殼裡 `export AOS_HOME=…`；或把根 `.env` 裡那行註解換成 `AOS_HOME=/絕對路徑`；或寫 `AOS_HOME=${AOS_WS}/../aos/proto8` 這種相對起根位置的（使用者 11-10 午「要用相對位置、絕對位置、環境變數指定都可」）。會被 `aos-exec` 直接起的根範本（[`daemon-root/`](daemon-root/README.md)、kernel 的四份）自帶 `.env`，最後一行 `AOS_HOME=${AOS_HOME}`＝沒設就在起根當下報 `DotenvBad … .env line N`。範本裡的 `tests/`、`README.md` 會一起抄過去，`tests/` 可以刪。細節在 [02-agent-fsm](docs/02-agent-fsm.md)；「`defs/` 本身就是根入口」的根 daemon 範本是 [`daemon-root/`](daemon-root/README.md)（名字只是例子）。

**範本不帶測試**（使用者 11-10「啊？範本不該有tests。有的話就跟着抄。」，[tonight-rulings](../thinking/2026-11/10/tonight-rulings/README.md) 題 5）：範本資料夾裡抄到哪就帶到哪，所以測試一律放 [`tests/`](tests/)——`tests/agent-fsm/`、`tests/reviewer/`、`tests/judge-llm/` 各測一個範本，`tests/` 底下直接放的 `test_daily.py`、`test_paths_move.py` 跨範本。跑法：`python3 -m unittest discover -s proto8/templates/tests/agent-fsm`（資料夾名有 `-`，不能從 `tests/` 一次 discover 下去）。`cp -r` 與 `agent_def new` 也是整夾抄。

**PATH 由呼叫的人放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），定義裡寫的 `aos-loop`、`aos-exec`、`aos-eca-turn` 要呼叫端事先放進 PATH：C++ 的 `proto8/impls/<名>/bin/`（要先建，見 [testing](../../wf/workflows/testing.md#proto8)）與 Python 的 `proto8/cmd/<名>/bin/`（`proto8/install.sh` 一次放好）。

[`tool-python`](tool-python/README.md) 不是 agent 範本，是**一支工具的骨架**（[tools-def](../thinking/2026-11/10/tools-def/README.md)）：`_entry.json`（`python3 tool.py`）＋`tool.py`（用 [`lib/tool_spec.py`](../lib/tool_spec.py) 寫的加法）＋產出來的 `_tooldef.json`、`_metainfo.json`＋給 AI 看的英文 README。腦用 `tools_def new` 複製它、只改 `tool.py` 的下半段；人可以直接 `cp -r`，改完跑 `python3 tool.py --write-defs`。測試在 `tests/tool-python/`。

[`judge-llm`](judge-llm/README.md) 是同步呼叫 llm kernel 的裁判比對器，供 measure 的 `compare` 使用；複製後改 `judge.json` 與 `prompt.txt` 就能換模型與規則。

[`reviewer`](reviewer/README.md) 重用 agent-fsm 的格，讓 review_round 試降級並留下專精、差異化與退休建議，agent 讀結果、開處方。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-eca-claude](docs/01-eca-claude.md) | 外部 coding agent 範本（eca-claude） |
| [02-agent-fsm](docs/02-agent-fsm.md) | loop／fsm agent 範本 agent-fsm |

<a id="eca-templates"></a>
<a id="agent-fsm"></a>
