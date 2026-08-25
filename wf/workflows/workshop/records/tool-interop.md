# aos 與 coding agent、skills、MCP 的協作
← [workshop](../README.md)｜前情：[核心行程與子行程](core-process-and-subprocess.md)／[四個懸而未決的選擇](four-open-choices-tradeoffs.md)／[agent loop](agent-loop-architecture.md)／[回頭審視](step-back-review.md)／[隨意發想](free-ideation.md)／[workflows on aos](workflows-on-aos.md)

| | |
|---|---|
| **主題** | aos 如何與 pi coding agent、skills、MCP 等現有工具協作 |
| **開場** | 2026-08-25 |
| **已跑輪數** | 主輪＋追問輪 |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員（作業系統／體系結構） / 要接這個工具的開發者 |
| **缺哪個角度** | 沒有「普通用戶」——使用者先前拿掉了那個身份。所以**沒有「這東西人看不看得懂」的視角** |
| **reasoning effort** | `xhigh` |
| **參與者** | **與前幾場是同一批人**（同一批 codex session 續下來） |

## 先讀這段（500 字懶人包）

最小 runtime tool 組是三支，四位 4／4 相同：`aos deliver` 原子投一批 instruction、
`aos status --json` 看 queue／`.runi`、`aos exec` 推一回合；`init` 只屬建置期。

`deliver` 從 stdin／檔案讀 instruction，發布前驗證，寫 `.aos/inst.tempd/*.json.temp`，完成後 rename
成 `.json`；成功回 JSON receipt，失敗回可讓模型修參數重試的結構化錯誤。agent **直接 tool-call
deliver**，不再把自然語言交給 adapter 猜成 JSON。

同一套 CLI 可服務三種入口：pi 用 `.agents/skills/aos/SKILL.md` 教內建 bash 工具呼叫；腳本直接
exec；支援 MCP 的 agent 用無狀態薄殼轉同一語意。pi 本身明確不做 MCP。`aos exec` 的 stdout 會
混流，不能當協定；stdout→agent stdin 只能傳專用的 request／context，不可直接管 raw exec 輸出。

---

本場有兩輪。主輪先問 coding agent、skill、MCP 與權限怎麼分層；追問輪因使用者一句話，拿掉了
主輪最重的一段 adapter：

> **agent 的自然語言輸出變成 inst json？直接給 tool 啊。**

也就是說，agent 不輸出一段等人猜的自然語言；它呼叫一支有 schema 的 tool。JSON 是否合法、
怎麼原子寫入，是 tool 的責任。那支 tool 正好是三步交接中唯一尚未實作的「投遞」。因此下面先
放追問輪的收攏結果，再回頭記主輪的整體分層。

## 追問輪：那支投遞 tool 到底長什麼樣

### `aos deliver` 的合成版 `--help`

**四位獨立地都把工具命名為 `aos deliver`**，也都讓一個呼叫等於一批原子投遞。共同形狀可以先
寫成：

```text
aos deliver [WORLD] [-f FILE|-] [--key K] [--durable]

讀取：FILE 或 stdin；WORLD 預設目前資料夾。
輸入：一筆 instruction object 或一批 instruction array（是否兩者都收，仍未拍板）。
動作：全批驗證成功後，原子發布到 WORLD 的 instruction 投遞區；不執行、不彙整。
成功：stdout 輸出一筆 JSON，至少含 published 狀態、count，receipt 是否必備待定。
失敗：不發布；輸出結構化 JSON 錯誤並使用非零退出碼。
```

這是共同比例最高的介面形狀，不是已定規格。四份原始 `--help` 的差異如下：

| 誰 | 命令形狀 | 輸入單位 | 成功輸出 | 額外旗標／特點 |
|---|---|---|---|---|
| **資深工程師** | `aos deliver [--key K] [--durable] <inst-file>` | 只明寫 instruction array；一 array＝一批 | `{"ok":true,"receipt":"R","state":"published\|already","hash":"…"}` | 以 inst-file 當目標；把 key／durable 放進第一版 |
| **資深架構師** | `aos deliver [--file FILE] [FOLDER]` | 單筆 object 或 array | `{"ok":true,"delivery":"1234-k7pz","count":2}` | FOLDER 預設 `.`；沒有 key／durable 旗標 |
| **資深研究人員** | `aos deliver [W] [--to X.json]` | 單筆或 array | JSON，欄位未定 | W 預設 `.`；允許廣義 `--to`，由 `X.json` 推出 `X.tempd/` |
| **要接工具的開發者** | `aos deliver [WORLD] [-f FILE\|-] [--key K]` | 單筆或 array | `{"status":"published","receipt":"R","count":2}` | WORLD／FILE 均有預設；保留 key，沒有 durable |

