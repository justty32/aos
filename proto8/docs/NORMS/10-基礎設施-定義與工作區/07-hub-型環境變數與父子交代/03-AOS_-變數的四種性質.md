← [回入口 07-hub-型環境變數與父子交代.md](../07-hub-型環境變數與父子交代.md)｜段落：`AOS_` 變數的四種性質（11-04）｜上一份：[02-N-63-實例-AOS_DAEMON與沒有AOS_HUB](02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)

<a id="aos-變數的四種性質11-04"></a>

### `AOS_` 變數的四種性質（11-04）

使用者 11-04 題 2「寫一張表」（[four-elements 06](../../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)、[01 盤點](../../../../thinking/2026-11/04/four-elements/01-環境變數.md)）：`AOS_` 開頭的環境變數分四種，每個活變數歸一格；下次有人想加 `AOS_XXX`，先問「你是哪一種」。

**11-06 註（理由）**：使用者 11-05「aos體系下，唯一與json無關的，就是環境變數」，所以不要濫用環境變數（[json-argv 原文](../../../../thinking/2026-11/05/json-argv/README.md)）。

| 性質 | 是什麼 | 活的變數 |
|---|---|---|
| ① 執行環境 | aos-exec 每層設（N-57），全體讀 | `AOS_WS`、`AOS_STACK`（同時是 hub 的實例；只有 aos-exec 給預設）、`AOS_CF`、`AOS_CD`、`AOS_CO`（現在沒人讀）；`AOS_ENTRY` 是全樹繼承的旋鈕、使用者 11-01 裁留〔11-04 晚 `AOS_KERNEL_REPORT` 退場：用量改在回信的 `usage`（N-42 (1)）〕 |
| ② hub | 值是資料夾、沒設＝`<名字>Missing`、子 process 繼承（本條 ①～③） | `AOS_CLOCK`（11-06；值＝時鐘檔路徑、沒設＝退牆鐘、不報 Missing，例外，跟 `AOS_KERNEL` 同類；來源＝根定義資料夾的 `.env`（或人 export），11-09；見表下註）、`AOS_LLM_KERNEL`（11-05 起值＝llm kernel 的 stack）、`AOS_DAEMON`、`AOS_KERNEL`（11-05；沒設＝`$AOS_DAEMON` 的 ctl 信箱、不報 Missing，例外）、`AOS_MEMORY`（11-05；知識庫根，相對＝相對 `$AOS_DAEMON`；沒設＝`MemoryMissing`；工具資料夾的 `_memory.json` 蓋過它，[agent-knowledge 01](../../../../thinking/2026-11/05/agent-knowledge/01-層級式記憶工具.md)） |
| ③ 人殼預設 | 人在殼裡 export、程式之間不靠它傳（像 `EDITOR`） | `AOS_AGENT`（上面的例外）；`AOS_HOME`（11-10 午 TC；值＝這台 proto8 資料夾的絕對路徑，每台設一次、改了值重起樹就生效；沒有程式直接讀它，只在定義檔寫成指示詞 `{"$env": "AOS_HOME", "$path": "/lib/…"}` 時由解指示詞的那一層讀，沒設＝那一層的 `DirectiveBad`；範本一律寫這種、`cp -r` 抄出去就能用（11-10 templates-cp，使用者「copy-out能刪就刪」；根範本 `.env` 帶 `AOS_HOME=${AOS_HOME}` 必填檢查），[templates/docs/02](../../../../templates/docs/02-agent-fsm.md)；使用者 11-10「使用者自己準備。要用相對位置、絕對位置、環境變數指定都可」） |
| ④ 旋鈕 | 原則上不走環境變數（刪、改 argv、改檔；使用者 11-01「除非真的有必要，否則不要用」）；真要走就帶 `AOS_`、寫在定義的 `.env` | 現無。（11-06 改讀：加 `AOS_CLOCK_INTERVAL`，已定、規劃中，見下註。）（11-06 註：已實作——T1 讀；11-09 起跟 `AOS_CLOCK` 一樣寫在根定義資料夾的 `.env`，daemon 不再往下傳。）`AOS_HEAP`（`lib/aos/memory`）、`AOS_ROSTER`（`lib/aos/send_message`）11-04 已封存（使用者 11-04 晚「封存」），隨工具退場；`AOS_BRAIN_URL`／`AOS_BRAIN_MODEL`／`AOS_BRAIN_KEY` 11-04 晚退場（原本等 kernel 收、使用者 11-04「我再想想」；11-04 晚「brain url那塊我不喜歡，我希望llm呼叫，或者說思考，這本身也是用aos函數」：端點、模型、金鑰改放 `kernel.json` 的 `endpoints`，agent 只寫代號，P-23、[think-as-function](../../../../thinking/2026-11/04/think-as-function/README.md)） |

