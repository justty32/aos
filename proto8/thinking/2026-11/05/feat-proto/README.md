# 2026-11-05 午 新功能原型五件：agent 自改工具、endpoint 能力包、依信排程、agent 生 agent、資源份額（fable 規劃；11-05 午已實作）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜前情：[kernel-daemon](../kernel-daemon/README.md)（llm kernel＝一台 daemon、問腦掛 proc）、[11-04 think-as-function](../../04/think-as-function/README.md)（代號表、`aos-llm`）、[portable-flow](../portable-flow/README.md)（tools 覆蓋層只存差異）、[edge-agent](../edge-agent/README.md)、[10-24 sandbox](../../../2026-10/24/sandbox/README.md)｜程式（只翻、沒改）：[aos-llm-kernel](../../../../impls/aos-llm-kernel/README.md)、[aos-llm](../../../../impls/aos-llm/README.md)、[aos-agent](../../../../cmd/aos-agent/README.md)、[aos-tools](../../../../cmd/README.md)、[lib](../../../../lib/README.md)、[demo](../../../../templates/README.md)、[aos-daemon](../../../../impls/aos-daemon/README.md)｜條文：[C-42、C-46、C-61](../../../../docs/CONCEPTS/05-agent.md)、[C-47](../../../../docs/CONCEPTS/04-kernel.md)、[C-52、C-56、C-64](../../../../docs/CONCEPTS/01-設計理念.md)、[N-42](../../../../docs/NORMS/09-kernel.md)、[P-17、P-23、P-41](../../../../docs/CONVENTION/02-題目stack停錯腦.md)