三位允許單筆 object 或 array，工程師只明寫 array；所以「單筆自動視為一筆批次」很接近共同形狀，
但不是 4／4。`--key` 只有工程師與開發者在追問輪簽名中保留，架構師、研究人員沒有；`--durable`
只有工程師列入。這兩項不能從表決外推成已定。

更重要的是，`--key` 與[回頭審視](step-back-review.md)仍有未解矛盾：那輪四位剛指出 aggregate 會
刪除投遞檔，沒有 ledger 就不能承諾跨回合 Already／Conflict。本輪工程師、開發者重新寫回 key，
卻沒有補 ledger；架構師、研究人員則乾脆沒放。故 key 可以是候選 correlation／檔名，**目前仍
不能據此宣稱跨回合冪等。**

### 寫到哪裡、檔名怎麼配

**四位獨立地都給出同一個發布順序**：

1. 找到目標 world 的 `.aos/inst.tempd/`；研究人員的廣義版本是 `X.json` 對應 `X.tempd/`。
2. 以排他方式建立 `<pid>-<suffix>.json.temp`。suffix 分別是 nonce、隨機尾碼、首個空 `n`、
   `seq＋nonce`；**四位都沒有只靠 PID 保唯一。**
3. write-all；若有 durable 契約再做相應 fsync。
4. 驗證與寫入都完成後，在同一目錄 rename 去掉 `.temp`，成為 `.json`，此刻才讓彙整者看見。
5. 一個呼叫只發布一個檔；array 內順序保留。開發者另外明講：多次投遞的不同檔案之間不承諾順序。

這支 tool **只補「投遞」**。彙整、取件、執行、釋放仍由 `aos exec` 負責；它不把 payload 直接寫
進 `inst.json`，也不因投遞成功就推世界一回合。

### 退出碼還沒有共同編號

四位只對 `0＝成功` 有穩定重疊；其餘人把相同號碼分給不同錯誤，不能把任何一份直接稱為共同
契約：

| 誰 | 0 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| 工程師 | 成功／Already | 用法 | 格式／大小 | key 衝突 | I/O／耐久 | — |
| 架構師 | 成功 | payload 無效 | world／版本無效 | I/O／rename | — | — |
| 研究人員 | 成功 | 用法 | — | 驗證 | I/O | — |
| 開發者 | 成功／Already | 用法 | JSON | schema | key 衝突 | I/O |

已成形的是**錯誤種類要分開**：用法、world／版本、JSON parse、schema／大小、key conflict（若有
key）、I/O／rename／durability。數字、Already 是否算 0、world 無效與 payload 無效誰先判，仍要
拍板。

### 誰驗證、驗不過怎麼回

**四位獨立地都要求 Deliver 在 rename 前驗證完整 payload；驗不過就整批失敗，不發布任何可見
檔案。**工程師要求與 executor 共用 parser；開發者要求 aggregate 仍重驗，防止有人繞過 tool
直接塞檔。`$ref`／`$env` 這類執行期資料不在投遞時求值；能做的是驗它們的結構。

`.bad` 也因此有清楚邊界：它只隔離**繞過 Deliver**、直接進投遞區的壞檔。正常 tool-call 驗證
失敗，不留下 `.bad`，也不留下可見 temp；錯誤直接回給呼叫者修正。

## 給模型看的錯誤訊息

