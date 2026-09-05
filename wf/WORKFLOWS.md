# WORKFLOWS — 工作流派發器

← [AGENTS.md](../AGENTS.md)｜專案地圖 [INDEX.md](INDEX.md)｜結構 [STRUCTURE](STRUCTURE.md)

你（使用者）說要做某件事 → **從這張表選對應工作流 → 讀它的「入口檔」→ 就知道要做什麼**。每個工作流的細節都在它自己的入口檔，不在這裡。

**可以跳流程**：單行或小範圍、低風險、不跨 session 的修正；純查詢或一次性回答，不留 durable 知識；使用者明確要求快速處理；既有工作流只會增加同步成本而不降低風險。跳流程不等於跳過工程規矩——仍要讀必要上下文、不破壞使用者改動、能測就測（鐵律 1）。

## 你想做什麼 → 用哪個工作流

### 開發 flavor

碰原始碼的工作流共用 [common/conventions](workflows/common/conventions.md)（程式碼慣例 + code map 維護鏈）與 [common/code-map](workflows/common/code-map.md)（哪個檔負責什麼）。

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）|
|--------------|--------|-------------------|
| 「我想開發 / 修改某個功能」「**修 bug**」 | **feature-dev** | [workflows/feature-dev/README.md](workflows/feature-dev/README.md) |
| 「**加一個新的小專案 / 新工具**」 | **add-subproject** | [workflows/add-subproject.md](workflows/add-subproject.md) |
| 「**我有個 idea**」「把這個構想記下來」「要重新拷問 X」 | **ideas** | [workflows/ideas/README.md](workflows/ideas/README.md)（13 章新構想集＋待決定總表；舊構想在 ideas/archive/）|
| 「**接下來做什麼**」「照進度表推進」「動工前該讀什麼」 | **roadmap** | [workflows/roadmap.md](workflows/roadmap.md) |
| 「**開個研討會討論 X**」「找幾個 agent 一起腦力激盪」「給我一些靈感」 | **workshop** | [workflows/workshop/README.md](workflows/workshop/README.md)（已累積的紀錄與待決問題見 [INDEX](workflows/workshop/INDEX.md)）|
| 「**辦個黑客松**」「找幾個 agent **各自去試做** X」「別再討論了，讓他們隨便做做看」 | **hackathon** | [workflows/hackathon/README.md](workflows/hackathon/README.md)（已辦場次見 [INDEX](workflows/hackathon/INDEX.md)）|
| 「**直接去試試看**」「跑個實驗看會怎樣」「別再想了，做一次」 | **experiments** | [workflows/experiments/README.md](workflows/experiments/README.md) |
| 「查清楚這是怎麼運作的」「這樣做可不可行」「這個 bug 是為什麼」（只讀不改）| **investigation** | [workflows/investigation.md](workflows/investigation.md) |
| 「**幫我用 aos**」「把 aos 接進我的專案」「這個指令怎麼下」 | **use-aos** | [workflows/use-aos.md](workflows/use-aos.md) |
| 「跑測試 / 驗證」「這樣改有沒有壞」 | **testing** | [workflows/testing.md](workflows/testing.md) |
| 「重構 / 拆檔 / 整理程式結構」（行為不變）| **refactor** | [workflows/refactor/README.md](workflows/refactor/README.md) |
| 「搬檔案 / 改目錄名 / 拆 repo」 | **refactor**（搬移專章）| [workflows/refactor/moving-things.md](workflows/refactor/moving-things.md) |
| 「環境怎麼裝」「fresh clone 後要做什麼」「指令是什麼」 | **dev-env** | [workflows/dev-env.md](workflows/dev-env.md) |
| 「這段程式在哪 / 哪個檔負責什麼」 | **code map** | [workflows/common/code-map.md](workflows/common/code-map.md) |
| 「**把這些東西濃縮給我看**」「我只有半小時」「寫個我看得懂的版本」 | **digest** | [workflows/digest/README.md](workflows/digest/README.md) |

> **digest 跟其他工作流的分界**：其他工作流**產生**東西，digest **只讀不產**——
> 把已經寫完的紀錄濃縮成使用者本人讀得動的精簡版。它不做判斷、不下結論，
> 只負責讓人在有限時間內掌握狀況。

> **研討會／黑客松／實驗／調查怎麼分**：同一件事的四種強度——**workshop** 唯讀、只發想；
> **hackathon** 多個 agent 各自**動手做同一題**，只收坑／好處／壞處；
> **experiments** 我自己拿**一個明確假設**去驗，要的是是／否；
> **investigation** 只讀不改，回答一個窄問題（怎麼運作、可不可行、為什麼壞）。

### kernel 內建

