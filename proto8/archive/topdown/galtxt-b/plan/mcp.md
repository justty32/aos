# 把 aos 的資料夾程式弄成 MCP（支線，乙隊 opus，2026-10-25）

← [galtxt-b](../README.md)｜原型：[mcp/aos_mcp.py](mcp/aos_mcp.py)｜相關：[lib 工具契約](../../../lib/README.md)、[`_metainfo` 位置與格式](../../../thinking/2026-10-24-metainfo/01-位置與格式.md)、[P-41 腦的工具呼叫](../../../docs/CONVENTION/02-題目stack停錯腦.md)、[aos-ai](../../../extras/ai_tools/README.md)

使用者 10-25（支線）：「在進行的過程中，可以適當將一些經驗留存下來。」「因爲我們目前都還是依賴claude code來操控，來制作這套程式。以後我們也會用aos體系，制作用來制作這套程式的程式」「到時候就會需要這些經驗。」「可以先想想，假如想要弄成mcp，那該怎麼做」「這是支線任務」

以下是 AI 的結論稿，沒有拍板；跟原則打架的地方在 §5，留給使用者定。

## 0. 一句話結論

**一支通用的 MCP server 就夠了**：給它一個根資料夾，它把底下有 `tool.json` 的資料夾都攤成 MCP 的 tool，叫的時候用 `aos-exec --ws <工作區> <那個資料夾>` 跑，arguments 從 stdin 進、stdout 當結果。這件事幾乎不用新發明——aos 的 `tool.json` 本來就是照 OpenAI function 的形狀定的，MCP 的 tool 也是同一個形狀（名字＋說明＋JSON Schema），兩邊一對就上。原型約 210 行標準庫 Python，跑得動（§6）。

真正要想的只有三件事：**工作區和 stack 由誰給**、**跑很久的 agent 怎麼回報與取消**、**`_metainfo` 哪些能變成 MCP 的提示、哪些對不上**。

## 1. 對照表：MCP 的東西 ↔ aos 的東西

### 1a. 一對一（直接轉）

| MCP | aos | 怎麼轉 |
|---|---|---|
| tool 的 `name` | 資料夾名（P-41：工具名＝資料夾名） | 用從根算起的路徑，`/` 換成 `__`（例 `base__clock`）。MCP 名字只收英數、`_`、`-`，所以中文或含 `.` 的資料夾名要換字（見 §5 第 7 條） |
| `description` | `tool.json` 的 `description` | 原樣 |
| `inputSchema` | `tool.json` 的 `parameters` | 原樣（兩邊都是 JSON Schema） |
| `tools/call` 的 `arguments` | 工具的 stdin（P-41、lib 規則 1） | `json.dumps` 後餵進 stdin |
| 結果的 `content`（text） | 工具的 stdout（lib 規則 2） | 整段原樣當一則文字 |
| `isError: true` | 結束碼非 0（lib 規則 3：錯一律退 1，同一行也印在 stdout） | 非 0 就標 isError，另附一則「結束碼 N」；lib 的工具錯誤那一行本來就在 stdout，模型看得到 |
| JSON-RPC 錯誤（-32602） | 叫了不存在的工具（agent-dan 的 `ToolUnknown`） | server 自己回協定錯誤，不起任何程式 |
| `annotations.title` | `_metainfo.summary` | 一句話給人看的名字 |
| `annotations.readOnlyHint` | `_metainfo.side_effect` 的反面 | `side_effect: false` → 唯讀 |
| `annotations.idempotentHint` | `_metainfo.idempotent` | 原樣 |

### 1b. 對得上一半（要推論）

