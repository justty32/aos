# `knowledge/wf/skeletons/conventions.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/skeletons/conventions.md`，跟到正本 commit `578a7c762`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

寫碼慣例的記憶骨架：碰原始碼的工作流（feature-dev、refactor、investigation）共用的規矩——寫碼時要遵守什麼、怎麼檢查。落在工作區的 `wf/knowledge/conventions.json`。

# holds

- 放：這個專案的寫碼慣例，一條一列、附怎麼檢查。
- 不放：哪個檔負責什麼、測試在哪、真相層優先序（工作區的 `wf/knowledge/code-map.json`）；工作文檔的組織原則（本庫 `wf/` 頂層的 `layers.json`、`nodes.json`、`tidying.json`）；使用者個人偏好（工作區的 `wf/knowledge/user.json`）。

# fields

- conventions: 物件陣列：`item`（項目）、`rule`（規矩）、`check`（怎麼檢查：指令、grep、或「目視」）。

# suggested_items

## 0

- item: 檔案拆分
- example: 按領域拆 module；檔太大照 `wf/tidying.md#/什麼時候該整理（膨脹即拆／雜亂即分類）` 檢視

## 1

- item: 命名
- example: 檔名 kebab-case、型別 PascalCase

## 2

- item: 註解語言
- example: 程式碼註解英文、文件繁中

## 3

- item: breaking change
- example: 改公開介面前先全域 grep 受影響處，同一 commit 一起改

## 4

- item: 型別／schema 同步
- example: 改 schema 要同步產生檔與測試 fixture

## 5

- item: 相依
- example: 新增套件前先確認，版本鎖進 lockfile

# rules

- 一條一列，**寫得出「怎麼檢查」的才留**；寫不出檢查方式的（「程式碼要乾淨」）不是慣例，別放。
- `suggested_items` 只是常見項目與例子，照專案實況寫，用不到的不列。
- 記錄是物件陣列，用 json 工具讀寫（`aos/packs.md#/json`）。

# skeleton

```json
{
 "conventions": []
}
```
