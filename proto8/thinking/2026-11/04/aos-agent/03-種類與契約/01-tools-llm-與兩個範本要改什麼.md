← [回入口 03-種類與契約.md](../03-種類與契約.md)｜段落：選配子介面總覽（`screen`／`tools`／`llm` 都怎麼宣告）、副本怎麼運作（改正在跑的那一隻）、`aos-tools`／`aos-llm` 改定義、eca 與 agent-fsm 各要改什麼｜上一份：—｜下一份：[02-子介面規格](02-子介面規格.md)

> 11-04 晚已改：`llm` 子介面改成設定檔宣告（`interfaces.json` 的 `"llm": "llm.json"`，aos-agent `llm` 是 aos-json 語法糖；`llm/` 入口、`aos-eca-llm`、Python `aos-llm` 退場），見 [think-as-function](../../think-as-function/README.md)（使用者 11-04 晚「然後aos llm,tool這兩個，我希望他們的定位是跟aos post一樣，作為基礎工具」）。本檔原字不動。

## 使用者 11-04 晚定的三句（原文在 [06 檔末](../06-衝突與方向題.md#使用者原文11-04-晚逐字toolsllm)）

「啊，還有，aos-agent tools/llm」→ 選「aos-agent 加兩個子命令」；對衝突 3「**改副本。改定義那塊用aos-tools**」；對方向題 3「**一個入口小程式。並且要是aos資料夾函數。可以設計宣告介面。**」；再補「**llm這塊也是，aos-agent llm改正在跑著的，aos-llm改定義**」。

所以兩層對稱：

| | 改**正在跑的那一隻**（stack 裡的副本） | 改**定義資料夾**（所有從它 add 的都變） |
|---|---|---|
| 工具箱 | `aos-agent tools --target bob …` → `$AOS_STACK/tools.json` | `aos-tools --file <定義>/tools.json …`（現成） |
| 腦 | `aos-agent llm --target bob …` → `$AOS_STACK/llm.json` | `aos-llm <定義> …`（新，`proto8/bin/aos-llm`，跟 aos-tools 並列） |

## 選配子介面總覽：值一律是「定義裡的一個資料夾程式」或「一個檔」

