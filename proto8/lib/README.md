# proto8/lib — aos agent 的函式庫（腦可以叫的工具，收成一份、被引用）

**lib - agent 跑的時候會呼叫的外部函數，收成一份標準版，掛捷徑引用、不複製**

← [proto8](../README.md)｜設計、盤點、代定與遷移清單：[thinking 2026-10-24 工具＝函式庫](../thinking/2026-10/24/tool-lib/README.md)｜慣例：[P-41、P-25](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-33](../docs/CONVENTION/06-巢狀/01-P-33～P-34.md)｜特性：[`_metainfo`](../thinking/2026-10/24/metainfo/README.md)｜範例 agent：agent-eve（11-04 隨 proto8/tests 刪了）

使用者 10-24：「我們在做工具集，這其實挺像是在做函式庫。因爲agent是函數，我們給他的工具就是他在內部自己跑的時候會呼叫的外部函數。既然是這樣，那我們就要把抽象做好，把函數庫做好」——agent 是函數（一個資料夾，C-46、C-68），它 `tools/<名>/` 裡的東西是它內部呼叫的外部函數（C-42、C-61）。這裡把那些外部函數收成一份。`lib` 不 import 上層 `py`；工具輸出共用 `tool_io.py`，CLI 對話與介面宣告的共用模組在 `agent/`（`cli_session.py`、`agent_files.py`；11-06 晚 K-5）。

共用記帳 [`observed.py`](observed.py) 提供 `append(stack, record)`（失敗提醒）、`append_strict(stack, record)`（失敗拋出）與 `prepare_strict(stack)`（先初始化並開啟帳本，供執行前預檢）；首次寫入會補 `self` 行與 stack 的 `aos-observed` 介面。`call(name, target, stdin, stack=None)` 用工具小格呼叫 `aos-exec`、記時間與位元組，回傳 `(code, stdout_bytes, stderr_bytes)`；沒設 `AOS_STACK` 就照跑不記。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-分層等](docs/01-分層等.md) | 分層（每層只依賴下層）；一個工具長什麼樣（契約）；怎麼引用（不複製） |
| [02-索引-base與索引-aos](docs/02-索引-base與索引-aos.md) | 索引：base；索引：aos（aos_json、判官 judge、measure、promote／rollback、watch／review_round） |
| [03-索引-agent等](docs/03-索引-agent等.md) | 索引：agent（11-05 加 self_tools：agent 改自己的工具；agents：agent 生、叫、收另一隻 agent）；agent 自己的格（11-03 刪了）；外部 agent 的一輪（eca）；範例（demo/agent-liv 11-04 刪了） |

<a id="分層每層只依賴下層"></a>
<a id="一個工具長什麼樣契約"></a>
<a id="怎麼引用不複製"></a>
<a id="索引base"></a>
<a id="索引aos"></a>
<a id="索引agent"></a>
<a id="agent-自己的格11-03-刪了"></a>
<a id="外部-agent-的格eca不是工具"></a>
<a id="外部-agent-的一輪eca"></a>
<a id="範例demoagent-liv-11-04-刪了"></a>
<a id="測試"></a>

`thought` 與 `agents` 的 `ask` 支援 `timeout_ticks`（與 `timeout_s` 擇一）；沒設 `AOS_TICK` 時，1 tick＝`AOS_TICK_INTERVAL` 毫秒，預設 1000。有時鐘時停鐘不會讓 tick 期限到期；詳見 [agent 工具索引](docs/03-索引-agent等.md)。

`memory read` 的 `path` 可寫 `節點#/JSON/Pointer`（RFC6901），只對 `.json` 葉取值；一般節點讀取方式見 [memory 說明](agent/memory/README.md)。
