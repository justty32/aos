← [回入口 07-hub-型環境變數與父子交代.md](../07-hub-型環境變數與父子交代.md)｜段落：`AOS_` 變數的四種性質（11-04）｜上一份：[02-N-63-實例-AOS_DAEMON與沒有AOS_HUB](02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)

<a id="aos-變數的四種性質11-04"></a>

### `AOS_` 變數的四種性質（11-04）

使用者 11-04 題 2「寫一張表」（[four-elements 06](../../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)）：`AOS_` 開頭的環境變數分四種，每個活變數歸一格；下次有人想加 `AOS_XXX`，先問「你是哪一種」。不要濫用環境變數：使用者 11-05「aos體系下，唯一與json無關的，就是環境變數」（[json-argv 原文](../../../../thinking/2026-11/05/json-argv/README.md)）。

| 性質 | 是什麼 | 活的變數 |
|---|---|---|
| ① 執行環境 | aos-exec 每層設（N-57），全體讀 | `AOS_WS`、`AOS_STACK`（同時是 hub 的實例；只有 aos-exec 給預設）、`AOS_CF`、`AOS_CD`、`AOS_CO`（現在沒人讀）；`AOS_ENTRY` 是全樹繼承的旋鈕、使用者 11-01 裁留；`AOS_STACK_IN_CALLER`（`aos-tools call` 每次叫工具時設、不是 aos-exec 設：值＝工具的小格在叫方 stack 裡的相對位置 `tools/<登記名>`，只給工具把自己小格裡的路徑印成叫方找得到的 `$AOS_STACK/tools/<登記名>/…` 用；父沒設 `AOS_STACK`＝不給，沒給＝工具照自己的小格印；使用者 11-13 裁 fx-2:A「全家一起改」，變數名、給相對位置、歸這一格都是代定、可翻案，[tool-stack-path](../../../../thinking/2026-11/13/tool-stack-path.md)） |
| ② hub | 值是資料夾、沒設＝`<名字>Missing` 或本列寫明的唯一退路、子 process 繼承（N-63 ①～③） | `AOS_CLOCK`（值＝時鐘檔路徑，不是資料夾；退路：沒設＝退牆鐘；來源＝根定義資料夾的 `.env`（或人 export）；見表下）、`AOS_LLM_KERNEL`（值＝llm kernel 的 stack）、`AOS_DAEMON`（退路：沒設＝找 cwd 的 `./.stack`）、`AOS_KERNEL`（退路：沒設＝`$AOS_DAEMON` 的 ctl 信箱） |
| ③ 人殼預設 | 人在殼裡 export、程式之間不靠它傳（像 `EDITOR`） | `AOS_AGENT`（N-63 的例外）；`AOS_HOME`（值＝放 lib、templates、knowledge 的那個資料夾的絕對路徑，可以是 proto8 本身或它的抄本（使用者 11-13「em-Q1:B」，[eca-main-six-fixes](../../../../thinking/2026-11/13/eca-main-six-fixes.md#要使用者裁的題)）；每台設一次、改了值重起樹就生效；aos 的指令一律從 PATH 找、不經它；沒有程式直接讀它，只在定義檔寫成指示詞 `{"$env": "AOS_HOME", "$path": "/lib/…"}` 時由解指示詞的那一層讀，沒設＝那一層的 `DirectiveBad`；範本一律寫這種、`cp -r` 抄出去就能用（使用者「copy-out能刪就刪」；根範本 `.env` 帶 `AOS_HOME=${AOS_HOME}` 必填檢查），[templates/docs/02](../../../../templates/docs/02-agent-fsm.md)；使用者 11-10「使用者自己準備。要用相對位置、絕對位置、環境變數指定都可」）；`AOS_LINUX_USER_STACK`（值＝人自己的 stack，aos-mailbox 的信箱在它的 `mailbox/`；順序 `-s` ＞ `$AOS_LINUX_USER_STACK` ＞ `~/.aos/stack`；使用者 11-10「4.改$AOS_LINUX_USER_STACK。」，[tonight-rulings](../../../../thinking/2026-11/10/tonight-rulings/README.md) 題 4；預設位置使用者 11-11 裁「改成帶 aos 字樣的位置」，[mailbox 01](../../../../thinking/2026-11/10/mailbox/01-設計.md)；歸這一格是代定、可翻案，[mailbox 01](../../../../thinking/2026-11/10/mailbox/01-設計.md)） |
| ④ 旋鈕 | 原則上不走環境變數（刪、改 argv、改檔；使用者 11-01「除非真的有必要，否則不要用」）；真要走就帶 `AOS_`、寫在定義的 `.env` | 只有使用者特許的 `AOS_CLOCK_INTERVAL`（見表下） |

**`AOS_CLOCK`**：使用者 11-05「好吧，看來得再加個環境變數：AOS_TICK。要參照哪個就去看這個。」（[fs-image](../../../../thinking/2026-11/05/fs-image/README.md)；原話的 `AOS_TICK` 現在叫 `AOS_CLOCK`，[附錄3](../../附錄3-舊名對照.md)）——值＝要參照的時鐘檔路徑，子行程預設繼承；沒設＝退牆鐘、不報錯（[N-65](../../02-設計理念-時空.md)）；**來源＝根定義資料夾的 `.env` 一行 `AOS_CLOCK=${AOS_STACK}/clock`（或人 export）**，底下照繼承；daemon 程式不設它（使用者 11-09 裁「拿掉，走 B」，[thinking clock-decouple](../../../../thinking/2026-11/09/clock-decouple/README.md)）。子 daemon 預設**聽外層**：`.env` 不蓋已有的 `AOS_CLOCK`，要用自己的鐘由掛它的那列加 `--dotenv-override`（使用者 11-09「預設聽外層」）。**歸 ② hub**（使用者 11-06 選「跟 AOS_KERNEL 同類 (Recommended)」，[lift-to-norms](../../../../thinking/2026-11/06/lift-to-norms/README.md)）：跟 `AOS_KERNEL` 一樣沒設有退路——值是檔不是資料夾、沒設不報 Missing、退回牆鐘。

**`AOS_CLOCK_INTERVAL`（④ 旋鈕的特許）**：一格大概多久的標稱默契（毫秒），只在退牆鐘與給人看換算時讀；使用者「我實在很不想再添加環境變數，但這太香了」（[fs-image](../../../../thinking/2026-11/05/fs-image/README.md)）。沒設＝1000 毫秒，**暫定：使用者說可再想**（[tick-time 03 原話](../../../../thinking/2026-11/05/tick-time/03-11-06-裁定與新設計.md)）；頻率不是 1000 才在根定義資料夾的 `.env` 另寫 `AOS_CLOCK_INTERVAL`，跟鐘列的 `interval_ms` 同值、不檢查；daemon 不往下傳（[thinking clock-decouple](../../../../thinking/2026-11/09/clock-decouple/README.md)）。

<a id="退路"></a>

**退路**（使用者 11-06 選項框「統一成 K3 (Recommended)」，[special-cases](../../../../thinking/2026-11/06/special-cases/README.md#使用者裁定11-06選項框)）：② hub 的「沒設＝`<名字>Missing`」讀成「沒設＝`<名字>Missing`，或在本表那一列寫明唯一一條退路」；退路只管「沒設」。現有三條：`AOS_CLOCK` 沒設退牆鐘、`AOS_KERNEL` 沒設＝`$AOS_DAEMON` 的 ctl 信箱、`AOS_DAEMON` 沒設找 `./.stack`（[02](02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)）；第四個要退路的在表上那一列寫就好。
設了但指不到時**不走退路、不改原本行為**，只多印一行 `warning:`；例外是 aos-agent 的 `mailbox_of`（見下）報 `MailboxMissing`（[env-portability](../../../../thinking/2026-11/06/env-portability/README.md) Q5 已裁，選項原文「不報錯、不改退路」）：
- `AOS_CLOCK` 設了但缺檔＝當第 0 格、不建檔；C++ 與 Python 共用入口印英文 `warning:`（每行程每路徑一次）；空白檔＝0、不提醒。
- `AOS_KERNEL` 指不到：aos-llm-kernel 照用那個信箱、印 `warning:`（`proto8/impls/aos-llm-kernel/src/daemon/daemon.cpp`）；aos-agent 走的 Python `mailbox_of` 報 `MailboxMissing`，不退到 daemon 信箱繞過判官（11-07 使用者裁定 sol 審查 #8）。