| MCP | aos | 怎麼辦 |
|---|---|---|
| `annotations.openWorldHint`（會不會碰外面的世界） | `_metainfo.resource` 裡有沒有 `net`／`llm`／`human` | 有寫 `resource` 才推：含這三種之一＝true，否則 false。這是推論，不是 `_metainfo` 原本的意思 |
| `annotations.destructiveHint`（會不會破壞、還是只會加東西） | 沒有對應的軸。`side_effect` 只說「會動外面」，沒說「蓋掉還是只加」；`idempotent` 也不是這個意思（`write` 整份蓋掉是冪等的，卻是破壞性的） | **不轉**，讓客戶端用 MCP 的預設（true，保守）。要精準就在 `_metainfo` 加一個 key（例 `destructive`），那是規範的事，不在這裡定 |
| `notifications/progress`（長工作回報進度） | 沒有進度通道；最接近的是 fsm 每跑完一格寫的 `$AOS_STACK/trace.jsonl` | 見 §3。要看下層的檔，碰到 C-52（§5 第 4 條） |
| `notifications/cancelled`（取消） | 送 TERM 給 aos-exec，它轉給整群、過 `grace_ms` 再 KILL；`_metainfo.interrupt` 說殺了會怎樣 | 見 §3 |
| MCP 的 roots（客戶端告訴 server「你可以碰哪些資料夾」） | `AOS_WS`（C-66：工作區＝指標） | 很像，但不是同一件事：roots 是允許範圍，`AOS_WS` 是這次要動的那一個。原型不用 roots，啟動時 `--ws` 給一個（§2） |
| resources（給客戶端讀的檔，用 URI 定位） | 工作區的 `out/`、stack 裡的 `trace.jsonl`、`history.jsonl` | 可以做成 resources 給人或 Claude 讀，但那是 server 去讀別人的 stack，碰 C-52。原型不做；要做也只開工作區（呼叫者自己的地方），不開 stack |

### 1c. 對不上（沒有對應）

| aos 這邊有、MCP 沒有 | 怎麼辦 |
|---|---|
| `_metainfo` 的 `deterministic`、`interrupt`、`time_ms`、`resource`、`parallel`、`lock`、`llm_calls`、`llm_tokens`、`cost` | 整份原樣塞進 tool 的 `_meta`（MCP 留給擴充的欄位，key 用 `aos/metainfo`）。一般客戶端不看、不給模型；以後 aos 自己當 MCP 客戶端時可以讀 |
| 結束碼 10（idle，沒事可做） | 不算錯，回一則「結束碼 10（沒事可做）」，不標 isError |
| stack（每個工具一個小格，跨呼叫延續） | MCP 沒有「狀態放哪」這個概念，server 自己管（§2） |
| `.env`、`AOS_ENTRY` 等六個環境變數 | aos-exec 自己處理，server 不碰 |
| **MCP 有、aos 沒有** | |
| `outputSchema`／`structuredContent`（結構化結果） | lib 的結構工具印一行 JSON，但 `tool.json` 沒寫輸出的形。原型只回文字；要用就得在 `tool.json` 多一個 key，那是 P-41 的事 |
| prompts（給使用者挑的提示範本） | aos 沒有對應。agent 的 `system.txt` 是 agent 自己的、不對外。不做 |
| sampling（server 反過來請客戶端的模型想） | 很誘人（agent 的腦借 Claude 用），但等於把「腦」換成走 MCP 的另一條路，跟 P-23（腦＝OpenAI 相容端點）是兩套。不做，有需要另提 |

## 2. 層次：通用一支還是每棵樹一支？工作區、stack 由誰給？

**通用一支**，理由三個：

1. `tool.json`＋`_metainfo` 本來就是契約。每棵樹一支 server 等於把同一段「讀 tool.json、跑 aos-exec」抄 N 份，違反 KISS。
2. 「掃 `tools/*/tool.json` 組 tools 陣列」本來就是 agent-dan 的 brain 在做的事。**把 server 的根指到某隻 agent 的 `tools/`，Claude Code 看到的工具就跟那隻 agent 的腦看到的一模一樣**——這是最有用的一點（§4）。
3. 每棵樹要的差異（哪些工具給、工作區在哪）都是啟動參數，不是程式。