這題四份輸出非常接近。**四位獨立地都給了 JSON，而不是一句人類 prose**；架構師、開發者明確
指定寫到 stderr。模型需要的不是「invalid input」，而是能定位、能改參數的欄位：

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_FIELD",
    "record": 2,
    "pointer": "/1/argv/0",
    "expected": "string",
    "actual": "number",
    "hint": "argv 必須是字串陣列"
  }
}
```

四人的欄位名有 `path`／`field`／`at`／`pointer`，code 也有大寫與 snake_case 兩種；共同語意是：

- 哪一筆 record；
- JSON Pointer 或至少欄位路徑；
- expected 與 actual；
- 穩定 machine code；
- 一句可執行的 hint，讓模型修 tool arguments 再呼叫。

**沒有人真正回答「給人看的版本長什麼樣」。**四位都把 machine JSON 做得很具體，但沒有提出
human-readable renderer、是否預設 JSON、或用 `--json` 切模式。這一塊不能由書記補答案；只能記
成追問輪仍漏掉的半題。

### 最小 tool 組

| 功能 | 入選情況 | 共同語意 | 命名差異 |
|---|---|---|---|
| **Deliver** | **4／4** | 驗證後原子投一批，不執行 | 四位都叫 `aos deliver` |
| **Status／Inspect** | **4／4** | JSON 回 world/version、idle／ready／running／blocked、pending queue、`.runi`，可選查 receipt | 架構師、研究人員、開發者叫 `status`；工程師叫 `inspect` |
| **Exec** | **4／4** | 推指定 world 一回合；輸出與退出另按 executor 契約 | 四位都叫 `exec`，研究人員稱「推一步」 |
| **Init** | 三位提到，但不列入 runtime 三支 | 建立 world／版面 | 工程師說它屬建置期；研究人員、開發者列為初次使用；架構師的最小組沒列 |

世界內容不用另造 read tool：資深架構師指出 coding agent 本來就有 read／ls；pi 也已有 read、write、
edit、bash。aos 的 tool set 應補磁碟交接語意，不重做 agent 已有的檔案工具。

### 一套 CLI 能不能同時服務 skill／MCP／腳本

**四位 4／4 都答「一套語意夠」。**pi skill 與 shell 腳本直接執行 CLI；MCP 只把 typed arguments、
stdin、stdout、stderr、退出碼轉接成 tool result，不能另寫一套投遞命名與驗證規則。

實作層仍有一個小分叉：工程師偏好共用 lib＋CLI，MCP façade 直接呼叫 lib；架構師、研究人員偏好
MCP 轉呼 CLI；開發者接受同一 lib 或 CLI。共同限制不是「一定 spawn subprocess」，而是**只有一份
Deliver 語意與 parser**。

### 四位收回／改寫的

使用者那句「直接給 tool」之後，**四位各自都收回了主輪的自然語言解析層**：

| 誰 | 收回什麼 | 改成什麼 |
|---|---|---|
| 工程師 | `agent JSON → adapter → deliver` 中 adapter 負責解析／猜測 | adapter 只轉 tool protocol；agent 直接呼叫 Deliver |
| 架構師 | adapter 解析 agent 自然語言，再驗 instruction | tool-call 的 arguments 就是待驗 payload；失敗作為 tool result 回模型修正 |
| 研究人員 | `aos prompt \| pi \| aos ingest --adapter pi` | 取消 ingest；agent 呼叫 Deliver，final 文字不進交接 |
| 開發者 | `aos accept W --adapter pi` | 取消 accept／解析；stdout→stdin 只傳上下文，instruction 由 tool-call Deliver |

連帶收回的還有 `response.bad/`／`agent.invalid` 作為正常解析失敗路徑：模型若 tool-call 錯，Deliver
直接回結構化錯誤；模型 final 文字本來就不是 instruction，不需要隔離。原始 response 若要留作
觀測仍可由 agent／driver 保存，但不再由一支 ingest 猜它是不是 JSON。

---

## 主輪：aos 怎麼跟現有工具協作

### pi 與本場的已知前提

這裡的 pi 是 [`earendil-works/pi`](https://github.com/earendil-works/pi)，不是泛稱，也不是本機 PATH
上的 `agy.exe`。使用者已親口更正：**`agy.exe` 是 Gemini 的，不是 pi。**

pi 是 TypeScript／Bun 的極簡 coding agent 終端，包含多供應商 LLM API、agent runtime 與互動 CLI；
狀態在 `~/.pi/agent/`，session 按工作目錄保存。對行程整合有 `-p/--print`（可吃 stdin）、
`--mode json`（JSON lines 事件）、`--mode rpc`；可用 `--no-session`、`--session <path|id>`、continue、
resume、fork。它從 `~/.pi/agent/skills/`、`.agents/skills/`、`.pi/skills/` 找 skill，也會讀
`AGENTS.md`／`CLAUDE.md`。

更關鍵的是它**明文不做三件事**：不做 MCP，建議「CLI＋README／Skill」或 extension；不做權限
彈窗，把隔離交給 Gondolin／Docker／OpenShell；不做 sub-agent 與 plan mode。這與 aos 近幾輪收回
內建 orchestration／權限系統的方向很接近，也直接限制了 pi 的接法。

使用者原本的方向是：

> 我預期的是，**這些 coding agent 可以是入口，然後 aos 作為他們的 MCP 或 tool set**。
> 也可以讓 **aos 產出的 stdout 導向到 coding agent 的 stdin**。

四位都說方向成立，但要拆成不同 agent 的原生入口：**pi 不是 MCP 路徑；pi 走 skill＋CLI（或日後
extension），支援 MCP 的其他 agent 才走 MCP façade。**

### 誰在上面、誰在下面

四位共同畫出的層次是：

```text
使用者
  │
  ▼
