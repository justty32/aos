← [入口](README.md)｜aos 體系知識庫：節點樹、每節教什麼、為什麼這樣寫、用詞表｜上一份 [01-層級式記憶工具](01-層級式記憶工具.md)｜下一份 [03-接進agent與工具說明](03-接進agent與工具說明.md)

# aos 體系知識庫（層級式記憶工具的第一個知識庫）

位置 `proto8/knowledge/aos/`（`../../../../knowledge/aos/README.md`）（說明在 [knowledge/README](../../../../knowledge/README.md)）。英文、給 Haiku／luna 級小模型讀；一節 ≤ 2 KB、十節共 18 KB，但 agent 一次只拿根（2 KB）＋它需要的一兩節。

## 節點樹（根＋九節）

| 節點 | 教什麼 | 為什麼放這層 |
|---|---|---|
| `/`（根） | aos 一句話；**八個詞**（definition、stack、workspace、daemon、proc、kernel、letter／mailbox、tool）各一行；**五條規則**（別改定義與別人的 stack、用工具不用 shell、看錯誤代號再重試一次、路徑相對工作區、被拒是決定不是 bug）；怎麼往下讀 | 每次都給的「核心」。只放必須先知道的；每個詞一行、不解釋機制（STRUCTURE：頂層不存下層細節） |
| `world` | 心智模型對照表（daemon＝硬體、stack＝記憶體、ws＝外置記憶體、定義＝source、kernel＝守門人、llm kernel、knowledge base）＋推論（一份定義多個實例、覆蓋層只存差異、proc 必在一台 daemon 下、能睡能搬）＋能依賴的環境變數 | 使用者 11-05 早定的世界觀；小模型要「為什麼」時讀 |
| `me/` | 我是誰（`aos-agent ctl who` 查表）；我的 stack 裡有什麼（`history.jsonl`、`queue/`、`tools.json`、`llm.json`、`tools/<名>/`）；我能改什麼（只有自己的覆蓋層、只經工具）、不能改什麼 | 「自省」是 kernel 層要給 agent 的能力（名詞表 kernel 列）；工具 self_tools 掛在它底下 |
| `me/self_tools` | 工具 `self_tools` 的四種呼叫（add／add override／rm／ls）、path 規則、下一輪生效、`PathMissing`／`ToolExists`／`DaemonMissing` 怎麼辦、為什麼安全（別隻看不到、人看得到 `tools overlay` 行、`tools reset` 可退） | feat-proto 件 1 |
| `agents/` | 工具 `agents` 的五種呼叫、不繼承腦與工具、`def` 路徑規則、只能叫自己生的、上限是判官定的（`AddRejected … SlotMissing`＝收一隻或回報、不迴圈）、`AnswerMissing` 兩種情況、用完要收 | feat-proto 件 4 |
| `brain` | 問腦是信（信的形狀、`aos-llm ask／send／recv`）；endpoint 包（smart-high／stupid-fast／fake；包釘死 model 與取樣參數→不要寫 `temperature`，寫了＝`RequestBad`）；priority（level／deadline、快包先、aging 保底）；budget（`BudgetMissing` 不替你降級）；常見代號 | feat-proto 件 2、3；agent 自己的思考已接好，這節是給它替子 agent 選腦、或回答人的問題時用 |
| `status` | daemon 表一列長什麼樣；phase 表（running／stopped＋reason／sleeping／stopping）各自「對我意味什麼、該做什麼」；列消失＝做完或被 rm；`queue N`；`reason` 怎麼讀；paused 表上看不出 | 11-05 晚裁定的「出錯留 stopped＋reason」 |
| `errors` | 錯誤行的三段（誰、代號、原因）；代號結尾表（Bad／Missing／Unknown／Failed／Rejected／Internal → 各自怎麼辦）；最常碰到的七個代號；「有文字沒錯誤行＝成功」 | C-54 四種結尾＋`Rejected`（aos-agent 的 `AddRejected`／`CtlRejected`）＋`Internal` |
| `rules` | 七個 Never（改定義、碰別人 stack 與 daemon 檔、改寫 history、繞過拒絕、用 shell 代工具、留子 agent 不收、刪工作區外的東西）＋四個 Always＋一段為什麼 | 安全邊界集中一處；根的五條是它的摘要 |
| `cli` | 給人與外部 coding agent 的 `aos-agent` 指令表（ctl add／ls／state／stop／start／sleep／wake／pause／resume／rm／who／where；say／listen／chat；tools／llm 覆蓋層；`aos-llm ls`／`ask`）、找哪台 daemon、三個常見代號 | 經 aos-mcp 進來的 Claude Code 等外部 agent、以及人，不是 aos 內的 agent 要讀的 |

## 寫法（照使用者「目標是haiku或codex-luna能懂」）

- **短句、每句一件事**；呼叫一律給可以照抄的 JSON 例子；指令一律給完整一行。
- **用詞固定**（下表）；不用同義詞換著講。比喻只在 `world` 一處，而且用對照表、每個比喻明寫對應到哪個詞。
- **每個代號都接「怎麼辦」**；小模型最常錯的是「被拒就重試」，所以根、agents、errors、rules 四處都講「不迴圈、回報或調整」。
- 不講底層（inst、aos-exec、fsm 格、信封欄位、daemon 信箱名）；需要時由人加一節，不往上堆。

## 用詞表（知識庫與工具說明都用這些字）

| 字 | 意思 | 不用的同義詞 |
|---|---|---|
| definition | 定義資料夾（source code） | template、config |
| stack | 一個實例的狀態資料夾 | state dir、instance folder |
| workspace / ws | 工作區 `$AOS_WS` | working directory、project |
| daemon | 跑 proc 的那台「機器」 | supervisor、runtime |
| proc | daemon 下一個會跑的東西 | process（除了講 Linux 時）、task |
| kernel / judge | 守門人；判官＝擋在 daemon 前面的 kernel | scheduler、policy |
| letter / mailbox | 信與信箱 | message、queue（queue 只指 `$AOS_STACK/queue/`） |
| tool | 可呼叫的資料夾 | function、skill、plugin |
| overlay | 實例自己的差異檔（`tools.json`、`llm.json`） | patch、override（只當 `self_tools` 的參數名） |
| endpoint pack | llm kernel 的一組命名腦設定 | model、provider |
| phase | 表上的狀態字 | state、status（指令名除外） |
| reason | 表上出錯結束留的那行 | error message |
| Code | 錯誤行第二個字 | error type |