掃描規則（原型照做）：跟著捷徑走、同一個實體只算一次（galtxt-b 的 `lib/lint` 被 `check/tools/lint`、`writer/tools/lint` 兩條捷徑掛，只出一個 `lib__lint`，名字取實體自己那條路）；找到 `tool.json` 就不再往下（工具裡面是工具自己的事，C-52）；`.` 開頭的資料夾（`.stack`）跳過。

**工作區**：server 啟動時給（`--ws`，沒給用 `$AOS_WS`，再沒有用目前資料夾）。一次 session 一個工作區，跟「叫的人決定 `AOS_WS`」（C-66、lib 規則 4）一致：Claude Code 就是那個叫的人，在設定檔寫好。不讓每次呼叫自己帶工作區——那要在 arguments 裡塞一個保留 key（例 `_ws`），等於改了工具的參數表，模型也會亂填。

**stack**：照 P-17／P-41 的做法——server 自己有一個 stack（`--stack`，沒給用 `$AOS_STACK`，再沒有 `$AOS_WS/.stack/`），**每個工具一個小格 `<stack>/<工具名>/`，跨呼叫延續**。理由：

- base 的純函數不用 stack，延續不延續都一樣。
- agent 包成的工具（lib/agent 的 `pyfix`、`claude`）本來就是「同一小格再叫＝接著上一次」；`interrupt: resumable` 也靠 stack 留著才成立。每次開新 stack 會把這兩件事都弄壞。
- 要「重新開始」＝換 stack（P-41：要忘記＝換 stack），是叫的人的事；以後可以加一個「清掉某工具小格」的管理用法，不放進工具本身。

代價：MCP 的世界預設工具是無狀態的，客戶端（或模型）不會知道 `writer` 第二次叫的時候記得上一次。這個資訊在 `_metainfo.idempotent: false` 裡，有轉成 `idempotentHint: false`，但沒有更明白的說法。

**整隻 agent（像 galtxt-b 本身）怎麼攤**：galtxt-b 的根沒有 `tool.json`，它的輸入是工作區 `new/` 裡的檔，不是 stdin——所以通用 server 不會把它攤出來，這是對的（P-41：沒有 `tool.json` 就不是可以叫的工具）。要讓 Claude Code 叫它，照 lib 現成的做法：另做一個工具資料夾，`_entry` 用 [agent_tool.py](../../../lib/agent/agent_tool.py) 的 `run_agent`（題目寫進子 agent 的 `ws/new/`、`aos-exec --ws` 跑、拿 `out/` 的答案），配一份 `tool.json`（參數就是場景那幾格）。轉接寫在工具自己的 `_entry`，server 不知道裡面是 agent（C-52）。

## 3. 跑很久的工作：進度與取消

galtxt-b 一題典型 26 秒、最壞 15 分鐘（`_metainfo.time_ms` `{"val": 26000, "max": 900000}`）。

**逾時**：server 有一個上限（原型 `--timeout-s`，預設 600），到了先 TERM 整群、2 秒後 KILL——跟 aos-exec 的 `timeout_ms`／`grace_ms` 同一套。更好的做法是拿 `_metainfo.time_ms.max` 當這個工具的上限（沒寫才用預設）。另外 **MCP 客戶端自己也有逾時**（Claude Code 有環境變數可調，數值要查），比 15 分鐘短的話，客戶端會先放棄。超過幾分鐘的工具建議改成兩段式：`start` 立刻回、`status`／`answer` 去拿——aos-ai 的 `start`／`wait`、lib/aos 的 `ask_agent`／`agent_status` 已經是這個形狀。

