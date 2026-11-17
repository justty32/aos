# investigation — 調查 / 解讀外部系統 / 可行性

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

只讀不改，查清楚「這怎麼運作／可不可行／為什麼壞」，產出可歸檔的筆記。

**何時用**：看懂外部系統或別人的碼、評估可行性、查 bug 成因、對照前作。
**何時不用**：已知道怎麼改 → [feature-dev](feature-dev/README.md)；只搬結構 → [refactor](refactor/README.md)；有一個明確假設要**動手跑**才知道是／否 → 直接跑、紀錄寫進 proto8/thinking（舊的 experiments 工作流 11-17 已封存）；要多方發想 → 先發想不急著規劃（[user/03](common/user/03-討論紀錄與規劃.md)；舊的 workshop 工作流 11-14 已封存）。

## Done when

- 筆記存在，且下列五段非空：proto8 年代寫在 [proto8/thinking/](../../proto8/thinking/README.md) 的 `<日期>/` 底下（一天一夾，例 [wake-1114](../../proto8/thinking/2026-11/14/wake-1114.md)），或寫成本資料夾的 `investigations/<主題>.md`，兩種都算（proto5 的兩份舊調查 11-17 已封存，見 [investigations/archive](investigations/archive/README.md)）。
- 結論是「要動手」→ [SESSION-LOG](../SESSION-LOG.md) 有接手列。

## 流程

1. **收集事實**：只讀不改，一條一則，附出處。
2. **對照現有能力**：這件事現在能不能做、靠什麼做（先查 [code map](../knowledge/code-map.json) 與 proto8 thinking 的決定，別重查已裁決的）。
3. **分類**：可直接做／有缺口／不值得做／需使用者驗證。
4. **產出 finding**：照下方筆記模板寫成一份可歸檔的筆記；缺口進 [planning](planning.md)（proto8/thinking／SESSION-LOG），踩到的坑進 [common/gotchas](common/gotchas.md)，需使用者驗證的寄使用者專區（`aos-user send`，見 [common/user.md](common/user.md)；舊條目在 [WAIT_USER](../WAIT_USER.md)）。

**不把未驗證的猜測寫成結論**——不確定就寫「缺什麼證據」，不要補完。

## 筆記模板

- **問題**：要回答什麼，一句話。
- **方法**：讀了哪些檔、跑了什麼指令。
- **發現**：一條一則事實，附出處。
- **結論**：直接回答問題；不確定就寫缺什麼。
- **來源**：檔案路徑＋行號、指令輸出、連結。

## 交接

- 要動手 → [feature-dev](feature-dev/README.md)；同一坑第二次 → [common/gotchas](common/gotchas.md)。