| 觸發（你說…）| 工作流 | 入口檔 |
|--------------|--------|--------|
| 「**記 / 查踩坑**」 | **gotchas** | [workflows/common/gotchas.md](workflows/common/gotchas.md) |
| 「整理 X」「封存過時的」「檔案太多／太雜」「太大要拆」（文件層）| **tidy** | [workflows/tidy/README.md](workflows/tidy/README.md) |
| 「記個想法」「以後要做」「排進 roadmap」「幫我規劃」 | **planning** → 本專案落點是 ideas／roadmap | [workflows/planning.md](workflows/planning.md) |
| 「記個決定」「為什麼選 A 不選 B」 | **decisions** → 本專案落點是 ideas 各章的「待決定」表 | [workflows/decisions.md](workflows/decisions.md) |
| 「我的偏好是…」「以後直接做 / 先問」 | **user** | [workflows/common/user.md](workflows/common/user.md) |

### 定期喚醒 flavor

**兩種進入**：① **循環執行**——[`/wf-tick [週期]`](../.claude/commands/wf-tick.md) 每隔週期喚醒 tick，tick 派發 routines → schedule，判時間、**做**到期項；② **使用者登記**——「幫我登記行程」進 schedule、「加個常規事務」進 routines，只寫進清單、不當場做。

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）|
|--------------|--------|-------------------|
| 「跑一次心跳」（多半由 `/wf-tick` 定期喚醒，不用人說）| **tick** | [workflows/tick.md](workflows/tick.md) |
| 「幫我加個常規事務」「登記例行」「每 N 天要做一次…」 | **routines** | [workflows/routines.md](workflows/routines.md) |
| 「幫我登記行程：17:00 重啟 X」「今晚 8 點提醒我 OO」 | **schedule** | [workflows/schedule.md](workflows/schedule.md) |

**tick 只派發、不判斷**；「什麼時間該做什麼」的判斷與清單各歸 routines / schedule。

### multi-agent flavor

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）|
|--------------|--------|-------------------|
| 「看看信箱」「處理 inbox」 | **inbox（收信）** | [workflows/inbox/README.md](workflows/inbox/README.md) |
| 「寄信給 X」「請別資料夾的 agent 做 Y」「回報做完了 / 卡住了」 | **inbox（寄信）** | [workflows/inbox/README.md](workflows/inbox/README.md)（格式與 STATUS 見 [PROTOCOL](workflows/inbox/PROTOCOL.md)）|
| 「把這件事切成幾條線派出去」「開一隊去做」「寫交接書」「收線」 | **dispatch** | [workflows/dispatch/README.md](workflows/dispatch/README.md) |
| 「要開團隊」「這層派哪級模型」「怎麼分角色」 | **team-model** | [workflows/team-model.md](workflows/team-model.md) |
| 「我要用螢幕 / 鍵鼠」「誰在佔著主工作樹」「誰在佔資源」 | **resources** | [workflows/resources.md](workflows/resources.md) |

> workshop／hackathon 本身就是派線：它們各自的入口檔管**題目與紀錄**，怎麼開隊、派哪級模型、怎麼收線一律照 dispatch／team-model。

**都不符 → 看 [INDEX.md](INDEX.md)**（repo 頂層結構地圖）。新開工作流 → 複製 [workflows/TEMPLATE.workflow.md](workflows/TEMPLATE.workflow.md) 從單檔長起，並在上表加一列；不要預先建空檔。

## 工作流的統一形式（規範）

- **檔名規範**：**README** = 初入一個資料夾**先讀的入口／導引**；**INDEX** = **描述該資料夾頂層結構**的索引。小資料夾兩者可合一；大到結構複雜時才分出獨立 INDEX。
- **入口檔段落**固定照 [TEMPLATE.workflow.md](workflows/TEMPLATE.workflow.md)：何時用 ↔ 何時不用 / `Done when:`（只准三類可觀察條件：檔案存在、指令回傳、表格填滿）/ 流程 / 交接。既有工作流的入口檔在下次動到時再補齊這些段，不為了補而改。
- **資料夾型**：入口 `README.md` ＋視需要的 `archive/`（過時文檔封存，規則見 [STRUCTURE](STRUCTURE.md)）、`gotchas.md`、`session-log.md`；**單檔型**：一個 `.md` 同時是入口與內容。撐大了就照 [STRUCTURE](STRUCTURE.md) 的四級成長軌跡升級成資料夾型；到底有哪些工作流看上面的派發表即可。

## 跨工作流的活狀態（只列 open，完成即刪）

| 在等誰 | 記哪裡 |
|--------|--------|
| 等**使用者**做 / 驗證 / 決定 | [WAIT_USER.md](WAIT_USER.md) |
| 等**同 repo 另一個 session / fork**、或我自己還沒做完的 | [SESSION-LOG.md](SESSION-LOG.md) 一行 open |
| 等**別資料夾的 agent** | 信件軸：放信處 [`wf/inbox/`](inbox/)，使用方式 [workflows/inbox/](workflows/inbox/README.md) |
