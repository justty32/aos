# templates — agent 範本與同步裁判比對器。

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop…，C++）、[cmd](../cmd/README.md)（aos-eca-turn、aos-tools…）、[aos-agent](../cmd/aos-agent/README.md)｜掛在 daemon 上的管理元件：[kernel](../kernel/README.md)｜慣例：[CONVENTION](../docs/CONVENTION.md)

<a id="agent-danagent-dan-q11-02-晚刪了"></a>
<a id="agent-eveagent-當工具10-24"></a>
<a id="agent-meg記憶庫10-24"></a>
<a id="talkagent-之間寄信10-24"></a>
<a id="agent-gus小念頭10-24"></a>
複製出去用的 agent 範本，都用 `aos-agent ctl add` 掛（不給預設、要明寫資料夾）：`eca-claude`（外部 coding agent，11-04 前是 aos-eca `add` 的預設範本）、[`agent-fsm`](#agent-fsm)（aos 自己的 loop／fsm agent，11-04；問腦＝寄信給 [llm-kernel](../kernel/docs/01-llm-kernel.md)）。兩個範本對外同形（`_entry`＝aos-loop、queue／history／ctl／state、同一份 `tools.json`、`--prompt` 開場白），對照表在 [thinking 11-04 loop-fsm-agent 02](../thinking/2026-11/04/loop-fsm-agent/02-跟-eca-對照.md)。使用者 11-04：「demo中的，用不到的全部刪掉，也不用封存了。」其餘範例（agent-ann、agent-bob、agent-eve 等）與 `run.sh` 當天都刪了。

**開一隻新 agent 用 [`copy-out`](copy-out)**（11-10 坑-73）：`proto8/templates/copy-out [--proto8 MODE] [範本名，預設 agent-fsm；或 kernel/<名>] 目的資料夾`＝整份抄出、範本裡指出範本資料夾、落在 repo 的相對路徑（`tools.json` 的 `../../lib/…`、`tools/memory/` 的單子／`_memory.json`／兩個捷徑、reviewer 借 `../agent-fsm/` 的格、kernel 範本的 `exec`）照 MODE 改寫：預設 `env`＝`{"$env": "AOS_PROTO8", "$path": "/…"}`（每台設一次 `AOS_PROTO8`，檔兩台一字不差），另有 `relative`（從那個檔的資料夾到 proto8 的相對路徑，兩台同樣相對擺法）、`absolute`（這台 proto8 的絕對路徑，兩台同位置）（11-10 午 TC，使用者「要用相對位置、絕對位置、環境變數指定都可」）；抄完多印一行這隻需要本機備好什麼；它放在 `templates/` 底下而不在範本裡，因為範本整份會被抄進每隻 agent。細節在 [02-agent-fsm](docs/02-agent-fsm.md)；「`defs/` 本身就是根入口」的根 daemon 範本是 [`daemon-root/`](daemon-root/README.md)（名字只是例子）。

兩份 agent 範本都備有 `tools/memory_write/`，與 `tools/memory/` 共用 `_memory.json`，但**不預先登記**。要寫入的那隻再登記；先把 `tools/memory/_memory.json` 的 `base` 指到有權寫的庫，可用相對路徑、絕對路徑或 `{"$env": "MY_KNOWLEDGE"}`，不要讓 agent 寫出廠庫。用法見 [agent-fsm](docs/02-agent-fsm.md) 與 [eca-claude](docs/01-eca-claude.md)。

**PATH 由呼叫的人放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），定義裡寫的 `aos-loop`、`aos-exec`、`aos-eca-turn` 要呼叫端事先放進 PATH：C++ 的 `proto8/impls/<名>/bin/`（要先建，見 [testing](../../wf/workflows/testing.md#proto8)）與 Python 的 `proto8/cmd/<名>/bin/`（`proto8/install.sh` 一次放好）。

[`judge-llm`](judge-llm/README.md) 是同步呼叫 llm kernel 的裁判比對器，供 measure 的 `compare` 使用；複製後改 `judge.json` 與 `prompt.txt` 就能換模型與規則。

[`reviewer`](reviewer/README.md) 重用 agent-fsm 的格，讓 review_round 試降級並留下專精、差異化與退休建議，agent 讀結果、開處方。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-eca-claude](docs/01-eca-claude.md) | 外部 coding agent 範本（eca-claude） |
| [02-agent-fsm](docs/02-agent-fsm.md) | loop／fsm agent 範本 agent-fsm（11-04） |

<a id="eca-templates"></a>
<a id="agent-fsm"></a>
