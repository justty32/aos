← [回入口 03-種類與契約.md](../03-種類與契約.md)｜段落：選配子介面總覽、副本怎麼運作（改正在跑的那一隻）、eca 與 agent-fsm 改了什麼｜上一份：—｜下一份：[02-子介面規格](02-子介面規格.md)

## 使用者 11-04 晚定的三句（原文在 [06](../06-衝突與方向題.md#使用者原文11-04-晚逐字toolsllm)）

「啊，還有，aos-agent tools/llm」→ 選「aos-agent 加兩個子命令」；對衝突 3「**改副本。改定義那塊用aos-tools**」；對方向題 3「**一個入口小程式。並且要是aos資料夾函數。可以設計宣告介面。**」；再補「**llm這塊也是，aos-agent llm改正在跑著的，aos-llm改定義**」。

`llm` 的做法同晚照使用者「然後aos llm,tool這兩個，我希望他們的定位是跟aos post一樣，作為基礎工具」改成設定檔宣告：`interfaces.json` 寫 `"llm": "llm.json"`，aos-agent `llm` 讀寫 stack 裡的副本、沒有入口程式；改定義＝人直接改定義裡的 `llm.json`（[think-as-function 03 § 4](../../think-as-function/03-呼叫端.md)）。

兩層對稱：

| | 改**正在跑的那一隻**（stack 裡的副本） | 改**定義資料夾**（所有從它 add 的都變） |
|---|---|---|
| 工具箱 | `aos-agent tools --target bob …` → `$AOS_STACK/tools.json` | `aos-tools --file <定義>/tools.json …` |
| 腦 | `aos-agent llm --target bob …` → `$AOS_STACK/llm.json` | 改 `<定義>/llm.json`（think-as-function 03 § 4） |

## 選配子介面總覽

| 子介面 | 宣告（`interfaces.json` 裡 `aos-agent` 的值） | 宣告的東西是什麼 | 那隻身體要多守的一條 | 規格 |
|---|---|---|---|---|
| `screen` | `"screen": "screen"` | **資料夾程式** `<定義>/screen/`（有 `_entry`），自己宣告遵守介面 `aos-agent/screen` | 沒有 | [02 § screen](02-子介面規格.md#介面-aos-agentscreen) |
| `llm` | `"llm": "llm.json"` | **一個檔**：定義裡的腦設定 | **讀腦設定時 `$AOS_STACK/llm.json` 有的鍵蓋過定義的**（宣告 `llm` 就是承諾這條） | think-as-function 03 § 4 |
| `tools` | `"tools": "tools.json"` | **一個檔**：aos-tools 登記檔 | **找登記檔時 `$AOS_STACK/tools.json` 有就用它、沒有才用宣告的那份** | [02 § tools](02-子介面規格.md#子介面-tools副本規則不需要程式) |

## 副本怎麼運作（fable 照原則定的，可翻案）

1. **位置固定**：`$AOS_STACK/tools.json`、`$AOS_STACK/llm.json`（宣告子介面＝同意這兩個名字）。
2. **什麼時候建**：**第一次改的時候**（copy-on-write）——`aos-agent tools add／rm` 沒副本就先把宣告的登記檔複製進 stack（相對路徑一律改寫成絕對），再對副本做；`llm.json` 只放改過的鍵。`add` 時不建、看的時候不建（C-56；N-05 先寫暫存再改名）。
3. **沒副本＝用定義的**：看的時候印「定義的值被副本蓋過之後」的結果；stderr 一行說哪些來自副本。
4. **副本不跟定義**：定義後來改了，有副本的那隻照舊用副本——**副本存在＝這隻自己的意見，人改定義是改「預設」**；要回去跟定義＝`aos-agent tools／llm --target bob reset`（刪副本）。使用者裁「不跟。風險自行處理。但我們可以給reset。」（[06/03](../06-衝突與方向題/03-新題-tools-llm.md#方向題-4副本要不要跟著定義變)）
5. **生命週期跟 stack**：`stop`／`start` 留著；`rm` 刪 stack 就一起沒了；同名再 `add`（同一 stack）接著用。
6. **生效＝下一題**：fsm 每格起來才讀；eca 每題起 CLI 前才讀。正在答的那題不受影響。

## eca 與 agent-fsm 改了什麼（11-04 已實作）

- 介面 1～6 兩邊零改動；各加 `interfaces.json`（內容見 [03](../03-種類與契約.md#agent-怎麼宣告定義資料夾裡一份-interfacesjson)）。
- eca-claude：新資料夾 `screen/`（`_entry` 叫 `aos-eca-screen`、`interfaces.json`＝`{"aos-agent/screen": {}}`）；`bin/aos-eca-screen` 是 aos-eca 的 open／close／watch 搬過去（stack＝`$AOS_STACK`、工作區＝`$AOS_WS`）；aos-eca-turn 不再寫 `eca.json`（P-43 加註）。agent-fsm 不做 screen（＝`ScreenMissing`）。
- 兩邊身體找登記檔時 `$AOS_STACK/tools.json` 在就用它；讀腦設定時 `$AOS_STACK/llm.json` 有的鍵蓋過定義。