**進度**：客戶端呼叫時帶了 `progressToken`，server 才能送 `notifications/progress`。aos 沒有進度通道；能用的是 fsm 每跑完一格就寫一行的 `trace.jsonl`。做法：server 盯著「這個工具的小格」底下的 `trace.jsonl`，多一行就送一次進度（訊息寫格名，例「draft 跑完」）。但 server 是叫的人，看被叫者 stack 裡的檔，是 C-52 說的「偷看下層」，除非把 trace 認定成 fsm 對外公開的窗口（aos-ai 的 `trace` 命令其實已經在讀它）。所以這條列進 §5 第 4 條。原型沒做。

**取消**：客戶端送 `notifications/cancelled`（帶那次呼叫的 id）→ server 對那次的 aos-exec 送 TERM。aos-exec 轉給整群，fsm 會等那一格跑完、寫好 state 才走（P-36），所以：

| `_metainfo.interrupt` | 取消時 |
|---|---|
| `safe` | 直接 TERM，沒事 |
| `resumable` | TERM；stack 留著，下次叫同一個工具會接著做（這正是延續 stack 的理由） |
| `unsafe` | 殺了可能留下半成品。三種選擇：照樣 TERM、拒絕取消（MCP 允許 server 不理取消）、或照樣 TERM 但回一則警告。原則推不出來，列 §5 第 5 條 |
| 沒寫 | 當 `unsafe` 看（沒說≠安全，`_metainfo` 01 § 3） |

要支援取消，server 得一邊等工具跑、一邊讀 stdin 的下一則訊息——原型是單執行緒、一次一個呼叫，所以沒做；要做就加一條讀訊息的執行緒、記住「呼叫 id → 行程」。新版 MCP 規格另有實驗中的「tasks」（長工作先回一個號碼、之後再查），跟上面的兩段式是同一個想法，等它穩定再看。

**並行**：MCP 客戶端可能同時叫兩次。`_metainfo.parallel: false` 或有 `lock` 的工具，server 要排隊；原型一次只跑一個，自然排隊。

## 4. 這對「用 aos 做製作這套程式的程式」有什麼用

現在的分工：Claude Code 是操控者，靠 Bash 打 `aos-exec`、`aos-ai`、讀檔改檔。換成 MCP 之後：

1. **同一套工具，兩個操控者都能用**。lib 的工具（`read`、`edit`、`bash`、`ls`、`memory`、`spawn_agent`、`ask_agent`…）攤給 Claude Code 之後，Claude Code 做事用的工具，跟 aos 自己的 agent（agent-dan 形）做事用的工具，是**同一份資料夾**。以後要把「操控者」從 Claude Code 換成 aos 自己的 agent，工具不用改、只換腦——而且可以拿同一題讓兩邊各跑一次比較，這就是「製作這套程式的程式」的試驗台。
2. **哪些操控可以先交給 aos**：
   - 起 agent、丟題、跑、看狀態、拿答案（現在 Claude Code 打 `aos-ai spawn/ask/run/status`）→ 交給 lib/aos 的 `spawn_agent`、`ask_agent`、`agent_status`，經 MCP 叫。
   - 檢查類（lint、跑測試、`aos-json check`）→ 做成工具資料夾，唯讀的會帶 `readOnlyHint`，Claude Code 可以設成不用逐次問權限。
   - 生成骨架（`make_json`、`make_tool`）→ 同上。
   - 留在 Claude Code 的：跟使用者對話、決定方向、改 wf/ 文件——那是頂層的事。
3. **權限變細**：現在給 Claude Code 的是「能跑 Bash」，很粗。經 MCP 後是逐個工具給，`readOnlyHint` 讓唯讀的可以放行、會寫的照樣問。
4. **反方向也成立**：aos 的 agent 要用外面現成的 MCP server（瀏覽器、GitHub…），可以反過來做一個工具資料夾，`_entry` 當 MCP 客戶端去連那個 server、`tool.json` 抄它的 schema。這樣外面的工具也進了 aos 的工具箱，agent 不知道它是 MCP（C-52）。這是下一步，不在這次原型裡。

**經驗（給以後做「製作這套程式的程式」的人）**：

