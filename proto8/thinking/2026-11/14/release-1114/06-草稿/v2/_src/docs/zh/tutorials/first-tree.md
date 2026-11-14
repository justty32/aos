# 教學 1：第一棵樹

這一頁帶你慢慢看一棵樹：兩個資料夾（llms 與 tree）、一隻叫 ann 的 agent，以及它留下的每個檔。

先跑過 [Get Started](../get-started.md)，或照下面的圖自己再起一次。這頁不重貼完整指令，只解釋「為什麼長這樣」。

<!-- copy:TRY -->
不用任何模型，先試試

<!-- source: 這兩列原稿標「用途本稿沒逐檔核對，標待驗」，hooks/ 等五項原稿稱「細節本稿沒逐檔核對，視為內部狀態」；ref/get-started.sh; ref/get-started.out.txt; proto8/templates/daemon-root/README.md; proto8/templates/agent-fsm/README.md; 知識庫 aos/definition.json、aos/mailbox.json、aos/agents.json -->

## 1. 整體擺法

```text
~/aos-demo/
  llms/                      腦那一邊（一個獨立的專案）
    def/                     llm kernel 的定義（抄自 kernel/llm-kernel）
    stacks/llm/              它跑起來的狀態
  tree/                      你的 agent 那一邊
    defs/                    根 daemon 的定義（抄自 templates/daemon-root）
    defs/ann/                ann 的定義（抄自 templates/agent-fsm）
    stacks/root/             根 daemon 跑起來的狀態
    stacks/root/procs/ann/   ann 自己的狀態
```

重點：**定義（defs）是「這東西是什麼」，stack 是「它跑起來後的記憶」**。定義不要手改；跑的時候的東西都在 stack。

## 2. 根 daemon：機器本身

根 daemon（`tree/defs` 這份定義）只帶兩個內建的東西，之後的 agent 另外掛上去：

| 名字 | 做什麼 |
|---|---|
| `_clock` | 每秒寫一次 `$AOS_STACK/clock`，agent 聽這個鐘 |
| `_sweeper` | 每 10 分鐘清這台自己的 stderr 封存，寫 `sweeper_report.json` |

`aos-daemon-ctl -d stacks/root ls` 看到的表就是 `_clock`、`_sweeper`、`ann` 三列。表上每列是一個 proc（行程），欄位有名字、狀態（`running` 等）、pid、工作區。

## 3. ann 的定義與 stack

`defs/ann` 是抄來的 `agent-fsm` 範本，裡面是 agent 的「程式碼」：

| 檔 | 是什麼 |
|---|---|
| `system.txt` | 給腦的系統文字 |
| `tools.json` | 它能用的工具（範本預設開很多包，包括看、改、刪、殼） |
| `llm.json` | 腦的設定 |
| `fsm.json` | 四格：idle 從隊列取信、think 組請求問腦、wait 等腦回信、act 執行工具呼叫 |
| `hooks.json` | 事件鉤子（範本預設有一個每 5 分鐘不做事的 timer，和每分鐘檢查新信的 mail_notify） |
| `interfaces.json` | 宣告上面這些檔放哪 |

`stacks/root/procs/ann/` 是 ann 跑起來的狀態，在 Get Started 第 4、6 步看到的：

| 項目 | 是什麼 | 出現時機 |
|---|---|---|
| `queue/` | 要進 ann 對話的訊息排隊的地方（`say` 的話會進這裡；信箱是另一個資料夾，不會自動進對話） | 一開始就有 |
| `history.jsonl` | 對話紀錄，一行一筆：叫工具、工具回傳、最後答案 | 第一次說話後才出現 |
| `think/` | think 格的工作資料夾（例如等腦太久的提醒記錄 `wait_warned.txt` 放這裡） | 第一次說話後才出現 |
| `hooks/`、`state.json`、`state_flux.json`、`stage.txt`、`stderr.txt` | 執行期的內部狀態、目前階段與錯誤輸出，由系統維護，平常不用手改 | 一開始就有 |
| `interfaces.json`、`observed.jsonl` | 這隻 agent 的介面宣告與執行觀察紀錄（這兩個檔的細節我們還沒逐一驗證） | 第一次說話後才出現 |

## 4. 一句話經過哪些地方

```text
你 say "hello..."
  → ann 的 queue/
  → idle 取出 → think 組請求
  → 寄給 llm kernel（AOS_LLM_KERNEL 指到它的 stack）
  → 假腦：先叫 peek_now_time，再答 FAKE ANSWER ...
  → act 執行工具 → history.jsonl 多三行
```

`AOS_LLM_KERNEL` 預設在 `tree/defs/.env` 裡指向 `${AOS_WS}/../llms/stacks/llm`，所以 llms 與 tree 要並排放。kernel 沒開時 agent 只是一直等，不會壞。

<details>
<summary>假腦是什麼</summary>

llm kernel 範本預設的 `endpoint` 是 `fake`：有工具就先叫 `peek_now_time`（沒有就叫第一個工具），再回 `FAKE ANSWER to: <你說的話> (tool said: …)`。它不是模型，所以每次回答都一樣格式。接真腦屬 L1，見[安裝總覽](../setup/index.md)。

</details>

## 5. 改一個地方看看：再加一隻 bob

> 這節要樹還在跑：請在[開始用](../get-started.md)第 8 步停樹**之前**做。已經停了的話，在同一個示範夾把第 3 步的兩行 `nohup aos-exec …` 再跑一次，樹和 ann 會接著醒來。

<!-- source: run literally 11-14 in a clean copy (ann + bob both running, bob answered, procs/ had ann and bob; no process left) -->

```bash
cd ~/aos-demo/tree
cp -r "$AOS_HOME/templates/agent-fsm" defs/bob
aos-agent -d stacks/root ctl add -w . defs/bob
aos-daemon-ctl -d stacks/root ls
aos-agent -d stacks/root -t bob say "hello, who are you?"
timeout 60 aos-agent -d stacks/root -t bob listen
ls stacks/root/procs/
```

```text
ann	running	…
bob	running	…
FAKE ANSWER to: hello, who are you? (tool said: …)
_clock  _sweeper  ann  bob
```

表上多一列 `bob`，它自己有一個 `procs/bob/`，對話與 ann 分開。看完後照 Get Started 第 8 步停樹。

<details>
<summary>想動手再多改一點</summary>

- 改 `defs/bob/system.txt` 再重掛一隻，看它的回答格式有沒有不同；假腦的回答格式是固定的，所以改了也看不出差別，這要等接上真腦（還沒實測，歡迎回報）。
- 只想讓 bob 唯讀：從 `defs/bob/tools.json` 的 `$override` 拿掉 `change.json`（改）、`delete.json`（刪）、`shell.json`（殼）那幾包（說明在 agent-fsm 範本 README；還沒實測，歡迎回報）。

</details>

## 停樹

照 [Get Started 第 8 步](../get-started.md)兩個 daemon 都收；若有殘留見[疑難排解](../manual/troubleshooting.md)。

下一步：[安全說明](../manual/security.md)、[狀態](../status.md)。
