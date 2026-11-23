# WORKFLOWS — 工作流派發器

← [AGENTS.md](../AGENTS.md)｜結構 [STRUCTURE](STRUCTURE.md)

你（使用者）說要做某件事 → **從這張表選對應工作流 → 讀它的「入口檔」→ 就知道要做什麼**。每個工作流的細節都在它自己的入口檔，不在這裡。

**可以跳流程**：單行或小範圍、低風險、不跨 session 的修正；純查詢或一次性回答，不留 durable 知識；使用者明確要求快速處理；既有工作流只會增加同步成本而不降低風險。跳流程不等於跳過工程規矩——仍要讀必要上下文、不破壞使用者改動、改完 build 得過。

## 你想做什麼 → 用哪個工作流

### 開發 flavor

碰原始碼的工作流共用 [common/conventions](workflows/common/conventions.md)（程式碼慣例 + code map 維護鏈）與 [code map](knowledge/code-map.json)（哪個檔負責什麼）。

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）|
|--------------|--------|-------------------|
| 「我想開發 / 修改某個功能」「**修 bug**」 | **feature-dev** | [workflows/feature-dev/README.md](workflows/feature-dev/README.md) |
| 「跑測試 / 驗證」「這樣改有沒有壞」 | **testing** | [workflows/testing.md](workflows/testing.md) |
| 「重構 / 拆檔 / 整理程式結構」（行為不變）| **refactor** | [workflows/refactor/README.md](workflows/refactor/README.md) |
| 「搬檔案 / 改目錄名 / 拆 repo」 | **refactor**（搬移專章）| [workflows/refactor/moving-things.md](workflows/refactor/moving-things.md) |
| 「環境怎麼裝」「fresh clone 後要做什麼」「指令是什麼」 | **dev-env** | [workflows/dev-env.md](workflows/dev-env.md) |
| 「這段程式在哪 / 哪個檔負責什麼」 | **code map** | [wf/knowledge/code-map.json](knowledge/code-map.json) |

**已封存、沒有入口的**（舊入口 11-17 集中收進 `wf/workflows/archive/`，不留指標頁，使用者 11-17 待裁網頁 wf-4 a）：
- ideas、spec（使用者 11-14 專區答「oldentry:archive」，reply cee70afc742361ba）→ 構想寫 [proto8/docs/CONCEPTS.md](../proto8/docs/CONCEPTS.md)，規格寫 [NORMS](../proto8/docs/NORMS.md)／[CONVENTION](../proto8/docs/CONVENTION.md)，討論紀錄寫 [proto8/thinking/](../proto8/thinking/README.md)。
- roadmap →「接下來做什麼」看 [progress.json](progress.json)（open 進度與下一步）。
- workshop、hackathon（11-14 封存）→ 要再辦得照現在的隊形（[dispatch](workflows/dispatch/README.md)）重寫。
- experiments、investigation、digest（11-17 封存）→ 要驗假設就直接跑、只讀就直接查，紀錄與筆記寫進 proto8/thinking。
- decide-page（11-14 停用）→ 要使用者裁的題寄使用者專區，見 [dispatch/aos-teams](workflows/dispatch/aos-teams.md) 第 2 件。

### kernel 內建