狀態：**已實作；使用者 11-05 裁完六題**（下「已定（使用者 11-05 裁六題）」；題 4、題 6〔原題號 3、5〕要改的與生子 agent 兩種、工具自己數配額 11-05 晚 E 線做了，見 [06](06-實作結果.md#11-05-晚使用者裁六題之後e-線)）。原狀態：已實作（11-05 午 S1～S10；件 5 的 daemon 半邊 E1～E3 也做了〔隊長接手 aos-daemon，`9f8c957f` `f376a12c` `b596cddf`〕；做到哪、代定總表、實測、已知限制在 [06-實作結果](06-實作結果.md)）。規劃時：使用者在午睡，方向題照推薦代定、標「可翻案」、不停線（鐵律 5：方向是他的，做原型讓他試）。本檔只記使用者原文（逐字）、已定、代定、留給他的題、跟原則的衝突（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。實作步驟給隊長：[steps](steps.md)。

## 使用者原文（11-05 午，逐字）

> 剛吃飽，想午睡...你繼續多測試一些邊緣狀況吧。然後我跟你說我之後想做的事情，你試試看：讓agent給自己改tool，把endpoint打包成smart-high, stupid-fast, ...這類，並且附上各種屬性(各種temperature也固定)，讓kernel能根據信件中額外附送的priority之類資訊做排程，讓agent利用aos指令產出另一個agent

> 啊，還有，會想要限制特定aos proc所占用的資源。以及daemon/kernel自己本身被限制占用資源，並且會分配份額給proc

> 讓daemon偷偷給底下的proc包s6

## 五件總覽（一句話各一）

| 件 | 一句話 | 分檔 |
|---|---|---|
| 1 | agent 的腦叫一個工具 `self_tools`，它用 `aos-agent ctl who` 認出「我是哪隻」，再 `aos-agent tools add／rm --target 我` 改**自己的覆蓋層**（`<stack>/tools.json`，定義不動）；下一格 brain 重讀就看到 | [01](01-self-tools.md) |
| 2 | `kernel.json` 的 `endpoints` 每組升級成**能力包**：`smart-high`、`stupid-fast`… 帶 `fixed`（釘死的取樣參數）、`slots`、`budget`、`speed`／`cost`／`context`／`summary`；信與 `llm.json` 只寫代號；kernel 把「包的屬性表」寫成一扇窗 `endpoints.json`，`aos-llm ls` 印它 | [02](02-endpoint-packs.md) |
| 3 | 排程多兩條：**包各自的 `slots`**（滿了跳過、讓下一封補位）、同級時**快的包先**；`priority` 的 `level`／`deadline`／aging 照舊；包的 `budget` 到頂回 `BudgetMissing`、不替人降級 | [03](03-scheduling.md) |
| 4 | 腦叫工具 `agents`（`add`／`say`／`ask`／`rm`／`ls`）＝包著 `aos-agent ctl add／say／listen／rm`，掛在**管我的那台 daemon**（`AOS_DAEMON` 繼承），定義＝任何範本資料夾、不繼承腦與工具（要就明寫 `endpoint`／`tools`）；上限交給判官 `max_running` | [04](04-spawn-agent.md) |
| 5 | daemon 表每列選填 `limits`（`mem_mb`／`cpu_s`／`procs`／`files`／`file_mb`／`user`，同 aos-sandbox 的 key），daemon 在 fork 出的子行程裡 `setrlimit`／`setuid`（＝s6-softlimit／setuidgid 的語意，不 exec s6）、proc 不知道；daemon 自己被限＝起它的人包；rlimit 不共享總額（天然差異）；llm kernel 的份額＝包的 budget＋每寄件人 budget。**daemon 那半要邊緣隊改**（清單在 05） | [05](05-資源份額.md) |

## 共同的已定（照既有原則推出來的）

- **全部走現成的 aos 指令、不加新協定**：改工具＝aos-agent tools（覆蓋層）、生 agent＝aos-agent ctl add、問腦＝aos-llm；新東西只有——兩個 lib 工具、一個 `ctl who` 子命令、kernel 認幾個新 key、daemon 表一個 `limits` key（C-42「aos 體系的每一樣都是 agent 的工具——自我迴圈改進的閉環」）。
- **件 1～4 只動我們領地**（lib、extras/agent、aos-llm-kernel、aos-llm、demo、條文），不需要邊緣隊改檔；**件 5 的 daemon 半邊**（E1～E3）請邊緣隊改，我們做 kernel 的寄件人額度與 aos-agent 的宣告。
- **邊界＝覆蓋層、判官、rlimit**：agent 改得了的只有自己 stack 裡的差異檔；生得出的 agent 數由判官 `max_running` 擋；吃多少資源由表上那列的 `limits` 擋；前兩者是 11-05 早已有的機制、第三個是 Linux 現成的。
- **fake 腦能演件 1～4**：`llm_fake` 加一個 `script` 鍵（照劇本回答、含 tool_calls），demo 零成本、可重跑；真腦（LM Studio `local-qwen`、LiteLLM 的 claude haiku）標成「要使用者試」。件 5 用 `ulimit`／`python3` 吃記憶體演。

## 留給使用者的題（推薦放第一；各件細節在分檔）

1. **包釘死的參數撞到信裡寫的**（件 2）：推薦 kernel 回 `RequestBad` 說「temperature 由包 smart-high 釘死」；另一條是包默默蓋過（違 C-56「寫什麼就做什麼」）。
2. **包的額度用完要不要自動降級**（smart-high → stupid-fast，件 3）：推薦**不降級**、回 `BudgetMissing` 讓寄信的 agent 自己改代號重寄；另一條是包寫 `fallback`。
3. **子 agent 的工作區預設**（件 4）：推薦跟父同一個 `AOS_WS`（協作同一堆檔）；另一條是 `$AOS_WS/<子名>/`。
4. **生 agent 的上限數字**：推薦判官 `max_running: 4`（含父）；深度不另限。
5. **範本 agent-fsm 要不要內建 `self_tools`、`agents`**：推薦**不內建**，demo 用 `aos-agent tools add` 當場加（這本身就是件 1 的機制）。
6. **件 5 的做法**：推薦 daemon 子行程自己 `setrlimit`／`setuid`（s6 的語意、不多一支程式、WSL 沒 s6 也跑）；另一條是照字面 exec `s6-softlimit`（要 PATH 有 s6、子行程改 execvp）。

## 已定（使用者 11-05 裁六題，逐字選項）

題號照使用者問卷的順序（跟上面「留給使用者的題」編號不同：問卷題 1＝上面題 6）。

1. 份額做法 →「維持自己 setrlimit (Recommended)」：不改（daemon 子行程自己 setrlimit／換帳號）。
2. 包釘死的參數撞到信裡的 →「回 RequestBad (Recommended)」：不改。
3. 包額度用完 →「不降級，回 BudgetMissing (Recommended)」：不改。
4. 子 agent 工作區 →「不要固定，因為各有不同需求。」：**改了**——`agents` 的 `new`／`add` 收 `ws`（相對＝從父的 `$AOS_WS` 算、絕對照用，不在先建）；沒給＝沿用父的 `$AOS_WS`（隊長代定）；tool description 寫明。
5. 判官上限 →「可以4。」：不改（`max_running` 4，含父）。
6. 範本內建 `self_tools`／`agents` →「內建」：**改了**——`demo/agent-fsm`、`demo/eca-claude` 的 `tools.json` 登記 `self_tools`、`agents`（eca 經 aos-mcp 用得到），各帶一份工具設定 `agents.json`（`{"max_children": 4}`）。

使用者 11-05 同時補的兩段（逐字）：

> 話說，生子agent有分兩種，一種是產出新agent定義，另一種是用現有定義生(可能會稍微改一些設定)。我希望兩種都有

> 不過claude code這類常見eca的做法，通常是在呼叫工具的時候，工具自己有紀錄，會看到說超過四個，直接回error

所以 `agents` 多了 `new`（產出新定義：範本複製到指定位置再改，或整份自己寫；寫完是普通定義資料夾、可重用）、`add` 收覆蓋（`llm`、`tools`、`tools_rm`、`ws`、`limits`，走子的覆蓋層、不複製定義）；工具自己數這隻父生了幾隻（`max_children`，超過＝`ChildSlotMissing`、不寄信），判官照舊是整台 daemon 的第二道關。原本 [04](04-spawn-agent.md) 代定 3「不在工具裡做名額（兩套上限打架）」被這句翻掉：兩道關各數各的（工具＝這隻父的配額、判官＝整台總量）。細節與實測在 [06](06-實作結果.md#11-05-晚使用者裁六題之後e-線)。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-self-tools](01-self-tools.md) | 件 1：自己是誰（`ctl who`）、只改覆蓋層、改壞怎麼救、腦怎麼知道；衝突 C-52 |
| [02-endpoint-packs](02-endpoint-packs.md) | 件 2：包的形狀與 key、哪些 kernel 看／哪些交給函數、`fixed` 與 `request.model`、窗 `endpoints.json`；衝突 C-56 |
| [03-scheduling](03-scheduling.md) | 件 3：排隊順序、包的 slots 補位、包的 budget、不降級；留題 |
| [04-spawn-agent](04-spawn-agent.md) | 件 4：工具 `agents`、定義從哪來、掛哪台、不繼承、收掉、遞迴爆量；衝突 C-52 |
| [05-資源份額](05-資源份額.md) | 件 5：`limits` 寫哪、daemon 自己被限、不共享總額、超額、kernel 的 token 份額、跟 aos-sandbox 的關係；衝突「包 s6」vs KISS；**請邊緣隊改 E1～E3** |
| [steps](steps.md) | 13 步：檔、完成判準、手跑、派誰、依賴、能否並行；demo 放哪（實作後的結果寫 06-實作結果） |
| [06-實作結果](06-實作結果.md) | 實作後：五件做到哪、代定總表（六題全照推薦）、WSL 假腦實測、已知限制；劇本 [demo/docs/05](../../../../kernel/docs/03-feat-proto.md) |
