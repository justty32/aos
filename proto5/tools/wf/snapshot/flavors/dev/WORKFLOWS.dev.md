### 開發 flavor

碰原始碼的工作流共用 [common/conventions](workflows/common/conventions.md)（寫碼慣例）與 [common/code-map](workflows/common/code-map.md)（哪個檔負責什麼）。

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）|
|--------------|--------|-------------------|
| 「開發 / 修改某個功能」「**修 bug**」 | **feature-dev** | [workflows/feature-dev/README.md](workflows/feature-dev/README.md) |
| 「跑測試 / 驗證」「這樣改有沒有壞」 | **testing** | [workflows/testing.md](workflows/testing.md) |
| 「重構 / 拆檔 / 整理結構」（行為不變）| **refactor** | [workflows/refactor/README.md](workflows/refactor/README.md) |
| 「搬檔案 / 改目錄名 / 拆 repo」 | **refactor**（搬移專章）| [workflows/refactor/moving-things.md](workflows/refactor/moving-things.md) |
| 「這個陌生專案是怎麼運作的」「幫我分析這個 repo」 | **analysis** | [workflows/analysis.md](workflows/analysis.md) |
| 「查清楚這是怎麼運作的」「這樣做可不可行」 | **investigation** | [workflows/investigation.md](workflows/investigation.md) |
| 「做一包 patch 給別的專案 / 別的 agent 套」 | **patch** | [workflows/patch.md](workflows/patch.md) |
| 「環境怎麼裝」「fresh clone 後要做什麼」「指令是什麼」 | **dev-env** | [workflows/dev-env.md](workflows/dev-env.md) |
| 「討論方案」「寫動工計畫」（spec / plan）| **planning**（kernel 管線的後兩段）| [workflows/planning.md](workflows/planning.md) |

**analysis** ＝初次接觸陌生專案、要建立可延續的分析產物；**investigation** ＝回答一個窄問題。**patch** ＝跨 repo、原專案無 git 或不能直接 push、要交給冷啟動 agent 套用時才用；同一個 repo 內能改能測就走 feature-dev。
