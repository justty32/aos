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
| 「**我有個 idea**」「把這個構想記下來」「要重新拷問 X」 | **ideas** | 現行落點：[proto8/docs/CONCEPTS.md](../proto8/docs/CONCEPTS.md)（概念層）、[proto8/thinking/](../proto8/thinking/README.md)（討論紀錄）；舊的 ideas 13 章已封存 |
| 「**寫 spec**」「照構想集定規格」「新實作要照什麼寫」 | **spec** | 現行落點：[proto8/docs/NORMS.md](../proto8/docs/NORMS.md)（規範）、[proto8/docs/CONVENTION.md](../proto8/docs/CONVENTION.md)（aos agent 慣例）；上一代 proto7-2 照 [proto7-2/spec.md](../proto7-2/spec.md)（核心 spec 是 [proto7/spec/core.md](../proto7/spec/core.md)），proto6 照 [proto6/spec](../proto6/spec/README.md)；舊的 09-05 規格已封存 |
| 「**接下來做什麼**」「照進度表推進」「動工前該讀什麼」 | **roadmap** | 現行落點：[SESSION-LOG.md](SESSION-LOG.md)（open 進度與下一步）；舊的 roadmap 已封存 |
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
| 「整理 X」「封存過時的」「檔案太多／太雜」「太大要拆」「只留結論」（文件層）| **tidy** | [workflows/tidy/README.md](workflows/tidy/README.md) |
| 「記個想法」「以後要做」「排進 roadmap」「幫我規劃」 | **planning** → 本專案落點是 [proto8/docs/CONCEPTS](../proto8/docs/CONCEPTS.md)／[proto8/thinking](../proto8/thinking/README.md)／[SESSION-LOG](SESSION-LOG.md)（舊的 ideas／roadmap 已封存） | [workflows/planning.md](workflows/planning.md) |
| 「記個決定」「為什麼選 A 不選 B」 | **decisions** → 本專案落點是 [proto8/thinking](../proto8/thinking/README.md) 的決定與結論（舊的 ideas「待決定」表已封存） | [workflows/decisions.md](workflows/decisions.md) |
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

multi-agent flavor 的派發表在 [WORKFLOWS-parts/01-multi-agent-flavor.md](WORKFLOWS-parts/01-multi-agent-flavor.md)（2026-10-13 tidy：本檔超過 8 KB，整段逐字下放）。

**都不符 → 看 [INDEX.md](INDEX.md)**（repo 頂層結構地圖）。新開工作流 → 複製 [workflows/TEMPLATE.workflow.md](workflows/TEMPLATE.workflow.md) 從單檔長起，並在上表加一列；不要預先建空檔。

## 工作流的統一形式（規範）

檔名規範、入口檔段落、資料夾型／單檔型的規範在 [WORKFLOWS-parts/02-統一形式.md](WORKFLOWS-parts/02-統一形式.md)（2026-10-13 tidy：本檔超過 8 KB，整段逐字下放）。

## 跨工作流的活狀態（只列 open，完成即刪）

| 在等誰 | 記哪裡 |
|--------|--------|
| 等**使用者**做 / 驗證 / 決定 | [WAIT_USER.md](WAIT_USER.md) |
| 等**同 repo 另一個 session / fork**、或我自己還沒做完的 | [SESSION-LOG.md](SESSION-LOG.md) 一行 open |
| 等**別資料夾的 agent** | 信件軸：放信處 [`wf/inbox/`](inbox/)，使用方式 [workflows/inbox/](workflows/inbox/README.md) |
