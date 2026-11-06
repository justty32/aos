← [回入口 07-hub-型環境變數與父子交代.md](../07-hub-型環境變數與父子交代.md)｜段落：`AOS_` 變數的四種性質（11-04）｜上一份：[02-N-63-實例-AOS_DAEMON與沒有AOS_HUB](02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)

<a id="aos-變數的四種性質11-04"></a>

### `AOS_` 變數的四種性質（11-04）

使用者 11-04 題 2「寫一張表」（[four-elements 06](../../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)、[01 盤點](../../../../thinking/2026-11/04/four-elements/01-環境變數.md)）：`AOS_` 開頭的環境變數分四種，每個活變數歸一格；下次有人想加 `AOS_XXX`，先問「你是哪一種」。

**11-06 註（理由）**：使用者 11-05「aos體系下，唯一與json無關的，就是環境變數」，所以不要濫用環境變數（[json-argv 原文](../../../../thinking/2026-11/05/json-argv/README.md)）。

| 性質 | 是什麼 | 活的變數 |
|---|---|---|
| ① 執行環境 | aos-exec 每層設（N-57），全體讀 | `AOS_WS`、`AOS_STACK`（同時是 hub 的實例；只有 aos-exec 給預設）、`AOS_CF`、`AOS_CD`、`AOS_CO`（現在沒人讀）；`AOS_ENTRY` 是全樹繼承的旋鈕、使用者 11-01 裁留〔11-04 晚 `AOS_KERNEL_REPORT` 退場：用量改在回信的 `usage`（N-42 (1)）〕 |
| ② hub | 值是資料夾、沒設＝`<名字>Missing`、子 process 繼承（本條 ①～③） | `AOS_LLM_KERNEL`（11-05 起值＝llm kernel 的 stack）、`AOS_DAEMON`、`AOS_KERNEL`（11-05；沒設＝`$AOS_DAEMON` 的 ctl 信箱、不報 Missing，例外）、`AOS_MEMORY`（11-05；知識庫根，相對＝相對 `$AOS_DAEMON`；沒設＝`MemoryMissing`；工具資料夾的 `_memory.json` 蓋過它，[agent-knowledge 01](../../../../thinking/2026-11/05/agent-knowledge/01-層級式記憶工具.md)） |
| ③ 人殼預設 | 人在殼裡 export、程式之間不靠它傳（像 `EDITOR`） | `AOS_AGENT`（上面的例外） |
| ④ 旋鈕 | 原則上不走環境變數（刪、改 argv、改檔；使用者 11-01「除非真的有必要，否則不要用」）；真要走就帶 `AOS_`、寫在定義的 `.env` | 現無。（11-06 改讀：加 `AOS_TICK_INTERVAL`，已定、規劃中，見下註。）`AOS_HEAP`（`lib/aos/memory`）、`AOS_ROSTER`（`lib/aos/send_message`）11-04 已封存（使用者 11-04 晚「封存」），隨工具退場；`AOS_BRAIN_URL`／`AOS_BRAIN_MODEL`／`AOS_BRAIN_KEY` 11-04 晚退場（原本等 kernel 收、使用者 11-04「我再想想」；11-04 晚「brain url那塊我不喜歡，我希望llm呼叫，或者說思考，這本身也是用aos函數」：端點、模型、金鑰改放 `kernel.json` 的 `endpoints`，agent 只寫代號，P-23、[think-as-function](../../../../thinking/2026-11/04/think-as-function/README.md)） |

**11-06 註（`AOS_TICK`；已定；實作排在 T1、T7）**：使用者 11-05「好吧，看來得再加個環境變數：AOS_TICK。要參照哪個就去看這個。」（[fs-image](../../../../thinking/2026-11/05/fs-image/README.md)）——值＝要參照的時鐘檔路徑，子行程預設繼承；沒設＝退牆鐘、不報錯（[N-65](../../02-設計理念-時空.md)）；daemon 的 `tick` key 把它設給底下排在 T7（[tick-time 03](../../../../thinking/2026-11/05/tick-time/03-11-06-裁定與新設計.md)）。**歸哪一格還沒定**：不是 aos-exec 每層設的（不合 ①），值是檔不是資料夾、沒設也不報 Missing（不合 ② 與 N-63），先記在表外，待使用者看（[lift-to-norms](../../../../thinking/2026-11/06/lift-to-norms/README.md)）。

**11-06 註／改讀（④ 旋鈕；已定；實作排在 T1、T7）**：「現無」加上使用者特許的例外 `AOS_TICK_INTERVAL`＝一次 tick 大概多久的標稱默契（毫秒），只在退牆鐘與給人看換算時讀；使用者「我實在很不想再添加環境變數，但這太香了」（[fs-image](../../../../thinking/2026-11/05/fs-image/README.md)）。沒設＝1000 毫秒，**暫定：使用者說可再想**（[tick-time 03 原話](../../../../thinking/2026-11/05/tick-time/03-11-06-裁定與新設計.md)）；daemon 的 `tick.interval_ms` 不是 1000 時設給子樹、近的贏，使用者「設，近的贏」（[daemon-board 題 2](../../../../thinking/2026-11/06/daemon-board/README.md)）。
