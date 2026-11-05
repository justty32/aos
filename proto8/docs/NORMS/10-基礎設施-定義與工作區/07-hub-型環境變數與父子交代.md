← [回入口 10-基礎設施-定義與工作區.md](../10-基礎設施-定義與工作區.md)｜段落：hub 型環境變數（10-28）｜上一份：[06-N-50～N-53](06-N-50～N-53.md)｜下一份：[08-父子交代](08-父子交代.md)

## hub 型環境變數（10-28）

- **N-63**（10-28 定，草稿；使用者 10-28「hub 照你的建議定薄標準。」，[thinking 10-28 medium](../../../thinking/2026-10/28/medium/README.md) 決定 17）**hub（類 singleton、全樹共用的那一個東西）用環境變數指，只定三件事，其他不管**：
  ① **命名 `AOS_<名字>`，值是一個資料夾的路徑**；
  ② **沒設定＝報錯、說缺什麼**：代號 `<名字>Missing`（C-54，例 `StackMissing`、`DaemonMissing`），不自己猜一個位置；
  ③ **子 process 預設繼承**（照 Linux 環境變數本來的樣子往下傳）。
  資料夾裡放什麼、誰建、怎麼跟它講話，各 hub 自己定。現有的實例：`AOS_STACK`（執行中狀態放哪，N-57）、`AOS_LLM_KERNEL`（llm kernel 的信箱資料夾，N-16、N-42、[aos-llm](../../../impls/aos-llm/README.md)；11-05 前叫 `AOS_KERNEL`，見下「舊名退場」）、`AOS_DAEMON`（見下）。
  - **跟實作對不上的**（只列、程式沒改）：
    - `AOS_STACK` 沒設時 **aos-exec 自己退回預設** `$AOS_WS/.stack/`（N-57、C-69，impls aos-exec `setup_ws_stack`），跟 ② 不合；aos-loop（開了窗才要）、aos-fsm、aos-daemon、aos-llm-kernel 沒設就報 `StackMissing`，合。 **11-04 定**（使用者 11-04 題 1「只有 aos-exec 給」，[four-elements 06](../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)）：`AOS_STACK` **只有 aos-exec 給預設**（它負責建），其他程式沒設＝`StackMissing`（aos-tools `call` 可執行檔工具 11-04 起也是，不再偷用暫存資料夾）；替人下 aos-exec 的人殼指令算成那一跳、照 aos-exec 的預設。
    - `AOS_LLM_KERNEL` 沒設時 aos-llm（11-04 晚前叫 aos-llm-send）報 `KernelMissing`、不猜位置，合 ②（**11-04 已改**：原本代號是 `MailboxMissing`，四元素審查）。kernel 那一邊（aos-llm-kernel）不讀 `AOS_LLM_KERNEL`，信箱位置讀 kernel.json 的 `mailbox`；範本 `demo/llm-kernel` 的信箱在它的 `$AOS_STACK` 底下，由人把那個路徑 export 成 `AOS_LLM_KERNEL`（掛 daemon 時＝`$AOS_DAEMON/procs/<名>/mailbox/`）；**daemon 不代設**（使用者 11-05「用人設吧，你得自己指定。AOS_KERNEL這個命名我感覺他是通用於所有proc的，像是llm請求這塊，感覺要用AOS_LLM_KERNEL，代表llm這個子領域下的，管理呼叫的kernel。」（[thinking 11-05 portable-flow 05 方向題 5](../../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)））。
    - **舊名退場**（11-05，照 11-04 `AOS_DAEMON_STACK` 的做法）：`AOS_KERNEL` 改名 `AOS_LLM_KERNEL`、不留別名——只設了 `AOS_KERNEL`、沒設 `AOS_LLM_KERNEL`＝aos-llm 報 `KernelMissing`，訊息提示改設 `AOS_LLM_KERNEL`。`AOS_KERNEL` 這個名字留給以後「通用於所有 proc 的 kernel」（使用者同句）；代號 `KernelMissing` 沒跟著改名（實作代定、可翻案）。
    - ③ 跟 [CONVENTION P-39](../../CONVENTION/06-巢狀/03-P-37～P-40.md) 的寫法不同：P-39 把 `AOS_STACK` 歸「叫別人時明給」（每層開小格、重設），不是一路繼承；繼承是預設，P-39 是 agent 範本在叫別人時的做法。
  - **實例 `AOS_DAEMON`**（使用者 10-30「關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。」，[thinking 10-30 map-review](../../../thinking/2026-10/30/map-review/01-使用者原文.md#決定10-30) 第 10 點；名字：使用者 11-02「就AOS_DAEMON_STACK吧」「最好明講，也就是--daemon-stack」，[thinking 11-02 daemon-env](../../../thinking/2026-11/02/daemon-env/01-使用者原文-11-02-逐字.md#決定11-02使用者)；**11-04 註**：改回 `AOS_DAEMON`、旗標 `--daemon`，使用者 11-04 晚「AOS_DAEMON_STACK實在太醜，還是直接簡化成AOS_DAEMON就好了」，[thinking 11-04 aos-agent](../../../thinking/2026-11/04/aos-agent/02-找-agent.md#哪個-daemon)；優先順序是實作代定、可翻案；照實作寫，[aos-daemon-ctl](../../../bin/README.md)、aos-eca〔11-04 併進 [aos-agent](../../../extras/agent/README.md)，照同一條〕）：aos-daemon-ctl、aos-eca〔＝aos-agent〕找「掛到哪個 daemon」用 `--daemon` ＞ `$AOS_DAEMON`，值＝那個 daemon 的 `$AOS_STACK` 資料夾；都沒有或不是資料夾＝`DaemonMissing`；子 process 照常繼承——三件都合。
    - **舊名退場**（11-04 晚反向重寫：11-02 定的是 `AOS_DAEMON`→`AOS_DAEMON_STACK`、不留別名〔頂層代定〕；現在倒回來、一樣不留別名，[11-04 四元素審查](../../../thinking/2026-11/04/four-elements/README.md)點名）：`AOS_DAEMON_STACK`、`--daemon-stack` 不留別名——給 `--daemon-stack`＝`FlagUnknown`；只設了 `AOS_DAEMON_STACK`、沒設 `AOS_DAEMON`＝`DaemonMissing`，訊息提示改設 `AOS_DAEMON`（或 `--daemon`）。
    - **不定三名**（使用者 11-02「那就不用定這三個名字了」）：不另設「daemon 的定義所在」「daemon 的工作區」的變數。
    - **daemon 起子項時把 `AOS_DAEMON` 設給它**（11-04 晚改名）（兄弟要共用位置時用；只設這一個。使用者 11-02 對常駐 bob 的衝突與方向題回「照建議走」，thinking 11-02 resident-bob（11-04 封存）衝突 2；daemon 起子項時設給子項見 [thinking 11-02 daemon-env 決定](../../../thinking/2026-11/02/daemon-env/01-使用者原文-11-02-逐字.md#決定11-02使用者)；照實作寫，[aos-daemon](../../../impls/aos-daemon/README.md)）：loop 型、exec 型子項的環境一律多 `AOS_DAEMON`＝daemon 自己的 `$AOS_STACK`，轉成絕對路徑、結尾 `/`（跟 aos-exec 給的 `AOS_STACK` 同形；頂層代定、可翻案）；daemon 自己的環境裡原本有沒有這個變數都蓋過去。子項裡的 `aos-daemon-ctl` 因此不用另給 `--daemon` 就找得到它的 daemon。
    - **例外 `AOS_AGENT`**（11-04 註；使用者 11-04 晚裁「N-63 加一句例外」，[thinking 11-04 aos-agent 06/02](../../../thinking/2026-11/04/aos-agent/06-衝突與方向題/02-新題-11-04-晚.md#使用者裁定11-04-晚選項原文)）：`AOS_` 開頭但**不是 hub**（值是名字、不是資料夾，不照 ①）：是 aos-agent 給人殼用的預設對象（`--target` 沒給就看它，[02-找-agent](../../../thinking/2026-11/04/aos-agent/02-找-agent.md#找-agent只有一條路)）。
  - **沒有 `AOS_HUB`**（使用者 10-30「都照建議」，[thinking 10-30 eca](../../../thinking/2026-10/30/eca/09-方向題.md#決定10-30) 衝突 2、4；[10-30 map-review](../../../thinking/2026-10/30/map-review/01-使用者原文.md#決定10-30) 第 5 點）：aos-eca〔11-04 併進 [aos-agent](../../../extras/agent/README.md)，同樣建在 aos-daemon 上〕 建在 aos-daemon 上、不設自己的常駐 kernel，用哪個 daemon 照 `AOS_DAEMON`（上面），不另設變數（一個 hub 一個變數，這裡的 hub 就是 daemon；另設＝同一個資料夾兩個名字，C-54 一詞一義）。`aos-hub` 這個名字保留，以後真有通用的 hub 再用（使用者 10-30）。

<a id="aos-變數的四種性質11-04"></a>

### `AOS_` 變數的四種性質（11-04）

使用者 11-04 題 2「寫一張表」（[four-elements 06](../../../thinking/2026-11/04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)、[01 盤點](../../../thinking/2026-11/04/four-elements/01-環境變數.md)）：`AOS_` 開頭的環境變數分四種，每個活變數歸一格；下次有人想加 `AOS_XXX`，先問「你是哪一種」。

| 性質 | 是什麼 | 活的變數 |
|---|---|---|
| ① 執行環境 | aos-exec 每層設（N-57），全體讀 | `AOS_WS`、`AOS_STACK`（同時是 hub 的實例；只有 aos-exec 給預設）、`AOS_CF`、`AOS_CD`、`AOS_CO`（現在沒人讀）；`AOS_ENTRY` 是全樹繼承的旋鈕、使用者 11-01 裁留〔11-04 晚 `AOS_KERNEL_REPORT` 退場：用量改在回信的 `usage`（N-42 (1)）〕 |
| ② hub | 值是資料夾、沒設＝`<名字>Missing`、子 process 繼承（本條 ①～③） | `AOS_LLM_KERNEL`、`AOS_DAEMON` |
| ③ 人殼預設 | 人在殼裡 export、程式之間不靠它傳（像 `EDITOR`） | `AOS_AGENT`（上面的例外） |
| ④ 旋鈕 | 原則上不走環境變數（刪、改 argv、改檔；使用者 11-01「除非真的有必要，否則不要用」）；真要走就帶 `AOS_`、寫在定義的 `.env` | 現無。`AOS_HEAP`（`lib/aos/memory`）、`AOS_ROSTER`（`lib/aos/send_message`）11-04 已封存（使用者 11-04 晚「封存」），隨工具退場；`AOS_BRAIN_URL`／`AOS_BRAIN_MODEL`／`AOS_BRAIN_KEY` 11-04 晚退場（原本等 kernel 收、使用者 11-04「我再想想」；11-04 晚「brain url那塊我不喜歡，我希望llm呼叫，或者說思考，這本身也是用aos函數」：端點、模型、金鑰改放 `kernel.json` 的 `endpoints`，agent 只寫代號，P-23、[think-as-function](../../../thinking/2026-11/04/think-as-function/README.md)） |

    - **11-05 例外 `AOS_DAEMON` 沒設＝找 cwd 的 `./.stack`**（使用者 portable-flow 題 3 選「沒設就找 ./.stack」，不是推薦項；[thinking](../../../thinking/2026-11/05/portable-flow/README.md)）：aos-daemon-ctl、aos-agent、`using-aos-agent.sh` 在 `--daemon`、`AOS_DAEMON` 都沒給時用 `$PWD/.stack`（轉絕對、不往上層找）；有設照用。這條對 ② 「不猜位置」開一個口：猜的只有「daemon 在這個 ws 裡起」這一種位置。