- `tool.json` 照 OpenAI function 去掉 `name` 的形狀定（P-41），這個選擇讓 MCP 幾乎零成本——以後再定介面，優先選外面現成協定的形狀。
- `_metainfo` 跟 MCP annotations 的分工剛好一致：annotations 是「給客戶端（人與權限系統）看的提示」，不是給模型看的；`_metainfo` 也是不給模型看（M10）。兩邊方向相同，所以能轉。
- MCP 沒有「破壞性 vs 只加」以外的行為軸、沒有成本與資源；aos 的 `_metainfo` 比它細，轉的時候只會丟資訊、不會缺資訊——放 `_meta` 帶著走，不要硬塞進 description（那會進模型的眼睛）。
- 捷徑掛載會讓同一個工具出現在好幾處；任何「掃資料夾找工具」的程式都要用實體路徑去重。
- 跑很久的東西不適合一次呼叫等到底：先想好兩段式（start／status），不要指望客戶端逾時夠長。

## 5. 跟既有原則的衝突（不拍板，列給使用者）

1. **M10（`tool.json` 給模型看、`_metainfo` 給 kernel 看，不合併）**：原型把 `_metainfo.summary` 放進 `annotations.title`、整份 `_metainfo` 放進 `_meta`。MCP 說這兩格是給客戶端看的，但**有沒有客戶端把 title 或 `_meta` 塞進模型的 context，各家不一定**。後果：如果有，就違反「`_metainfo` 不進 prompt」（使用者 10-15「小 LLM 模型的判斷力不足，會被這個搶走注意力」）。選項：(a) 照原型，賭客戶端不給模型；(b) 只轉成布林提示，不帶 title 與 `_meta`；(c) 加開關。
2. **C-52／C-53（下層的錯不轉述、不讀下層 stderr）**：原型把工具的 stderr 只寫進 server 自己的 stderr（客戶端會記在日誌），結果裡只有 stdout＋「結束碼 N」。lib 的工具沒問題（錯誤那一行 stdout 也有）；但**不照 lib 契約的資料夾程式（例 agent 本身、aos 的指令）錯只印在 stderr，模型只看到「結束碼 1」**，不知道錯在哪。選項：(a) 照原型，要讓模型看到錯的工具自己照 lib 規則 3 把錯印進 stdout；(b) 非 0 時把 stderr 最後一行也附上（轉述下層，違反 C-53）。
3. **C-69（aos 只訂環境變數）**：server 需要「根、工作區、stack、上限」四個設定。原型全用旗標、不新增 `AOS_*` 環境變數，沒衝突；但如果以後要拿 MCP 的 roots 自動當 `AOS_WS`，那是 aos 之外多一條「roots → 工作區」的規則，要另外定。
4. **C-52（想看子層的東西要另外透過其他機制，沒機制就別碰）**：進度回報要讀被叫工具小格裡的 `trace.jsonl`。要做進度，得先認定「fsm 的 trace 是對外公開的窗口」，或另訂一個工具自己寫進度的地方（例 stack 裡固定一個 `progress.txt`，由工具自己寫）。後者是新慣例。
5. **`_metainfo.interrupt: unsafe` 被取消時怎麼辦**：原則推不出來（§3 表裡三個選擇）。
6. **C-56 KISS／少用 sh**：沒衝突。原型 argv 直接跑 `aos-exec`、不經 `sh -c`；通用一支、沒有每棵樹各一份。只提一點：server 本身是多一層程式，它該不該做成 aos 的資料夾程式（`_entry`＋`_metainfo`）——MCP server 是長駐的、靠 stdin 一則一則收，跟「跑一次就結束」的資料夾程式形狀不同；硬套會很怪，建議不套，留在 aos 外面當轉接。
7. **P-41（工具名＝資料夾名）**：MCP 的名字只收英數、`_`、`-`（客戶端常限 64 字），而且一個 server 底下要唯一。所以原型用「路徑換 `__`」，`clock` 變 `base__clock`。後果：模型在 Claude Code 看到的名字跟 agent 的腦看到的名字不一樣（腦看到 `clock`）。選項：(a) 照原型帶路徑；(b) 只用資料夾名，撞名才帶路徑。
8. **C-61（不靠 PATH）**：server 要在 PATH 上找 `aos-exec`。這跟 aos 自己的指令一樣（「由呼叫者自己放進 PATH」），不算衝突，記一下。

