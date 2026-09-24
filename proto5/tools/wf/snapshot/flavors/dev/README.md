# dev — 開發 flavor 包

← [repo README](../../README.md)（導航中樞）

程式開發專案用的工作流包，搭配 [`template/`](../../template/) 這個**共用 kernel**：kernel 給分層樹骨架（AGENTS / WORKFLOWS / INDEX / STRUCTURE / 活狀態 / planning / decisions / common），本包只加**碰原始碼的那幾條工作流**，外加兩份共用參考：慣例與 code map。

## 這個包有什麼

| 路徑 | 角色 |
|------|------|
| [WORKFLOWS.dev.md](WORKFLOWS.dev.md) | 派發表片段（貼進 kernel 的 `WORKFLOWS.md`）|
| [AGENTS.dev.md](AGENTS.dev.md) | `AGENTS.md`「開場與入口」的一行 bullet |
| [COMMON.dev.md](COMMON.dev.md) | `workflows/common/README.md` 表的兩列 |
| [workflows/feature-dev/](workflows/feature-dev/README.md) | 功能開發 / 修 bug（**資料夾型**範例）|
| [workflows/testing.md](workflows/testing.md) | 驗證表：驗證 / 指令 / 誰跑 |
| [workflows/refactor/README.md](workflows/refactor/README.md) | 行為不變的結構整理（含 [moving-things.md](workflows/refactor/moving-things.md)）|
| [workflows/investigation.md](workflows/investigation.md) | 調查 / 解讀外部系統 / 可行性 |
| [workflows/analysis.md](workflows/analysis.md) | 陌生專案分析：產物結構與 Level 流程 |
| [workflows/patch.md](workflows/patch.md) | 獨立 patch 包：交給冷啟動 agent 套用 |
| [workflows/dev-env.md](workflows/dev-env.md) | 環境、fresh clone、指令表、外部工具與 env var |
| [workflows/common/conventions.md](workflows/common/conventions.md) | 寫碼慣例 |
| [workflows/common/code-map.md](workflows/common/code-map.md) | 程式碼導航 index ＋ 維護鏈 |

## 怎麼合進 kernel

```
tools/wf-init.sh --target <專案> --flavor dev
```

通用步驟（複製 kernel → 併 `workflows/` → 貼片段 → 填 `{{}}`／處理〔導入判斷〕〔模板說明〕→ 跑 lint）見 [IMPORT.md](../../IMPORT.md)。本包特有的兩點：`workflows/common/*` 併入既有的 `workflows/common/`；片段檔三個（`WORKFLOWS.dev.md`／`AGENTS.dev.md`／`COMMON.dev.md`，沒有 `INDEX.dev.md`）。

## 可選工作流菜單

常見的開發工作流；本包已附的直接使用，其餘需要哪個才建，照 kernel 的 [`TEMPLATE.workflow.md`](../../template/workflows/TEMPLATE.workflow.md) 從單檔長起，並在派發表加一列。

| 你可能想要的 | 現在在哪 |
|--------------|---------|
| **idea**（要不要做）／**roadmap**（會做，何時）／**spec**（討論後方案）／**plan**（動工前詳規）| 已合成 kernel 的一條 planning 管線：[`workflows/planning.md`](../../template/workflows/planning.md)。四個是同一個想法的四個階段，分四檔會讓 agent 卡在「這算 idea 還是 roadmap」 |
| **tooling**（工具設定 / env var / 依賴）| 併入 [dev-env](workflows/dev-env.md)——那些本來就是環境的一部分 |
| **analysis**（陌生專案分析）／**patch**（獨立套用包）| 本包已附：[analysis](workflows/analysis.md)／[patch](workflows/patch.md) |
| **release / deploy / incident** | 不在本包（維運類），需要就自建 |
| **review / benchmark / migration** | 不在本包，需要就自建 |

**混合型專案**（同時合 [knowledge 包](../knowledge/README.md)）：dev 的 spec / plan 與 knowledge 的 plan-a-thing 觸發詞都是「規劃」，以**產出是否為程式碼**分流——是程式碼走 planning → feature-dev，不是就走 plan-a-thing。兩張派發表都貼，kernel 內建那幾列（gotchas / planning / decisions / user）只留一份。

## 移除某工作流要動的地方

| 工作流 | 刪的檔 | 同步改的檔 |
|--------|--------|-----------|
| feature-dev | `workflows/feature-dev/` | `WORKFLOWS.md` 該列；`testing.md`、`refactor/README.md`、`investigation.md` 的交接段；`common/code-map.md` 維護鏈第 4 點 |
| testing | `workflows/testing.md` | `WORKFLOWS.md` 該列；`feature-dev/README.md` 的 Done when 與流程；`refactor/README.md` 的 Done when；`dev-env.md` 指令表下那句 |
| refactor | `workflows/refactor/` | `WORKFLOWS.md` 該列；`feature-dev/README.md` 交接段；`common/conventions.md` 開頭那句 |
| investigation | `workflows/investigation.md` | `WORKFLOWS.md` 該列；`feature-dev/README.md` 的「何時不用」；`refactor/README.md` 的「何時不用」 |
| analysis | `workflows/analysis.md` | `WORKFLOWS.md` 該列；`patch.md` 的前置條件 |
| patch | `workflows/patch.md` | `WORKFLOWS.md` 該列；`analysis.md` 流程第 5 步 |
| dev-env | `workflows/dev-env.md` | `WORKFLOWS.md` 該列；`AGENTS.md` 那行 bullet；`testing.md` 的「何時不用」 |
| conventions / code-map | `workflows/common/conventions.md`、`code-map.md` | `workflows/common/README.md` 對應列；`AGENTS.md` 那行 bullet；`WORKFLOWS.md` 表前那句；各工作流的 Done when 與流程裡的 code map 步驟 |

動完跑 `tools/wf-lint.sh <專案>`：`BROKEN` 清單就是漏掉的地方。
