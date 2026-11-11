# proto8/lib — aos agent 的函式庫（腦可以叫的工具，收成一份、被引用）

**lib - agent 跑的時候會呼叫的外部函數，收成一份標準版，掛捷徑引用、不複製**

← [proto8](../README.md)｜設計、盤點、代定與遷移清單：[thinking 2026-10-24 工具＝函式庫](../thinking/2026-10/24/tool-lib/README.md)｜慣例：[P-41、P-25](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-33](../docs/CONVENTION/06-巢狀/01-P-33～P-34.md)｜特性：[`_metainfo`](../thinking/2026-10/24/metainfo/README.md)｜範例 agent：agent-eve（11-04 隨 proto8/tests 刪了）

使用者 10-24：「我們在做工具集，這其實挺像是在做函式庫。因爲agent是函數，我們給他的工具就是他在內部自己跑的時候會呼叫的外部函數。既然是這樣，那我們就要把抽象做好，把函數庫做好」——agent 是函數（一個資料夾，C-46、C-68），它 `tools/<名>/` 裡的東西是它內部呼叫的外部函數（C-42、C-61）。這裡把那些外部函數收成一份。`lib` 不 import 上層 `py`；工具輸出共用 `tool_io.py`，CLI 對話與介面宣告的共用模組在 `agent/`（`cli_session.py`、`agent_files.py`；11-06 晚 K-5）。

共用記帳 [`observed.py`](observed.py) 提供 `append(stack, record)`（失敗提醒）、`append_strict(stack, record)`（失敗拋出）與 `prepare_strict(stack)`（先初始化並開啟帳本，供執行前預檢）；首次寫入會補 `self` 行與 stack 的 `aos-observed` 介面。`call(name, target, stdin, stack=None)` 用工具小格呼叫 `aos-exec`、記時間與位元組，回傳 `(code, stdout_bytes, stderr_bytes)`；沒設 `AOS_STACK` 就照跑不記。提醒行的程式名（11-10 坑-88）：`append`／`call` 可給選填 `prog`；沒給＝叫過 `tool_io.start(名)` 的工具用那個名（measure、watch、review_round、judge-llm…），都沒有＝`agent-fsm`（四格）。[`observed_children.py`](observed_children.py) 的 `copy_child` 跳過讀不了、宣告壞或指到子 stack 外的子帳時，用同一個名字印一行 `名: warning: skipped child observations declared in …`（11-10 open-16；原本安靜跳過）。

給 AI 寫新工具用 [`tool_spec.py`](tool_spec.py)（11-10 深夜 [tools-def](../thinking/2026-11/10/tools-def/README.md)）：一支 Python 裡宣告說明、參數（`ts.param`）、特性（`META`）和 `run(args)`，它產 `_tooldef`／`_metainfo`（資料夾的兩個檔，或 JSON 物件的兩個鍵）、執行時接 `tool_io` 驗參數；骨架在 [`templates/tool-python`](../templates/tool-python/README.md)，腦用 [`tools_def`](agent/tools_def/) 的 `new`／`check`。現有工具不必遷移。

跨 kernel 的問腦轉交用 [`aos/llm_forward`](aos/llm_forward/README.md)：下一層位置寫在包的 `kernel`，成功用 `child` 串起兩本帳，失敗透明轉交。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-分層等](docs/01-分層等.md) | 分層（每層只依賴下層）；一個工具長什麼樣（契約）；怎麼引用（不複製） |
| [02-索引-base與索引-aos](docs/02-索引-base與索引-aos.md) | 索引：base；索引：aos（量測、換版、審視、shell 帳與關箱比對、定義樹） |
| [03-索引-agent等](docs/03-索引-agent等.md) | 索引：agent（11-05 加 self_tools：agent 改自己的工具；11-10 晚 agents 拆成三支（11-11 第一支改名 subagent）：subagent 生、叫、調、收自己的子 agent，agents_ctl 管表上任何一隻，agent_def 造新定義與檢查）；agent 自己的格（11-03 刪了）；外部 agent 的一輪（eca）；範例（demo/agent-liv 11-04 刪了） |

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

`subagent` 的 `ask`／`listen` 支援 `timeout_cycles`（與 `timeout_s` 擇一）；沒設 `AOS_CLOCK` 時，1 cycle＝`AOS_CLOCK_INTERVAL` 毫秒，預設 1000。有時鐘時停鐘不會讓時鐘期限到期；詳見 [agent 工具索引](docs/03-索引-agent等.md)。

`knowledge_read read` 的 `path` 寫統一路徑 `資料夾/檔.json#/JSON/Pointer`（RFC6901，帶副檔名；出廠根是 `knowledge/`，例 `aos/me.json#/self_tools`）；工具 tooldef 指向知識節點一律寫 `Details: knowledge_read aos/路徑.`；一般節點讀取方式見 [knowledge_read 說明](agent/knowledge_read/README.md)。