coding agent（pi／Codex／Claude…）── 管對話、session、批准與既有 read/bash tools
  │  skill／CLI tool-call，或 MCP typed tool-call
  ▼
aos CLI／共用 lib ──────────────── 管 Deliver、Status、Exec 的磁碟回合語意
  │
  ▼
world folder ───────────────────── 真相：queue、.runi、kernel、request／result
```

資深工程師的句子收得最短：

> **CLI 是共同母語，skill 與 MCP 只是入口；磁碟上的 request／result 才是契約。**

這個方向同時支援兩種產品場景：

1. **coding agent 是入口。**人在 pi／其他 agent 對話，agent 依 skill 或 MCP 呼叫 status、deliver，
   視權限再 exec。這是使用者原話最直接的版本。
2. **aos 批次召喚 coding agent。**world／driver 準備 request，啟動 `pi -p`／其他 CLI，安全保存結果，
   再由 agent 的 tool-call 或 driver 推進下一步。

工程師與架構師**兩位獨立地都問**：第一個真正要做好的產品場景是哪一個？兩者可共用 CLI，
但互動批准、session、結果捕捉與 crash 責任不同。

### stdout → stdin 能成立，但不能拿 `aos exec` raw stdout 當協定

**四位獨立地都指出**：`aos exec` 會直接承接任意子指令 stdout，平行時還可能交錯；把它管進
`pi -p`，模型收到的是無 envelope 的混合文字，無法知道來源、turn、成功與否。

追問輪之後，閉環的下半段也改了：

```text
aos 的專用 request／context 輸出 ──► pi -p／其他 agent 的 stdin
                                        │
                                        └─ agent 直接 tool-call `aos deliver`
                                           （不再把 stdout 送進 ingest parser）
