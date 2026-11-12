← [回入口 10-基礎設施-定義與工作區.md](../10-基礎設施-定義與工作區.md)｜段落：hub 型環境變數（10-28）｜上一份：[06-N-50～N-53](06-N-50～N-53.md)｜下一份：[08-父子交代](08-父子交代.md)

## hub 型環境變數（10-28）

> 超過 8 KB，依 [STRUCTURE](../../../../wf/STRUCTURE.md) 拆開；本檔留入口，各段在下列分檔（原路徑保留，外部連結不斷）。

| 分檔 | 涵蓋 |
|---|---|
| [01-N-63-三件事與跟實作對不上的](07-hub-型環境變數與父子交代/01-N-63-三件事與跟實作對不上的.md) | N-63 本文（命名 `AOS_<名字>`、沒設＝`<名字>Missing`、子 process 繼承）；各實例細節：`AOS_STACK`、`AOS_LLM_KERNEL`（值＝llm kernel 的 stack）、`AOS_KERNEL`、P-39、「給」與 `DaemonFailed`、跨樹 hub |
| [02-N-63-實例-AOS_DAEMON與沒有AOS_HUB](07-hub-型環境變數與父子交代/02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md) | 實例 `AOS_DAEMON`（沒設找 `./.stack`、`find_daemon`）、不定三名、daemon 起子項設 `AOS_DAEMON`、`aos-agent ctl who`、例外 `AOS_AGENT`、沒有 `AOS_HUB` |
| [03-AOS_-變數的四種性質](07-hub-型環境變數與父子交代/03-AOS_-變數的四種性質.md) | `AOS_` 變數的四種性質（表）、`AOS_CLOCK`、`AOS_CLOCK_INTERVAL`、退路 |

<a id="aos-變數的四種性質11-04"></a>
