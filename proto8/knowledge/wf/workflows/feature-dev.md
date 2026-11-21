功能開發／修 bug：改變行為的工作，加一個功能、修一個 bug，從動手到 commit。碰原始碼前先讀工作區的 `wf/knowledge/conventions.json`（寫碼慣例）與 `wf/knowledge/code-map.json`（哪個檔負責什麼）。

# when

使用者說「我想開發／修改某個功能」「這裡壞了，修一下」「修 bug」——**修 bug 也走這條**，產出一樣是「行為改變＋驗證綠燈」。

# not_when

只是要查清楚原因、還不動碼 → `wf/workflows/investigation.md`；行為不變、只重排結構 → `wf/workflows/refactor.md`；還在討論要不要做、方案長怎樣 → `wf/workflows/planning.md`；要交一包給別的 repo／冷啟動 agent 套用 → `wf/workflows/patch.md`。單行或小範圍、低風險、不跨 session 的修正可以跳流程（條件見 `wf/workflows/_description.md` 的「可以跳流程」）。

# done_when

- 工作區的 `wf/knowledge/verification.json#/checks` 標「改完必跑」的驗證指令回傳 0。
- 工作區的 `wf/knowledge/code-map.json#/domains` 中該領域的列已更新（新增／刪除的檔、職責變動、測試位置）。
- 要使用者實機驗證的在工作區的 `wf/progress.json` 有一條、status 寫「等使用者」；跨 session 沒收尾的在同一檔有一條 open。

# steps

- 碰原始碼前先讀工作區的 `wf/knowledge/conventions.json`（寫碼慣例）與 `wf/knowledge/code-map.json`（哪個檔負責什麼）；環境與指令看 `wf/knowledge/dev-env.json`（`wf/knowledge/dev-dispatch.md#/before_code`）。工作區還沒有 → 照 `wf/skeletons/conventions.md#/skeleton`、`wf/skeletons/code-map.md#/skeleton` 建。
- 工作區還沒有 `wf/knowledge/verification.json` → 照 `wf/skeletons/verification.md#/skeleton` 建；至少寫進一列「改完必跑」（done_when 看的就是它）。

```
讀 code map 找到相關領域（只讀清單裡的檔）
  → 增量修改（守 conventions）
  → 跑 testing 的自動驗證，綠燈
  → 要實機／實環境的交使用者驗證 → 回報問題 → 修 → 重複
  → 全數通過後：更新 code map → 補文檔 → commit
```

- code map 怎麼讀、怎麼維護：`wf/knowledge/code-map-rules.md#/maintenance_chain`；慣例本身在工作區的 `wf/knowledge/conventions.json`。
- 自動驗證是 agent 自己跑的把關；跑不了的一律交使用者（見工作區 `wf/knowledge/verification.json#/checks` 的「誰跑」欄，流程在 `wf/workflows/testing.md`）。
- 迭代期間 code map／文檔可暫時落後，**commit 前必須對齊**。
- commit：流程尾端 commit。怎麼 commit（誰來 commit、直接 commit 還是開 branch 走 PR）看工作區的 `wf/knowledge/user.json`（骨架 `wf/skeletons/user.md`），那裡沒寫就照本流程 commit。push 不在本流程，要有授權來源（`wf/knowledge/iron-rules.md#/rules/authorization`）。
- 跨 session 時在工作區的 `wf/progress.json` 補一條（`flow` 填 `feature-dev`，`what` 寫「[功能名] 文檔／code map 待同步」、`next` 寫「commit 前對齊」；欄位見 `wf/knowledge/live-lists.md#/progress`），下個 session 才不會誤判已同步。

# grows

下面這些都是**長出來才建**，不要預先建空檔（一個工作流怎麼長大見 `wf/nodes.md#/一個工作流的成長軌跡（四級）`）：

- 已落地功能目錄（功能在哪、實作細節指標）→ 工作區的 `wf/knowledge/` 底下新開一個節點。
- 本工作流專屬踩坑 → 工作區的 `wf/knowledge/gotchas.md` 的 feature-dev 那段（共通的在共通段；流程見 `wf/workflows/gotchas.md`）。
- 本工作流 open 進度 → 工作區的 `wf/progress.json`，`flow` 填 `feature-dev`（活清單怎麼寫見 `wf/knowledge/live-lists.md`）。
- 過時節點封存 → `wf/tidying.md#/archive 規則`。

# handoff

- 驗證怎麼跑 → `wf/workflows/testing.md`；改到一半發現該先整理結構 → `wf/workflows/refactor.md`。
- 為什麼選這個做法 → `wf/workflows/decisions.md`；卡在使用者 → 工作區的 `wf/progress.json` 一條、status 寫「等使用者」。
