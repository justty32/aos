調查／解讀外部系統／可行性：只讀不改，查清楚「這怎麼運作／可不可行」，產出一篇可歸檔的筆記。筆記放工作區的 `wf/knowledge/notes/`（單篇形狀與索引寫法見 `wf/skeletons/notes.md`）。

# when

看懂外部系統或別人的碼、評估可行性、查 bug 成因；使用者說「查清楚這是怎麼運作的」「這樣做可不可行」。

# not_when

已知道怎麼改 → `wf/workflows/feature-dev.md`；只搬結構 → `wf/workflows/refactor.md`；初次接觸陌生專案、要建立可延續的整套分析產物（「幫我分析這個 repo」）→ `wf/workflows/analysis.md`。分辨：investigation＝回答一個窄問題、留一篇筆記；analysis＝初次接觸、留整套產物。純查詢或一次性回答、不留 durable 知識的可以跳流程（`wf/workflows/_description.md` 的「可以跳流程」）。

# done_when

- 工作區的 `wf/knowledge/notes/<主題>.json` 存在，且 `wf/skeletons/notes.md#/fields` 的五段都非空。
- 筆記夾有 `_index.json` 時，裡面有這篇的條目（寫法見 `wf/skeletons/notes.md#/index`）。
- 結論是「要動手」→ 工作區的 `wf/knowledge/ideas.json` 的 `ideas` 或 `roadmap` 有接手的一條（流程 `wf/workflows/planning.md`，骨架 `wf/skeletons/ideas.md`）。

# steps

0. 碰原始碼前先讀工作區的 `wf/knowledge/conventions.json`（寫碼慣例）與 `wf/knowledge/code-map.json`（哪個檔負責什麼）；環境與指令看 `wf/knowledge/dev-env.json`（`wf/knowledge/dev-dispatch.md#/before_code`）。工作區還沒有 → 照 `wf/skeletons/conventions.md#/skeleton`、`wf/skeletons/code-map.md#/skeleton` 建。（只讀不改也一樣，慣例與 code map 是讀碼的地圖。）
1. **收集事實**：只讀不改，一條一則，附出處。
2. **對照現有能力**：這件事現在能不能做、靠什麼做。
3. **分類**：可直接做／有缺口／不值得做／需使用者驗證。
4. **產出 finding**：照 `wf/skeletons/notes.md#/skeleton` 寫成工作區的 `wf/knowledge/notes/<主題>.json`（筆記夾還沒有 → 用到才建，入口寫法見 `wf/skeletons/notes.md#/index`）；缺口進 `wf/workflows/planning.md`，踩到的坑進 `wf/workflows/gotchas.md`，需使用者驗證的進工作區的 `wf/progress.json`（status 寫「等使用者」）。

**不把未驗證的猜測寫成結論**——不確定就寫「缺什麼證據」，不要補完。

# handoff

要動手 → `wf/workflows/feature-dev.md`；同一坑第二次 → `wf/workflows/gotchas.md`。
