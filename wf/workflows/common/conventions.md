# 程式碼慣例 + 導航 index 維護鏈（碼相關工作流共用）

← [common/README](README.md)｜[INDEX](../../INDEX.md)

碰原始碼的工作流（feature-dev / refactor / specs / plans…）共用這套規矩。純文檔/調查類工作流用不到。結構整理原則（被動、按需取用）在 [DEV-GUIDE](../../DEV-GUIDE.md)；always-on 鐵律在 [AGENTS.md](../../AGENTS.md)。

> 〔模板說明〕本檔是給「有程式碼的專案」用的骨架；純文檔專案整檔刪除（並從 common/README 移除該列）。

## 程式碼慣例

> 〔模板說明〕填你專案自己的慣例，例如：檔案拆分方式（partial / module 按領域拆）、單檔行數門檻（建議與 DEV-GUIDE 觸發 A 一致，如 300 行）、breaking change 前必須先全域 grep 受影響處並同 commit 更新、schema/型別檔的同步規則…。

- {{慣例 1}}
- {{慣例 2}}

## 導航 index（code map）維護鏈

> 〔模板說明〕「code map」＝描述程式碼結構的導航 index（哪個檔負責什麼領域、測試在哪）。小專案一個檔就夠；大了按領域拆成多份子 index（此時可獨立成 `common/code-map/` 資料夾）。沒有 code map 的專案可先刪本節，等程式碼大到 agent 找檔困難時再建。

三個面向構成維護鏈：**程式碼 → code map → 文檔**。

**優先級（衝突或時間不夠時，依序保持一致）：** 程式碼 > code map > 文檔。
**code map 與程式碼衝突時：以程式碼為準，立即修正 code map。**

**日常規則：**
1. **修改前**：先讀 code map，找到相關領域，只讀清單中列出的檔案——不要讀無關領域的檔案。
2. **修改後**：若新增或刪除了原始碼檔案，或某檔案的職責有顯著改變，必須同步更新 code map。
3. 原始碼檔案本身**不加**「對應 code map」的註釋（維護成本過高）；反向查找直接 grep code map 文件。