| 觸發（你說…）| 工作流 | 入口檔 |
|--------------|--------|--------|
| 「**記 / 查踩坑**」「這件事有沒有現成做法」「投稿一個做法」 | **public**（公用知識庫；坑只留這一處，使用者 11-17 待裁網頁 wf-7 a） | [public/README.md](public/README.md#主題) |
| 「整理 X」「封存過時的」「檔案太多／太雜」「太大要拆」「只留結論」（文件層）| **tidy** | [workflows/tidy/README.md](workflows/tidy/README.md) |
| 「記個想法」「以後要做」「排進 roadmap」「幫我規劃」 | **planning** → 本專案落點是 [proto8/docs/CONCEPTS](../proto8/docs/CONCEPTS.md)／[proto8/thinking](../proto8/thinking/README.md)／[progress.json](progress.json) | [workflows/planning.md](workflows/planning.md) |
| 「記個決定」「為什麼選 A 不選 B」 | **decisions** → 本專案落點是 [proto8/thinking](../proto8/thinking/README.md) 的決定與結論 | [workflows/decisions.json](workflows/decisions.json)（json 節點：通用版＋本地差異，可用 `index_view`／`json_get` 讀） |
| 「我的偏好是…」「以後直接做 / 先問」 | **user** | [workflows/common/user.md](workflows/common/user.md) |
| 「對 aos 本身有改進意見」「這個 aos 設計不好用」 | **advices**（對 aos 的意見，精簡成三個小檔） | [advices/README.md](advices/README.md) |
| 「派 fsm 隊員要配什麼 system、工具、權限」 | **kits**（配給包） | [workflows/dispatch/kits/README.md](workflows/dispatch/kits/README.md)（隊長流程 [card](workflows/dispatch/kits/card.md)） |
| 「交件」「commit」 | **commit-request**（交件排隊，鐵律 3） | [aos-teams/07](workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)（`wf/tools/commit-request` 的 claim／submit） |
| 「要問使用者」「這題要他拍板」 | **使用者專區**（`aos-user send --kind decide`） | [common/user.md](workflows/common/user.md)「回覆風格」 |

### multi-agent flavor

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）|
|--------------|--------|-------------------|
| 「看看信箱」「處理 inbox」 | **inbox（收信）** | [workflows/inbox.json](workflows/inbox.json) |
| 「寄信給 X」「請別資料夾的 agent 做 Y」「回報做完了 / 卡住了」 | **inbox（寄信）** | [workflows/inbox.json](workflows/inbox.json)（信的格式與 STATUS 在它的 `local/letter_format`）|
| 「把這件事切成幾條線派出去」「開一隊去做」「寫交接書」「收線」 | **dispatch** | [workflows/dispatch/README.md](workflows/dispatch/README.md) |
| 「派 agent 時要它讀什麼規矩」 | **規矩卡**（使用者 11-17 待裁網頁 wf-6 a） | [workflows/common/rules-card.md](workflows/common/rules-card.md) |
| 「這件事歸誰」「做完交給誰」「要開／收一個位子」「掛打雜工」 | **org**（eca-aos 這邊的工作室分工；11-23 第一版，標〔提案〕的等使用者定） | [org/README.md](org/README.md) |
| 「要開團隊」「這層派哪級模型」「怎麼分角色」 | **team-model** | [workflows/team-model.md](workflows/team-model.md) |
| 「我要用螢幕 / 鍵鼠」「誰在佔著主工作樹」「誰在佔資源」 | **resources** | [workflows/resources.md](workflows/resources.md) |

**都不符** → repo 頂層各放什麼看 [AGENTS.md](../AGENTS.md) 第一段與 [proto8/README](../proto8/README.md)，`wf/` 頂層一覽用 `index_view wf`（`wf/_index.json`）。新開工作流 → 複製 [workflows/TEMPLATE.workflow.md](workflows/TEMPLATE.workflow.md) 從單檔長起，並在上表加一列；不要預先建空檔。

## 工作流的統一形式（規範）

檔名規範、入口檔段落、資料夾型／單檔型的規範，唯一出處在 [STRUCTURE「工作流的統一形式」](STRUCTURE.md#工作流的統一形式)（檔名規範見同檔「分層原則」第 2 條）。

## 跨工作流的活狀態（只列 open，完成即刪）

兩軸：信、進度（使用者 11-18 選項框「併進進度檔後退場 (Recommended)」，待使用者併進進度；每軸一處是 11-17 待裁網頁 wf-2 a）：

| 在等誰 | 記哪裡 |
|--------|--------|
| 等**使用者**做 / 驗證 / 決定 | [progress.json](progress.json) 一條、status 寫「等使用者」；有使用者專區的機器，新題照舊寄專區（`aos-user send`，見 [common/user.md](workflows/common/user.md)） |
| 等**同 repo 另一個 session / fork**、或我自己還沒做完的 | [progress.json](progress.json) 一條 open（11-18 從 `SESSION-LOG.md` 轉成 json，使用者 11-17 待裁網頁 wf-3、wf-3b a） |
| 等**別資料夾的 agent** | 信件軸：樹內走 aos 信箱，樹外專案的放信處 [`wf/inbox/`](inbox/)，使用方式 [workflows/inbox.json](workflows/inbox.json) |

導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)；停在半路的見 [restart](../proto8/thinking/2026-10/11/restart/README.md) §4（原在進度檔末，11-18 搬來）。
