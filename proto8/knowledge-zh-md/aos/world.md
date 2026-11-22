# `knowledge/aos/world.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/world.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/world.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

**`#/How the pieces fit`**

# 各部分怎麼湊在一起

心裡的模型：daemon = 硬體，stack = 記憶體，工作區 = 外部記憶體，定義 = 原始碼，kernel = 你送請求去的地方。

把它想成一台小電腦：

| aos 用詞 | 像什麼 | 在哪裡 |
|---|---|---|
| daemon | 硬體；它跑 proc，並保管誰在跑的那張表 | `$AOS_DAEMON`（daemon 自己的 stack 資料夾） |
| stack | 一個在跑的 proc 的 RAM：它的狀態、對話歷史、信箱 | `$AOS_STACK` |
| 工作區（ws） | 你工作用的磁碟；其他 agent 拿到同一個 ws 時就共用 | `$AOS_WS` |
| 定義 | 程式的原始碼；執行它就做出一個實例（某個 daemon 底下的一個 stack）；它的檔案：`aos/definition.md` | agent 啟動時用的那個資料夾 |
| kernel | 資源管理和排程，從送出的人看：你把請求送到哪裡，那裡就是你的 kernel，它決定請求要不要跑、什麼時候跑；daemon 是最簡單的一種（叫它啟動什麼它就啟動什麼）；見 aos/kernel.md | `$AOS_KERNEL`（沒設：`$AOS_DAEMON` 裡的 daemon） |
| llm kernel | 回覆以信送來的腦請求；它以自己的 daemon 跑，或以會循環的 proc 跑在現有的 daemon 上（每一輪都是新的程序，會重讀它的設定；見 aos/cli/parts/llm_kernel.md） | `$AOS_LLM_KERNEL`（它的 stack；信送到 `$AOS_LLM_KERNEL/requests/`） |

從這個模型推出來的事實：

- 一個定義可以跑成很多個實例。每個實例有自己的 stack。改 stack 永遠不會改到定義。
- 不要手動改定義。要做新的，用 `agent_def`（它會先複製一份）。每個實例自己的改動（你的工具、你的腦設定）以「overlay」存在你的 stack 裡：只存差異。
- 一個 proc 永遠只在恰好一個 daemon 底下。「我的 daemon」就是 `$AOS_DAEMON` 裡那個。你啟動的子 agent 放在同一個 daemon 上。
- 一切都以檔案保存，所以 daemon 可以睡、連同它的 stack 和工作區被複製到別處，然後在那裡醒來。
- 替你設好的環境變數：`AOS_STACK`（你的 stack）、`AOS_DAEMON`（你的 daemon）、`AOS_WS`（你的工作區，有的話）、`AOS_HOME`（放 lib、範本和知識的資料夾：proto8 本身或它的複本；定義透過它找到工具）。有替你設定時：`AOS_LLM_KERNEL`、`AOS_KERNEL`、`AOS_CLOCK`、`AOS_CLOCK_INTERVAL`；由 `subagent` 或 `fork` 啟動的 agent 還有 `AOS_PARENT_STACK`（誰叫它來的），也可能有 `AOS_NOTIFY_BOX`（它的通知送去哪；子 agent 預設是父 agent 的信箱）；fork 有 `AOS_FORK_DEPTH`。工具還看得到 `AOS_CD`（它自己的資料夾），經由 aos-tools 呼叫時還有 `AOS_STACK_IN_CALLER`（工具自己的 stack 在呼叫的人的 stack 裡的位置，像 `tools/todo`）。不要自己發明別的。
- 工具印成 `$AOS_STACK/...` 的路徑（例如 `$AOS_STACK/tools/todo/todo.json`）是從你的 stack 算起：照寫的樣子打開。

**`#/Time`**

## 時間

- 這棵樹有一個時鐘，像板子上的晶振：設了 `AOS_CLOCK` 時，它指名一個檔案，裡面放一個整數，就是目前的週期。根 daemon 用它 `procs` 裡一個普通的 `_clock` 列推進它；子 daemon 通常沒有時鐘列，跟著根的時鐘走。
- proc 之間，等待用週期寫：`subagent` 的 ask 收 `timeout_cycles` 而不是 `timeout_s`（給一個，不要兩個都給）。有時鐘時，等待在那麼多個週期後結束；時鐘暫停或樹在睡時，時間不會走，等待也不會逾時。
- 沒有時鐘（沒設 `AOS_CLOCK`）：週期退回用真實時間，1 個週期 = `AOS_CLOCK_INTERVAL` ms（預設 1000）。這是給等待用的；`on_clock` hook 需要時鐘，沒有就不跑。
- 等人、等外部服務、等 Linux 程序，仍然用秒或毫秒。
- 計時器：時鐘信（工具 `clock_register`）會以訊息進到你的佇列；`on_clock` hook 只跑一個程式，不會在你的對話歷史裡加任何東西（agent 範本附了一個每 5 分鐘、什麼都不做的 `timer` hook，和一個告訴你有新信的 `mail_notify` hook）。見 aos/clock.md。
- 週期數只在同一棵樹裡能比較；寫給另一棵樹的信，用毫秒。