## 6. 原型：`plan/mcp/aos_mcp.py`

```
aos_mcp.py ROOT [--ws WS] [--stack DIR] [--timeout-s N]
```

純 Python 標準庫、stdio、一行一則 JSON-RPC。做了 `initialize`、`tools/list`、`tools/call`（加 `ping`），通知不回、其他方法回 -32601。`_metainfo` 只轉有寫的格（沒寫就不給 annotation，讓客戶端用 MCP 的保守預設），整份放 `_meta["aos/metainfo"]`。沒接進任何設定檔（`.mcp.json`、`.claude/` 都沒動）。

**跑過的（2026-10-25）**：PATH 放 `proto8/impls/aos-exec/bin`，請求一行一則從 stdin 餵：

```sh
PATH=$PWD/proto8/impls/aos-exec/bin:$PATH python3 proto8/topdown/galtxt-b/plan/mcp/aos_mcp.py proto8/lib --ws <空資料夾> < req.jsonl
```

請求：`initialize` → `notifications/initialized` → `tools/list` → `tools/call base__math {"expr":"17*23"}` → `tools/call base__clock {}` → `tools/call base__math {"expr":"__import__(1)"}` → `tools/call nope`。回：

```
{"id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":false}},"serverInfo":{"name":"aos-mcp","version":"0.1"}}}
id 2：29 個工具 agent__claude agent__codex agent__pyfix aos__agent_status … base__clock … base__math … base__write
  base__math    annotations {"title":"算一個算術式子，回結果","readOnlyHint":true,"idempotentHint":true,"openWorldHint":false}
  base__write   annotations {"title":"把整份內容寫進工作區裡一個檔（建或整份蓋掉）","readOnlyHint":false,"idempotentHint":true,"openWorldHint":false}
  agent__claude annotations {"title":"把一句話交給 claude CLI 做…","readOnlyHint":false,"idempotentHint":false,"openWorldHint":true}
{"id":3,"result":{"content":[{"type":"text","text":"391\n"}]}}
{"id":4,"result":{"content":[{"type":"text","text":"2026-10-25T07:30:42Z\n"}]}}
{"id":5,"result":{"content":[{"type":"text","text":"math: ExprBad 不認得的寫法：Call\n"},{"type":"text","text":"結束碼 1"}],"isError":true}}
{"id":6,"error":{"code":-32602,"message":"沒有這個工具：nope"}}
```

工作區的 `.stack/` 底下多了 `base__clock/`、`base__math/` 兩個小格（每個工具一格）。

- 根指 `proto8/topdown/galtxt-b`：攤出 `lib__lint`、`lib__plan_lint` 兩個（`check/tools/lint`、`writer/tools/lint` 兩條捷徑沒有重複出現）；`tools/call lib__lint {}` 回 `lint: ArgumentsBad 缺 text…`＋isError。第一版是「先走到的路徑贏」，攤出來叫 `check__tools__lint`，改成取實體自己的路徑。
- 逾時：`--timeout-s 1` 叫 `base__bash {"command":"sleep 30; echo done"}`，約 1 秒回「結束碼 143（逾時，被停掉）」＋isError，事後查沒有留下 `sleep` 行程。

**沒做的**（要做時照 §3）：取消（要多一條執行緒讀訊息）、進度、照 `_metainfo.time_ms.max` 定逾時、照 `parallel`／`lock` 排隊（現在一次一個，自然排隊）、`outputSchema`、resources。
