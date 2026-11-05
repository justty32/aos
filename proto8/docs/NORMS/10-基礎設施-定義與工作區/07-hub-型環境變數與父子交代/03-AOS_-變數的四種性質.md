← [回入口 07-hub-型環境變數與父子交代.md](../07-hub-型環境變數與父子交代.md)｜段落：`AOS_` 變數的四種性質（11-04）｜上一份：[02-N-63-實例-AOS_DAEMON與沒有AOS_HUB](02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)

<a id="aos-變數的四種性質11-04"></a>

### `AOS_` 變數的四種性質（11-04）

使用者 11-04 題 2「寫一張表」（[four-elements 06](../../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)、[01 盤點](../../../../thinking/2026-11/04/four-elements/01-環境變數.md)）：`AOS_` 開頭的環境變數分四種，每個活變數歸一格；下次有人想加 `AOS_XXX`，先問「你是哪一種」。

| 性質 | 是什麼 | 活的變數 |
|---|---|---|
| ① 執行環境 | aos-exec 每層設（N-57），全體讀 | `AOS_WS`、`AOS_STACK`（同時是 hub 的實例；只有 aos-exec 給預設）、`AOS_CF`、`AOS_CD`、`AOS_CO`（現在沒人讀）；`AOS_ENTRY` 是全樹繼承的旋鈕、使用者 11-01 裁留〔11-04 晚 `AOS_KERNEL_REPORT` 退場：用量改在回信的 `usage`（N-42 (1)）〕 |
| ② hub | 值是資料夾、沒設＝`<名字>Missing`、子 process 繼承（本條 ①～③） | `AOS_LLM_KERNEL`（11-05 起值＝llm kernel 的 stack）、`AOS_DAEMON`、`AOS_KERNEL`（11-05；沒設＝`$AOS_DAEMON` 的 ctl 信箱、不報 Missing，例外） |
| ③ 人殼預設 | 人在殼裡 export、程式之間不靠它傳（像 `EDITOR`） | `AOS_AGENT`（上面的例外） |
| ④ 旋鈕 | 原則上不走環境變數（刪、改 argv、改檔；使用者 11-01「除非真的有必要，否則不要用」）；真要走就帶 `AOS_`、寫在定義的 `.env` | 現無。`AOS_HEAP`（`lib/aos/memory`）、`AOS_ROSTER`（`lib/aos/send_message`）11-04 已封存（使用者 11-04 晚「封存」），隨工具退場；`AOS_BRAIN_URL`／`AOS_BRAIN_MODEL`／`AOS_BRAIN_KEY` 11-04 晚退場（原本等 kernel 收、使用者 11-04「我再想想」；11-04 晚「brain url那塊我不喜歡，我希望llm呼叫，或者說思考，這本身也是用aos函數」：端點、模型、金鑰改放 `kernel.json` 的 `endpoints`，agent 只寫代號，P-23、[think-as-function](../../../../thinking/2026-11/04/think-as-function/README.md)） |
