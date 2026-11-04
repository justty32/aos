# proto8/demo — 兩個 agent 範本：eca-claude（外部 coding agent）與 agent-fsm（aos 自己的 loop／fsm agent）

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop…，C++）、[bin/README](../bin/README.md)（aos-eca-turn、aos-tools…）、[extras/agent](../extras/agent/README.md)（aos-agent）｜慣例：[CONVENTION](../docs/CONVENTION.md)

<a id="agent-danagent-dan-q11-02-晚刪了"></a>
<a id="agent-eveagent-當工具10-24"></a>
<a id="agent-meg記憶庫10-24"></a>
<a id="talkagent-之間寄信10-24"></a>
<a id="agent-gus小念頭10-24"></a>
使用者 11-04：「demo中的，用不到的全部刪掉，也不用封存了。」所以這裡只留 `eca-claude`（當時 aos-eca `add` 的預設範本；aos-eca 11-04 晚併進 [aos-agent](../extras/agent/README.md)，`aos-agent add` 不給預設、要明寫資料夾）；同一天又加了 [`agent-fsm`](#agent-fsm)（使用者「接下來是弄aos loop/fsm agent了」）。兩個範本對外同形（`_entry`＝aos-loop、queue／history／ctl／state、同一份 `tools.json`、`--prompt` 開場白），對照表在 [thinking 11-04 loop-fsm-agent 02](../thinking/2026-11/04/loop-fsm-agent/02-跟-eca-對照.md)。其餘範例（agent-ann、agent-bob、agent-eve、agent-gus、agent-hal、agent-kai、agent-liv、agent-meg、agent-pip、daemon、daemon-2、daemon-3、tick、talk、eca-codex）與 `run.sh` 都刪了、沒封存；測試還要用的 agent-bob、agent-ann、agent-eve、tick 搬到 `proto8/tests/fixtures/` 當測試的固定資料（說明在 [code map 02-tests](../../wf/workflows/common/code-map/proto8/02-tests.md)）。

**PATH 由呼叫的人放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），定義裡寫的 `aos-loop`、`aos-exec`、`aos-eca-turn` 要呼叫端事先放進 PATH：C++ 的 `proto8/impls/<名>/bin/`（要先建，見 [testing](../../wf/workflows/testing.md#proto8不在-ctest-裡)）與 Python 的 `proto8/bin/`；`proto8/tests/aos_bins.py` 就是這樣放的。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-eca-claude](docs/01-eca-claude.md) | 外部 coding agent 範本（eca-claude） |
| [02-agent-fsm](docs/02-agent-fsm.md) | loop／fsm agent 範本 agent-fsm（11-04） |

<a id="eca-templates"></a>
<a id="agent-fsm"></a>

## 測試

`python3 -m unittest discover -s proto8/tests`（先建 impls）：`test_agent_fsm.py`（agent-fsm：13 案，假腦與本機假端點、掛 daemon）、`test_eca.py`（這份範本；codex 版由它複製再換 `cli.json`）、`test_eca_turn.py`（aos-eca-turn）、`test_agent_cmd.py`（aos-agent，兩個範本都掛；11-04 起取代 `test_eca_cmd.py`、`test_human.py`）。
