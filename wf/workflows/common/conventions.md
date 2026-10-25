# 程式碼慣例 + 導航 index 維護鏈（碼相關工作流共用）

← [common/README](README.md)｜[INDEX](../../INDEX.md)

碰原始碼的工作流（feature-dev / refactor / specs / plans…）共用這套規矩。純文檔/調查類工作流用不到。結構整理原則（被動、按需取用）在 [STRUCTURE](../../STRUCTURE.md)；always-on 鐵律在 [AGENTS.md](../../../AGENTS.md)。

## 程式碼慣例

- **C++23**（`CMAKE_CXX_EXTENSIONS OFF`）。C ABI 檔案另外守 C99。
- **單向分層是鐵律**：每個小專案（不分 `core/` 或 `modules/`）內部照 `core/inst/` 那樣切分層（例如 `inst ← format ← exec`），下層不可以知道上層存在；跨小專案只能透過對外標頭（`include/aos/<專案>.hpp`）與 `aos::<專案>` target 相依，不可以互相 include 對方的 `src/`。
- **對外標頭 vs. 內部標頭**：`include/aos/` 底下是公開 API，會被安裝，裡面宣告的每個函式都要標 `AOS_API`（`<aos/export.h>`）——漏標的話 `-fvisibility=hidden` 之下外部連得到標頭卻連不到實作。`src/` 底下的 `.hpp`（`spawn_prep.hpp`、`wait.hpp`、`capi_common.hpp`、`run.hpp`）是**內部標頭**，只給同一個小專案自己的 `.cpp` 用，不安裝也不標 `AOS_API`。
- **C ABI 的 ABI 規則**：`include/aos/<專案>.h` 裡的列舉值一經釋出就凍結，只能在尾端加新值，不能重排或刪除既有值；C++ 列舉與 C 列舉的對齊靠 `capi.cpp` 開頭的一串 `static_assert`，新增/改列舉值兩邊都要動。
- **KISS 是最高原則（也是最後原則：先滿足需求與其他原則，最後回頭清掉多餘的；寫什麼就做什麼——給的值照字面用，不讓特定值偷偷變成另一種行為，10-16）；巢狀只管自己這一層、錯誤只處理自己的**（使用者 10-15，proto8 起的總原則；10-15 深夜加嚴）：每一層只說自己的結果與錯誤，不替下層處理、不偷讀下層的 stderr、不替下層驗它的東西，上層不該知道下層是什麼（fsm 不知道格是 fsm、agent 不知道工具是 agent）；想看子層要另有機制，沒機制就不碰；對別人的錯明寫採「入口默認正常／入口檢查」「出口保證」「事先列出」哪一種；錯誤路徑濃縮成少數幾條。條文在 [proto8 C-56、C-52、C-53](../../../proto8/docs/CONCEPTS/01-設計理念.md)。
- **命名**（使用者 10-15，proto8 起）：資料夾、檔名、JSON key 全小寫加底線，主題放前面；對外指令名＝同名把底線換連字號；環境變數全大寫加底線；程式照語言規範（PEP8）並跟檔名固定對應（`NodePath` ⇄ `node_path`）；裝同類的資料夾用複數（`insts/a.json`）；新縮寫先進[縮寫表](../../../proto8/docs/CONCEPTS/abbr.json)。條文在 [proto8 C-54](../../../proto8/docs/CONCEPTS/01-設計理念.md)。
- **單檔行數門檻**：與 [STRUCTURE 觸發 A](../../STRUCTURE.md) 一致，程式碼單檔超過 300 行就該考慮拆。
- **`fork` 前後的界線**（`exec` 層專屬，但任何碰行程操作的程式碼都要守）：`fork` 之後、`execve` 之前只能呼叫 async-signal-safe 的 POSIX 操作，不能有 C++ 記憶體配置、`setenv`、字串操作。所有準備工作（環境變數合併、PATH 解析、`argv`／`envp` 實體化）都要在 `fork` 之前做完；細節見 `core/inst/docs/architecture.md`。
- **新增/改欄位或列舉值**要全域 grep 受影響處（C++ 型別、format 的 encode/decode、C ABI 的鏡像宣告與 static_assert）並同一個 commit 更新，不要分批留下不一致的中間狀態。

## 導航 index（code map）維護鏈

三個面向構成維護鏈：**程式碼 → code map → 文檔**。三份真相的完整優先序（含 normative 規格）在 [code-map「真相層優先序」](code-map.md)。

**優先級（衝突或時間不夠時，依序保持一致）：** 程式碼 > code map > 文檔。
**code map 與程式碼衝突時：以程式碼為準，立即修正 code map。**

**日常規則：**
1. **修改前**：先讀 code map，找到相關領域，只讀清單中列出的檔案——不要讀無關領域的檔案。
2. **修改後**：若新增或刪除了原始碼檔案，或某檔案的職責有顯著改變，必須同步更新 code map。
3. 原始碼檔案本身**不加**「對應 code map」的註釋（維護成本過高）；反向查找直接 grep code map 文件。