**11-06 註（`AOS_CLOCK`；T1 讀的那半已實作，[tick-time 04](../../../../thinking/2026-11/05/tick-time/04-T線實作結果.md)；誰給它 11-09 改讀）**：使用者 11-05「好吧，看來得再加個環境變數：AOS_TICK。要參照哪個就去看這個。」（[fs-image](../../../../thinking/2026-11/05/fs-image/README.md)）——值＝要參照的時鐘檔路徑，子行程預設繼承；沒設＝退牆鐘、不報錯（[N-65](../../02-設計理念-時空.md)）；**來源＝根定義資料夾的 `.env` 一行 `AOS_CLOCK=${AOS_STACK}/clock`（或人 export）**，底下照繼承；daemon 程式不設它（11-09 clock-decouple 拿掉 `clock` key，使用者裁「拿掉，走 B」，[thinking clock-decouple](../../../../thinking/2026-11/09/clock-decouple/README.md)）。子 daemon 預設**聽外層**：`.env` 不蓋已有的 `AOS_CLOCK`，要用自己的鐘由掛它的那列加 `--dotenv-override`（使用者 11-09「預設聽外層」，翻 11-06「設，近的贏」）。**歸 ② hub、當例外**（使用者 11-06 選「跟 AOS_KERNEL 同類 (Recommended)」，[lift-to-norms](../../../../thinking/2026-11/06/lift-to-norms/README.md)）：跟 `AOS_KERNEL` 沒設有退路同類——值是檔不是資料夾、沒設不報 Missing、退回牆鐘。

**11-06 註／改讀（④ 旋鈕；T1 讀的那半已實作，[tick-time 04](../../../../thinking/2026-11/05/tick-time/04-T線實作結果.md)；誰給它 11-09 改讀）**：「現無」加上使用者特許的例外 `AOS_CLOCK_INTERVAL`＝一格大概多久的標稱默契（毫秒），只在退牆鐘與給人看換算時讀；使用者「我實在很不想再添加環境變數，但這太香了」（[fs-image](../../../../thinking/2026-11/05/fs-image/README.md)）。沒設＝1000 毫秒，**暫定：使用者說可再想**（[tick-time 03 原話](../../../../thinking/2026-11/05/tick-time/03-11-06-裁定與新設計.md)）；頻率不是 1000 才在根定義資料夾的 `.env` 另寫 `AOS_CLOCK_INTERVAL`，跟鐘列的 `interval_ms` 同值、不檢查（11-09 改讀，[thinking clock-decouple](../../../../thinking/2026-11/09/clock-decouple/README.md)）。

**11-06 註（K3；使用者 11-06 選項框「統一成 K3 (Recommended)」）**：② hub 的「沒設＝`<名字>Missing`」改讀成「沒設＝`<名字>Missing`，或在本表那一列寫明唯一一條退路」；設了但指不到時**不改原本行為**（`AOS_CLOCK`＝當第 0 格；`AOS_KERNEL`＝照用那個信箱），只多印一行 `warning:`（[env-portability](../../../../thinking/2026-11/06/env-portability/README.md) Q5 已裁，選項原文「不報錯、不改退路」）；退路只管「沒設」。（**11-07 sol 審查 #8 改**：原寫「設了但指不到時照退路走」，照字面會把指錯的時鐘當沒時鐘、退牆鐘，跟 Q5 與 `AOS_CLOCK` 缺檔＝第 0 格相反。使用者 11-07 裁定：aos-agent 走的 Python `mailbox_of` 在 `AOS_KERNEL` 指不到時維持報 `MailboxMissing`；沒有退路，不退到 daemon 信箱繞過判官。（11-07 使用者裁定 sol 審查 #8））現有三條退路照本句成立、不再各算例外：`AOS_CLOCK` 沒設退牆鐘、`AOS_KERNEL` 沒設＝`$AOS_DAEMON` 的 ctl 信箱、`AOS_DAEMON` 沒設找 `./.stack`（[02](02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)）；第四個要退路的照這句在表上那一列寫就好（[special-cases](../../../../thinking/2026-11/06/special-cases/README.md#使用者裁定11-06選項框)）。

**11-06 E2 時鐘半已實作（R 隊）**：`AOS_CLOCK` 設了但缺檔時，C++ 與 Python 共用入口印英文 `warning:`（每行程每路徑一次），仍沿用缺檔＝0、不建檔的行為；空白檔＝0 不提醒。沒設仍退牆鐘。~~`AOS_KERNEL` 的 warning 半另排 E2~~（11-07 註：已實作，`proto8/impls/aos-llm-kernel/src/daemon/daemon.cpp`；aos-agent 這一路照 sol 審查 #8 維持 `MailboxMissing`）。
