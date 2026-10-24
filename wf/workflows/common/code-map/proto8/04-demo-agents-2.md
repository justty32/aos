← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 agent-kai、agent-liv、agent-meg、agent-pip、`kernel-llm/agent-ivy`（10-24）｜上一份：[04-demo-agents](04-demo-agents.md)（agent-eve、fay、gus、hal）

> 2026-10-24 收尾補（各 agent 做的時候沒改 code map）。「同 agent-dan」的意思、babdaad2 那一行，見上一份開頭。

### agent-kai

按意圖組 context：history 照存，問腦時只送這題用得到的。[thinking](../../../../../proto8/thinking/2026-10-24-intent-context.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`.env`、`idle/` | 同 agent-dan |
| `tools/math`、`tools/clock` | 符號連結 → `../../../lib/base/<名>`（10-24 遷移前是 agent-dan 的複本） |
| `brain.py` | 組 context：system＋先前對話目錄＋〔有 `tools/memory` 就附記憶〕＋挑出的舊題（只有問與結論）＋這題完整；整份 ≤ `KAI_FULL_UNDER`（1500 token）就全送；每次記一行 `$AOS_STACK/context.jsonl` |
| `act.py` | 同 agent-dan，多給工具 `RECALL_HISTORY`＝自己的 `history.jsonl` |
| `system.txt` | 告訴腦看到的不是全部、不夠就 recall 或重查、回答把關鍵寫完整 |
| `tools/recall/_entry`、`tool.json` | `op`＝search（關鍵字找舊題）／read（展開一題，`detail` 連工具原始輸出）；錯 `HistoryMissing`、`HistoryBad` |
| `tools/recall/turns.py` | 把 history 切成題、照意圖挑（上一題、指代詞、「第 N 題」、字面重疊）；brain 也 import |
| `tools/read` | 符號連結 → `../../../lib/base/read`（10-24 遷移前指 demo/pi-tools/read） |

### agent-liv

工具引用 [proto8/lib](../../../../../proto8/lib/README.md) 的函式庫，不複製。[thinking](../../../../../proto8/thinking/2026-10-24-tool-lib.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`.env`、`idle/` | 同 agent-dan |
| `act.py` | 同 agent-pip（10-24 真腦實測改）：工具退非 0、叫了沒有的工具、arguments 壞都接成 tool 訊息回給腦，不停 |
| `tools/clock/` | 自己的真資料夾（agent-dan 的複本）：庫裡也有 `clock`，同名自己的贏——示範覆寫 |
| `brain.py` | 同 agent-dan，假腦改叫一次 `ls`、答 `（ls said: N items）` |
| `system.txt` | 教腦哪件事用哪個工具 |
| `_metainfo` | 這隻 agent 的特性（summary、time_ms、resource、llm_calls…；_metainfo 規劃的範例 2） |
| `tools/read`、`write`、`edit`、`bash`、`ls`、`json_read`、`json_edit` | 七條符號連結 → `../../../lib/base/<名>`（庫的工具出錯回給腦，見 `act.py`） |

### agent-meg

記憶庫（heap）：stack 清空了，記得的事還在。[thinking](../../../../../proto8/thinking/2026-10-24-memory.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/` | 同 agent-dan |
| `act.py` | 同 agent-dan |
| `.env` | 模型名；說明 `AOS_HEAP`（沒設＝`$AOS_WS/.heap/`，指同一個＝共用） |
| `brain.py` | 同 agent-dan，多一件：問腦前把偏好全部＋跟題目有關的幾筆接在 system 後面（不進 history）；庫壞＝`HeapBad`；假腦附上記憶字數 |
| `system.txt` | 教腦什麼該存、只存確認過的、衝突以現在說的為準 |
| `tools/memory` | 符號連結 → `../../../lib/aos/memory`（10-24 遷移；`_entry`、`tool.json`、`_metainfo`、`heap.py` 都在庫裡，見 [06-周邊工具](06-周邊工具.md)）；brain 照舊從 `tools/memory` import `heap` |

### agent-pip

coding agent，工具全部掛 [proto8/lib](../../../../../proto8/lib/README.md) 的 base（10-24 遷移前掛 demo/pi-tools 與 demo/file-tools）。[thinking](../../../../../proto8/thinking/2026-10-24-pi-tools.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`.env`、`idle/` | 同 agent-dan |
| `loop.json`、`fsm.json` | max 200；think 180 秒、act 15 分鐘 |
| `brain.py` | 同 agent-dan，假腦改叫一次 `bash`（`ls`） |
| `act.py` | 工具退非 0、沒有這個工具、arguments 不是 JSON，都接成一則 tool 訊息回給腦、不停（原本跟 agent-dan 差這一條，10-24 晚起 agent-dan 也這樣） |
| `system.txt` | 照 pi 的精神寫的短版，列各工具看／改的用途 |
| `tools/*` | 十二條符號連結 → `../../../lib/base/<名>`：`read`、`write`、`edit`、`bash`、`ls`、`stat`、`view`、`json_edit`、`mkdir`、`move`、`copy`、`trash` |

### kernel-llm/agent-ivy

走 LLM kernel 的 ann 式 agent（零子資料夾的全內嵌寫法）；`kernel-llm/` 本身見入口那句。[thinking](../../../../../proto8/thinking/2026-10-24-llm-kernel.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json` | `exec aos-loop loop.json`；`loop.json` 的 `exec` 是單子 `aos-fsm fsm.json`、max 20 |
| `.env` | `AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low`（同 agent-dan，不蓋外面的；10-24 真腦實測加，沒這份時送 `default`） |
| `fsm.json` | 沒有 `_entry`；idle／act 跑 python，think 的 `exec`＝`aos-gate $BRAIN`、stdout 導到 `$AOS_STACK/plan.txt`、120 秒 |
| `idle.py` | `cur/` 或 `new/` 有題退 0，沒有退 10 |
| `brain.py` | 經 kernel 才跑：認領題目、答案草稿印 stdout；假腦睡 1 秒；有 `AOS_KERNEL_REPORT` 就寫 usage（假腦用字數編） |
| `act.py` | `plan.txt` 寫成 `out/<題名>`、題目搬 `done/` |
| `brains/plain.json`、`quick.json`、`urgent.json` | 腦的單子（`cwd` ..）：normal；normal＋`_metainfo.time_ms` 800；high＋5000 |
