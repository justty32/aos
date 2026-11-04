# conventions — 程式碼慣例（碰原始碼的工作流共用）

[common/README](README.md)｜[INDEX](../../INDEX.md)

碰原始碼的工作流（feature-dev / refactor / investigation）共用這套規矩：**寫碼時要遵守什麼**。哪個檔負責什麼領域、測試在哪 → [code-map](code-map.md)；真相層優先序也在 [code-map](code-map.md)。結構整理原則 → [STRUCTURE](../../STRUCTURE.md)。

> 〔模板說明〕一條一行，寫得出「怎麼檢查」的才留；寫不出檢查方式的（「程式碼要乾淨」）不是慣例，別放。填完刪除本段。

## 慣例

| 項目 | 規矩 |
|------|------|
| 檔案拆分 | {{例：按領域拆 module；單檔超過 300 行就照 STRUCTURE 檢視}} |
| 命名 | {{例：檔名 kebab-case、型別 PascalCase}} |
| 註解語言 | {{例：程式碼註解英文、文件繁中}} |
| breaking change | {{例：改公開介面前先全域 grep 受影響處，同一 commit 一起改}} |
| 型別 / schema 同步 | {{例：改 schema 要同步產生檔與測試 fixture}} |
| 相依 | {{例：新增套件前先確認，版本鎖進 lockfile}} |
| {{其他}} | {{…}} |