| 子介面 | 宣告（`interfaces.json` 裡 `aos-agent` 的值） | 宣告的東西是什麼 | 那隻身體要多守的一條 | 規格 |
|---|---|---|---|---|
| `screen` | `"screen": "screen"` | **資料夾程式** `<定義>/screen/`（有 `_entry`），自己宣告遵守介面 `aos-agent/screen` | 沒有 | [02 § screen](02-子介面規格.md#介面-aos-agentscreen) |
| `llm` | `"llm": "llm"` | **資料夾程式** `<定義>/llm/`，自己宣告遵守介面 `aos-agent/llm`；`def`／`stack` 兩個對象 | **讀腦設定時 `$AOS_STACK/llm.json` 有就用它蓋過定義的**（不是暗路，宣告 `llm` 就是承諾這條） | [02 § llm](02-子介面規格.md#介面-aos-agentllm) |
| `tools` | `"tools": "tools.json"` | **一個檔**：aos-tools 登記檔（兩邊同格式，不需要程式） | **找登記檔時 `$AOS_STACK/tools.json` 有就用它、沒有才用宣告的那份** | [02 § tools](02-子介面規格.md#子介面-tools副本規則不需要程式) |

**為什麼 `screen` 也改成資料夾程式**（使用者只說 llm 要是 aos 資料夾函數）：三個選配兩個是程式，一個檔一個資料夾會變成兩種寫法（C-54 一次記住）；資料夾程式才有地方放自己的 `interfaces.json` 宣告（C-71 入口之外都是其他元素），aos-agent 叫之前能確認「它說它遵守 `aos-agent/screen`」（宣告了卻沒做到＝`ScreenBad`，不是猜）；C-55 布局成長本來就是「檔長成資料夾」。`tools` 不用程式：登記檔格式已全體系通用，程式就是 aos-tools。

## 副本怎麼運作（fable 照原則定的，可翻案）

1. **位置固定**：`$AOS_STACK/tools.json`、`$AOS_STACK/llm.json`（stack 是那隻的地盤，宣告子介面＝同意這兩個名字；跟工具小格 `tools/` 同層不撞）。
2. **什麼時候建**：**第一次改的時候**（copy-on-write）——`aos-agent tools add／rm` 沒副本就先把宣告的登記檔複製進 stack（相對路徑一律改寫成絕對，因為 aos-tools 的相對路徑從登記檔所在資料夾算），再對副本做；`aos-agent llm set` 由 llm 入口程式寫 `llm.json`（只放改過的鍵）。`add` 時不建、`ls`／`show` 不建。｜C-56：沒人改就沒副本，零新檔；N-05 先寫暫存再改名。
3. **沒副本＝用定義的**：`tools ls`、`llm show` 印的是「定義的值被副本蓋過之後」的結果；stderr 一行列出哪些鍵來自副本（stdout 保持 `鍵=值`）。
4. **副本不跟定義**：定義後來被 `aos-tools`／`aos-llm` 改了，有副本的那隻照舊用副本——判準：**副本存在＝這隻自己的意見，人改定義是改「預設」**；要回去跟定義＝`aos-agent tools／llm --target bob reset`（刪副本）。另一案（副本只記差異、每次合併）在[方向題 4](../06-衝突與方向題/03-新題-tools-llm.md#方向題-4副本要不要跟著定義變)。
5. **生命週期跟 stack**：`stop`／`start` 留著；`rm` 刪 stack 就一起沒了；同名再 `add`（同一 stack）接著用。
6. **生效＝下一題**：fsm 每格起來才讀；eca 的 cli_session 每題起 CLI 前才讀。正在答的那題不受影響。

## eca 與 agent-fsm 各要改什麼（盡量少改；檔名與函數名給實作者）

| | agent-fsm（`demo/agent-fsm/`） | eca-claude（`demo/eca-claude/`＋`bin/aos-eca-turn`、`lib/agent/cli_session.py`） |
|---|---|---|
| 介面 1～6 | 零改動 | 零改動 |
| 宣告 | 新 `interfaces.json`：`{"aos-agent": {"tools": "tools.json", "llm": "llm"}}` | 新 `interfaces.json`：`{"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm"}}` |
| `screen` | 不做 → `ScreenMissing` | 新資料夾 `screen/`：`_entry`＝`["aos-eca-screen", ".."]`、`interfaces.json`＝`{"aos-agent/screen": {}}`；新 `bin/aos-eca-screen <eca 資料夾> open [-d]\|close\|watch`＝aos-eca 的 `cmd_open`／`cmd_close`／`cmd_watch`／`close_screen`／`Busy` 原樣搬，`it["cell"]`→`$AOS_STACK`、`it["ws"]`→`$AOS_WS`、`r["template"]`→位置參數 |
| `llm` | 新資料夾 `llm/`：`_entry`＝`["python3", "llm.py"]`、`interfaces.json`＝`{"aos-agent/llm": {}}`、`llm.py`（約 60 行）：`def` 對象讀寫 `../.env` 的 `AOS_BRAIN_URL`／`MODEL`／`KEY`（鍵 `url`／`model`／`key`）、`stack` 對象讀寫 `$AOS_STACK/llm.json` | 新資料夾 `llm/`：`_entry`＝`["aos-eca-llm", ".."]`、`interfaces.json` 同左；新 `bin/aos-eca-llm <eca 資料夾> def\|stack show\|set\|reset`：`def` 讀寫 `cli.json` `flags` 裡 `--model` 後面那格（鍵 `model`；`kind` 只印、`set kind=`＝`KeyUnknown`）、`stack` 讀寫 `$AOS_STACK/llm.json` |
| 身體讀副本：tools | `brain.py`、`act.py` 的 `tools_file`：沒給 `--tools` 時 `$AOS_STACK/tools.json` 在就用它、否則 `AOS_CD/tools.json`（各改一行） | `cli_session.load_cfg`（第 76～90 行那段）：算出登記檔之前先看 `$AOS_STACK/tools.json`，在就用它 |
| 身體讀副本：llm | `brain.py` 的 `ask`／`url`：讀 `$AOS_STACK/llm.json`（在才讀；壞 JSON＝`CfgBad`），`url`／`model`／`key` 蓋過環境變數 | `cli_session` 組 CLI 旗標處：`$AOS_STACK/llm.json` 有 `model` 就把 `flags` 裡的 `--model X` 換成它（沒有 `--model` 就加） |
| 退場時 | — | aos-eca-turn 不再寫 `eca.json`（P-43 加註）；aos-eca 的 open／close／watch 改叫 `aos-eca-screen`（過渡期），最後整支刪 |
