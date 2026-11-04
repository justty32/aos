← [回入口 03-種類與契約.md](../03-種類與契約.md)｜段落：選配子介面 `tools` 與 `llm`（使用者 11-04 晚追加）、改哪裡與什麼時候生效、eca 與 agent-fsm 各要改什麼｜上一份：—｜下一份：—

## 選配子介面 `tools`（工具箱）與 `llm`（腦）

使用者 11-04 晚：「啊，還有，aos-agent tools/llm」，頂層問意思，他選「aos-agent 加兩個子命令」（看／改它的工具箱、看／換它用的模型端點；原文在 [06 檔末](../06-衝突與方向題.md#使用者原文11-04-晚逐字toolsllm)）。工具箱與腦都不在必備六條裡（介面 `aos-agent` 不管腦是誰、工具怎麼接），所以照 `screen` 的做法：**要讓 aos-agent 看／改，就在 `interfaces.json` 宣告選配子介面**；沒宣告＝`ToolsMissing`／`LlmMissing`，aos-agent 不猜。

| 子介面 | 宣告 | aos-agent 子命令 | 底下是 | 為什麼這樣宣告 |
|---|---|---|---|---|
| `tools` | `"tools": "<登記檔相對定義資料夾>"`（兩個範本都是 `tools.json`） | `tools [ls\|add 名 路徑\|rm 名\|get 名]`；沒給動作＝`ls` | `aos-tools --file <定義>/<登記檔> ls／add／rm／get` 原樣轉（argv 介面） | 工具箱**已有全體系通用格式**（aos-tools 登記檔，兩邊同一份寫法，11-03 eca-tools），宣告檔在哪就夠；aos-agent 不懂格式、全交給 aos-tools |
| `llm` | `"llm": "<入口相對定義資料夾>"` | `llm [show\|set 鍵=值…]`；沒給動作＝`show` | `aos-exec --ws <ws> --stack <stack> <定義>/<入口> show`／`set 鍵=值…`（同 `screen` 的叫法） | 腦的設定**兩邊長得不一樣**（eca＝`cli.json` 的 `--model` 旗標＋CLI 種類；fsm＝`.env` 的 `AOS_BRAIN_URL`／`MODEL`／`KEY`），沒有共通格式，只能像 `screen` 一樣由那隻自己提供一支小程式。另一案「統一走 `.env`」在[方向題 3](../06-衝突與方向題/03-新題-tools-llm.md#方向題-3llm-走入口還是統一-env) |

**`llm` 入口的 argv 契約**：`show`→stdout 一行一個 `鍵=值`（至少要有 `model`；`key` 這類印 `***`）、退 0；`set 鍵=值…`→改定義裡對應的設定（N-05 先寫暫存再改名）、再印一次 show、退 0；不認得的鍵＝stderr 一行、退 1。aos-agent 只透傳 stdout／stderr，入口退非 0＝`LlmBad`（訊息帶它 stderr 那一行）。

## 改哪裡、什麼時候生效

- **改的是定義資料夾、不是 stack 裡的副本**：使用者 11-03「不應該有定義(template)這東西」——`add` 的 XXX 就是那隻 agent，工具箱與腦是它的一部分；stack 放的是執行狀態（C-65），裡面沒有登記檔或 `.env` 的副本可改（兩個範本每題都回定義讀）。**多隻共用同一份定義時一起變**：aos-agent 用 daemon 表的 `exec` 欄（方向題 1 裁定）找出同一定義的其他名字、stderr 提醒一行「ann、cat 也用這份定義」；要分開就複製一份定義再 `add`。這對上 P-15「定義資料夾不被寫；所以同一個 agent 可以同時被兩個工作區跑」→ [衝突 3](../06-衝突與方向題/03-新題-tools-llm.md#衝突-3toolsllm-改定義資料夾對上-p-15)。
- **生效＝下一題，不用 stop／start**：fsm 的 brain／act 每格都 `aos-tools ls`、每輪 `aos-exec fsm.json` 重讀 `.env`（`loop.json` 的 exec 是字串）；eca 的 cli_session 每題重讀 `cli.json`、重寫 `mcp.json`。例外：`.env` 預設不蓋外面已設的（N-59 第 4 件）——daemon 的環境已有 `AOS_BRAIN_URL` 時 `llm set url=…` 改了也沒用，fsm 的 `show` 要標 `(env 蓋住)`。
- 正在答的那題不受影響（它已經讀過了）。

## eca 與 agent-fsm 各要改什麼（盡量少改）

| | 介面 1～6 | 宣告 `interfaces.json` | `screen` | `tools` | `llm` |
|---|---|---|---|---|---|
| **agent-fsm**（[demo/agent-fsm](../../../../../demo/README.md#agent-fsm)） | 零改動 | `{"aos-agent": {"tools": "tools.json", "llm": "llm"}}` | 不做 → `ScreenMissing`（`listen --follow` 就是全貌） | 零改動（登記檔就是 `tools.json`） | 入口檔 `llm`＝`["python3", "llm.py"]`，範本多一支 `llm.py`：`show` 印 `url`／`model`／`key`（讀同層 `.env`，沒設的印外面環境的值並標 `(env)`）；`set` 改 `.env` 那一行 |
| **eca-claude**（[demo/eca-claude](../../../../../demo/README.md#eca-templates)＋[aos-eca-turn](../../../../../bin/README.md)） | 零改動（P-43「跟 aos agent 同形」） | `{"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm"}}` | ① 入口檔 `screen`＝`["aos-eca-screen", {"$env": "AOS_CD"}]`；② 新 `bin/aos-eca-screen`（aos-eca 的 `cmd_open`／`close`／`watch` 原樣搬，ws／stack 從 `AOS_WS`／`AOS_STACK`） | 零改動（`cli.json` 沒寫 `tools`＝同層 `tools.json`；寫了別處就宣告那個，不驗一致） | 入口檔 `llm`＝`["aos-eca-llm", {"$env": "AOS_CD"}]`；新 `bin/aos-eca-llm`：`show` 印 `kind=claude`、`model=sonnet`（`cli.json` `flags` 裡 `--model` 後面那個；沒有＝`model=`）；`set model=…` 改那格；`kind` 不給改（換 CLI 種類＝換一隻 agent） |
| 退場時 | — | — | `eca.json` 名片沒人讀了，拿掉（P-43 加註） | — | — |
