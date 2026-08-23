# 程式碼慣例 + 導航 index 維護鏈（碼相關工作流共用）

← [common/README](README.md)｜[INDEX](../../INDEX.md)

碰原始碼的工作流（feature-dev / refactor / specs / plans…）共用這套規矩。純文檔/調查類工作流用不到。結構整理原則（被動、按需取用）在 [DEV-GUIDE](../../DEV-GUIDE.md)；always-on 鐵律在 [AGENTS.md](../../../AGENTS.md)。

## 程式碼慣例

- **C++23**（`CMAKE_CXX_EXTENSIONS OFF`）。C ABI 檔案另外守 C99。
- **單向分層是鐵律**：每個小專案內部照 `inst/` 那樣切分層（例如 `inst ← format ← exec`），下層不可以知道上層存在；跨小專案只能透過對外標頭（`include/aos/<專案>.hpp`）與 `aos::<專案>` target 相依，不可以互相 include 對方的 `src/`。
- **對外標頭 vs. 內部標頭**：`include/aos/` 底下是公開 API，會被安裝，裡面宣告的每個函式都要標 `AOS_API`（`<aos/export.h>`）——漏標的話 `-fvisibility=hidden` 之下外部連得到標頭卻連不到實作。`src/` 底下的 `.hpp`（`spawn_prep.hpp`、`wait.hpp`、`capi_common.hpp`、`run.hpp`）是**內部標頭**，只給同一個小專案自己的 `.cpp` 用，不安裝也不標 `AOS_API`。
- **C ABI 的 ABI 規則**：`include/aos/<專案>.h` 裡的列舉值一經釋出就凍結，只能在尾端加新值，不能重排或刪除既有值；C++ 列舉與 C 列舉的對齊靠 `capi.cpp` 開頭的一串 `static_assert`，新增/改列舉值兩邊都要動。
- **單檔行數門檻**：與 [DEV-GUIDE 觸發 A](../../DEV-GUIDE.md) 一致，程式碼單檔超過 300 行就該考慮拆。
- **`fork` 前後的界線**（`exec` 層專屬，但任何碰行程操作的程式碼都要守）：`fork` 之後、`execve` 之前只能呼叫 async-signal-safe 的 POSIX 操作，不能有 C++ 記憶體配置、`setenv`、字串操作。所有準備工作（環境變數合併、PATH 解析、`argv`／`envp` 實體化）都要在 `fork` 之前做完；細節見 `inst/docs/architecture.md`。
- **新增/改欄位或列舉值**要全域 grep 受影響處（C++ 型別、format 的 encode/decode、C ABI 的鏡像宣告與 static_assert）並同一個 commit 更新，不要分批留下不一致的中間狀態。

## 導航 index（code map）維護鏈

> 〔模板說明〕「code map」＝描述程式碼結構的導航 index（哪個檔負責什麼領域、測試在哪）。小專案一個檔就夠；大了按領域拆成多份子 index（此時可獨立成 `common/code-map/` 資料夾）。沒有 code map 的專案可先刪本節，等程式碼大到 agent 找檔困難時再建。

三個面向構成維護鏈：**程式碼 → code map → 文檔**。

**優先級（衝突或時間不夠時，依序保持一致）：** 程式碼 > code map > 文檔。
**code map 與程式碼衝突時：以程式碼為準，立即修正 code map。**

**日常規則：**
1. **修改前**：先讀 code map，找到相關領域，只讀清單中列出的檔案——不要讀無關領域的檔案。
2. **修改後**：若新增或刪除了原始碼檔案，或某檔案的職責有顯著改變，必須同步更新 code map。
3. 原始碼檔案本身**不加**「對應 code map」的註釋（維護成本過高）；反向查找直接 grep code map 文件。
