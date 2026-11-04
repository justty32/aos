# proto8/demo — 兩個 agent 範本：eca-claude（外部 coding agent）與 agent-fsm（aos 自己的 loop／fsm agent）

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop…，C++）、[bin/README](../bin/README.md)（aos-eca-turn、aos-tools…）、[extras/agent](../extras/agent/README.md)（aos-agent）｜慣例：[CONVENTION](../docs/CONVENTION.md)

<a id="agent-danagent-dan-q11-02-晚刪了"></a>
<a id="agent-eveagent-當工具10-24"></a>
<a id="agent-meg記憶庫10-24"></a>
<a id="talkagent-之間寄信10-24"></a>
<a id="agent-gus小念頭10-24"></a>
使用者 11-04：「demo中的，用不到的全部刪掉，也不用封存了。」所以這裡只留 `eca-claude`（當時 aos-eca `add` 的預設範本；aos-eca 11-04 晚併進 [aos-agent](../extras/agent/README.md)，`aos-agent add` 不給預設、要明寫資料夾）；同一天又加了 [`agent-fsm`](#agent-fsm)（使用者「接下來是弄aos loop/fsm agent了」），晚上再加 [`llm-kernel`](docs/03-llm-kernel.md)（agent-fsm 問腦要寄信給它；使用者「把請求丟到llm kernel(一個loop)，處理好後收回信」）。兩個範本對外同形（`_entry`＝aos-loop、queue／history／ctl／state、同一份 `tools.json`、`--prompt` 開場白），對照表在 [thinking 11-04 loop-fsm-agent 02](../thinking/2026-11/04/loop-fsm-agent/02-跟-eca-對照.md)。其餘範例（agent-ann、agent-bob、agent-eve、agent-gus、agent-hal、agent-kai、agent-liv、agent-meg、agent-pip、daemon、daemon-2、daemon-3、tick、talk、eca-codex）與 `run.sh` 都刪了、沒封存（agent-bob、agent-ann、agent-eve、tick 先搬進 tests/fixtures，同天隨 proto8/tests 刪了）。

**PATH 由呼叫的人放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），定義裡寫的 `aos-loop`、`aos-exec`、`aos-eca-turn` 要呼叫端事先放進 PATH：C++ 的 `proto8/impls/<名>/bin/`（要先建，見 [testing](../../wf/workflows/testing.md#proto8)）與 Python 的 `proto8/bin/`。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-eca-claude](docs/01-eca-claude.md) | 外部 coding agent 範本（eca-claude） |
| [02-agent-fsm](docs/02-agent-fsm.md) | loop／fsm agent 範本 agent-fsm（11-04） |
| [03-llm-kernel](docs/03-llm-kernel.md) | llm kernel 範本 llm-kernel（11-04 晚：問腦＝寄信給它、收回信） |

<a id="eca-templates"></a>
<a id="agent-fsm"></a>