```

主輪提出過 `aos prompt`／`aos emit`，但追問輪研究人員明確收回整條 `prompt|pi|ingest`，其餘三位也
只收斂了 Deliver，**沒有收斂出一支新的 context exporter**。所以使用者說的 stdout→stdin 可以作為
方向，但目前只知「不能是 raw exec stdout」；究竟由 `status --json`、request file，還是日後專用
`prompt／emit` 供應上下文，仍缺答案。

### coding agent 的 session 只可當快取

**四位獨立地都先選 `--no-session` 作可攜預設**：對話歷史／request 留在 world，看得見、可搬、
可重建；pi session 若啟用，只加速續談，不能成為世界唯一真相。`--fork` 也只 fork agent 快取脈絡，
不定義 aos 子世界身分。

四位主輪都提到把 pi session 放 `W/.aos/pi` 或 `W/.aos/adapters/pi/sessions`，並使用
`--session-dir`。但本場提供的 pi 介面事實只列 `--session <path|id>`、continue、resume、fork，
**沒有列出 `--session-dir`**；四位也都標記 JSON event／RPC／session 磁碟格式是否跨版本穩定為
不確定。因此這段不能寫成可用命令：要先核對 pi 實際支援的 session 定址方式，再決定如何把綁定
記進 world。

## skills 怎麼接

**四位獨立地都選 `.agents/skills/aos/SKILL.md`**，因為 pi 會發現這個跨 agent 路徑，也能用
`--skill <path>` 明載。skill 應告訴 coding agent：

- 什麼情況用 aos，以及 Deliver → Status → Exec 的次序；
- 每支命令的參數、JSON stdout／stderr 與退出碼；
- `.runi` 代表什麼，blocked 時不要自行刪；
- **禁止直接寫 `.aos/inst.tempd`**，必須呼叫 Deliver；
- exec 等於讓 world 跑 POSIX 指令，何時需要批准／container；
- recovery 與錯誤修正範例。

工程師把 `references/` 指向磁碟規格、`assets/*.json` 放 instruction 模板；架構師提
`scripts/validate-reply`，但追問輪拿掉自然語言解析後，這類 script 應只驗 tool payload／參考資料，
不再猜 final 文字。開發者也讓 skill 帶規格與必要腳本。

四位還特別分開三個容易混的詞：**skill 是上層 agent 的操作手冊；workflow 是耐久政策／流程；
instruction template 是資產。**三者可以放在同一個 skill package 方便取用，不能當成同一概念。

對 pi 而言，skill 本身主要是文字指引，實際呼叫可由既有 bash tool 執行 `aos`。若要在 pi 裡註冊
有 typed schema 的原生 tool，依 pi 的立場應寫 extension；四位本輪沒有設計 extension 介面。

## MCP 怎麼接，或為什麼 pi 不接

pi 已明確選擇**不做 MCP**。所以「aos 作為 pi 的 MCP」這條字面路徑不成立；pi 的第一級整合面是
CLI＋SKILL.md，或更深時使用 pi extension。

對支援 MCP 的其他 coding agent，**四位獨立地都提出無狀態薄殼**：

| MCP tool（合併命名） | 轉接的 aos 語意 | 是否預設暴露 |
|---|---|---|
| `aos_status(world)`／`world_status(path)` | `aos status WORLD --json`；回 queue、world/version、`.runi` | 是 |
| `aos_deliver(world, instructions[, key])` | 同一份 Deliver parser、驗證與原子投遞 | 是 |
| `aos_exec(world)`／`step(path)`／`exec_once(path)` | `aos exec WORLD` 推一回合 | 四位都要求比 status／deliver 更嚴格；預設關閉或明示開啟 |
| `aos_runi(world)`／receipt query | Status／Inspect 的局部查詢 | 研究人員、工程師提出；是否獨立成 tool 未定 |

MCP server 每次呼叫都重讀 world folder，**記憶體不是狀態真源**；用 `--root`／root allowlist 限制
可見 world，不提供任意 shell。它可以 subprocess 轉 CLI，也可以共用 lib，但不能重新實作投遞
協定、改錯誤 code 或另養 session 真相。

## 權限這塊

pi 沒有權限系統，aos 也不是 sandbox。**四位獨立地都把隔離責任交給入口 agent 所在的
container／micro-VM／OS sandbox**，而不是在 executor 裡長一套批准彈窗。

共同的最小暴露面是：

- Status／Inspect 可預設開；
- Deliver 與 Exec 分開授權。Deliver 雖不立即執行，但可排入危險 POSIX instruction，所以仍需
  root allowlist／instruction template 或等待人審；
- Exec 等同允許 world 跑 bash／任意 POSIX 指令，MCP server 必須同權或更低權，且預設不開；
- adapter／skill 不接受模型任意 argv 直通高權 shell；具名工具映射、人工批准或 container 由上層
  coding agent 負責。

資深架構師的邊界是「批准政策屬 agent extension 或沙盒，不塞進 executor」；要接工具的開發者
則主張 agent 預設只排隊，Exec 明開或由人操作。這也留下待問的產品選擇：互動 agent 是否預設可
Exec，還是只能 Deliver 等待批准。

## 把這場研討會搬到 aos 上

四位身在這個 workshop 裡，畫出的資料夾名稱不同但回合相同：

```text
topic-world/
├─ briefs/R1/                    # 議題與四份角色任務
├─ rounds/R1/responses/<role>.md # 或 raw/R1/<role>.md
├─ sessions.json                 # agent session 只是綁定／快取
└─ record.md                     # 書記最後寫的紀錄
```

1. 主持人把四份參與者工作原子投遞成同一輪；四個 coding agent 可平行執行。
2. 每位結果先完整落到自己 `<role>.md`，連同 exit／完成狀態提交。
3. join 確認四份都完成後，再 Deliver 一筆書記 instruction。
4. 書記只讀 brief＋raw responses，寫 `record.md`；下一輪若續場，session id 只作快取提示。

**四位獨立地都說第一個立即卡點是 Deliver 尚未實作。**其後還有三個實際洞：

- pi／Codex 等 coding agent 的 JSONL、RPC、final event、session id 格式是否穩定，四位都不確定；
- `-o`／stdout capture 不是 aos 的原子發布；遠端可能已完成／付費，本機 raw 尚未落盤，重跑有
  unknown 視窗（工程師、架構師、研究人員、開發者都提到）；
- exit、response file、session 綁定與「這一位真的完成」目前沒有一個共同 commit，join 仍要外部
  driver 判斷。

追問輪刪掉 adapter 的**內容解析**，沒有刪掉行程 adapter 的**傳輸責任**：啟動 agent、捕捉事件、
原子保存 raw、記 exit／unknown，仍要有人做。tool-call Deliver 解的是 agent 如何合法投 instruction，
不是主機如何保證一支遠端 coding agent 的 Markdown response 已落盤。

## 大家問出來的問題

1. **第一個產品體驗是哪一個：人在 coding agent 對話中呼叫 aos，還是 aos 無人值守地批次召喚
   coding agent？**工程師、架構師**兩位獨立地都問了**。兩者共用 CLI，但 session、批准與
   unknown 責任不同。

2. **第一個入口先做 pi skill，還是先做給其他 agent 的 MCP？**研究人員直接問。pi 不支援 MCP，
   所以這實際是在問第一個要驗證的宿主是 pi，還是 MCP ecosystem。

3. **可攜的 `--no-session` 重播，與快速續談的 session，哪個優先？**研究人員直接問；四位都把
   session 當 cache，但也都想過續談模式。

4. **pi 的 JSONL final event、RPC 與 session 格式是否有跨版本穩定承諾？實際支援的 session 定址
   旗標是什麼？**；**四位都標記格式不確定**，本場事實表沒有列參與者反覆使用的 `--session-dir`。

5. **coding agent 預設可呼叫 Exec，還是只准 Deliver、等人批准後再推？**開發者直接問；架構師、
   研究人員也要求 Deliver／Exec 分權。

6. **Deliver 是否接受單筆 object？`--key`／`--durable`／`--to` 哪些進第一版？**三位接受單筆，
   key 只有兩位，durable 只有一位，`--to` 只有研究人員；目前沒有 4／4。

7. **沒有耐久 ledger 時，key 的作用只是 correlation，還是仍要承諾 Already／Conflict？**工程師、
   開發者本輪放回冪等狀態；架構師、研究人員省略，且四位在回頭審視曾一起指出 ledger 缺口。

8. **成功 JSON、錯誤 JSON、退出碼要採哪一份；給人看的錯誤如何與模型 JSON 分開？**四位都給了
   machine JSON，但欄位與 code 不同，且沒有人完成 human-facing 半題。

9. **stdout→stdin 的上半段由誰產生穩定 context？**raw `aos exec` stdout 已被四位排除；主輪的
   prompt／emit 沒有在追問輪留下共同介面。

## 明顯的坑

- **為 pi 先做 MCP server。**pi 明確不做 MCP；它的自然路徑是 CLI＋skill，或 pi extension。

- **把 PATH 上的 `agy.exe` 當 pi。**使用者已澄清它是 Gemini；整合測試若用錯 executable，所有
  event／session 結論都會對錯產品。

- **把 raw `aos exec` stdout 當 agent protocol**。**四位獨立地都指出**子指令輸出任意且可能混流；
  沒有 turn／source／exit envelope，不能安全 pipe 給模型。

- **重新長回「自然語言→adapter 猜 JSON」**。**四位在追問輪 4／4 收回這層**；agent 應直接
  tool-call Deliver，錯誤作為 tool result 回去修。

- **讓 pi session 成為 world 真源**。**四位都只接受 session 作可丟快取**；遺失後必須能從 world
  request／history 重建。`--fork` 也不能偷偷定義 aos 子世界身分。

- **把未核對的 `--session-dir` 寫進 skill。**本場提供的 pi 介面沒有這個旗標；先驗實際 CLI，
  否則 skill 第一條 session 指令就可能不可用。

- **CLI、skill、MCP 各自實作一次 Deliver**。**四位都要求單一 parser／單一原子投遞語意**；入口
  可不同，receipt、錯誤與檔名契約不能分叉。

- **MCP 預設開 Exec，卻因為 server 有 `--root` 就以為安全。**Exec 可跑任意 POSIX 指令；path
  限界不是完整 sandbox，仍需 container／同權或降權執行。

- **正常驗證失敗也丟 `.bad`。**tool caller 應立即收到可修正的 JSON 錯誤；`.bad` 只處理繞過
  Deliver 的壞檔，否則模型得去掃磁碟才知道參數錯了。

- **看到 `--key` 就宣稱跨回合 exactly-once。**沒有 ledger，aggregate 刪檔後無從辨認舊 key；
  本輪兩位重新提出 key，沒有補掉這個前情缺口。

- **agent 直接 Deliver 後，就以為 workshop 的 raw response capture 也解決了。**Deliver 解的是
  instruction 入 queue；付費 agent 的 Markdown／JSONL 是否完整落盤，仍有另一個 unknown 視窗。

## 續場資訊

本輪沿用前幾場的四個 codex session；它們仍保留完整前情。session id **只在 office Windows
那台機器有效**；`codex exec resume <id>` **不吃 `-s` 與 `-C`**。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（OS／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

---

## 轉交提案（未拍板，不自行改規格／roadmap）

1. **先拍板並實作 `aos deliver` 的最小公開契約。**需決定 WORLD／FILE 位置參數、單筆是否接受、
   `--key`／`--durable`／`--to` 是否進第一版、成功／錯誤 JSON、退出碼、receipt、檔名 suffix，以及
   key 在沒有 ledger 時是否只作 correlation。四位已對原子寫入順序與只負責投遞形成強訊號。

2. **把 runtime tool set 收成 Deliver＋Status／Inspect＋Exec。**需拍板查詢工具叫 `status` 還是
   `inspect`、回哪些 world／queue／`.runi` 欄位，以及 Exec 是否維持現有 CLI；Init 另列建置期，
   不占 coding agent 的最小三支。

3. **若先驗 pi，做 `.agents/skills/aos/SKILL.md`＋CLI，不做 pi MCP。**skill 應教直接 tool-call／
   bash 呼叫 Deliver、讀 machine JSON、處理 `.runi` 與批准；先核對 pi 真正支援的 session 旗標、
   JSONL final event 與 RPC 穩定性，不把 `--session-dir` 當既定事實。

4. **若要支援其他 MCP agent，再做無狀態 façade。**第一版只暴露 Status＋Deliver；Exec 明示 opt-in。
   每次重讀磁碟、用 root allowlist 限 world、共用同一 CLI／lib 語意，server 記憶體與 agent session
   都不當真源。

5. **拍板 coding agent 的預設權限。**可選「只 Deliver、由人 Exec」或「在 container 內允許自動
   Exec」；aos 本身不補權限彈窗。無論哪個，模型輸出不得以任意 argv 穿透高權 MCP／adapter。

6. **若要完成 stdout→stdin 方向，另定專用 context 出口。**不能用 raw `aos exec` stdout；可從
   request file、既有 Status JSON，或日後 `aos prompt／emit` 選一種。追問輪只定了回程用 Deliver，
   去程仍需使用者拍板是否值得做成 core tool。

7. **用這場 workshop 當第一個端到端 interop 驗證。**前置是 Deliver、四個 agent 結果的原子
   capture、完成 commit 與 join；先跑一輪 briefs→四 responses→書記 record，逐點測 agent 已付費
   但 raw 未落盤的 unknown。這能同時驗 pi／其他 CLI adapter 與 aos 磁碟契約。

8. **正式刪除 ingest／accept 的自然語言解析責任。**adapter 仍可負責啟動 agent、搬 JSONL、保存
   raw 與 exit，但不再解析 final prose 來猜 instruction；instruction 只能經 typed Deliver tool-call
   進 queue。
